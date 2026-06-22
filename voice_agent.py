

import os
import sys
import asyncio
import random
import time

# Force UTF-8 for Windows console to prevent emoji crashes
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import (
    Frame, LLMRunFrame, TranscriptionFrame, InterimTranscriptionFrame, TTSTextFrame,
    LLMMessagesAppendFrame,
    TextFrame, TTSSpeakFrame, UserStoppedSpeakingFrame, FunctionCallsStartedFrame,
    FunctionCallInProgressFrame, FunctionCallResultFrame, LLMTextFrame,
    BotStartedSpeakingFrame, TTSAudioRawFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.google.vertex.llm import GoogleVertexLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport, TransportParams

load_dotenv(override=True)

BLOSTEM_BACKEND_URL = os.getenv("BLOSTEM_BACKEND_URL", "http://localhost:8000")

# ─── Cascaded voice config (STT → LLM → guardrail → TTS) ────────────────────
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5")
# Pin STT language — auto-detect mis-fires on Hinglish (tags Hindi as en/mr → garbage).
SARVAM_STT_LANGUAGE = os.getenv("SARVAM_STT_LANGUAGE", "hi")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
# Voice LLM = Gemini 2.5 Flash: reliable native tool-calling (Llama-on-Groq
# intermittently mangles multi-arg tool calls) + strong multilingual Hindi.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
# Dedicated key for the voice LLM, separate from embeddings (GOOGLE_API_KEY) so
# the two don't share/compete for the same project quota. Falls back if unset.
GEMINI_LLM_API_KEY = os.getenv("GEMINI_LLM_API_KEY", "") or GOOGLE_API_KEY
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# VOICE_MODE = "cascaded" (Sarvam STT → Gemini text → Cartesia TTS, default) or
# "gemini_live" (audio-native: one model does STT+LLM+TTS, no separate STT). Flip
# via env to A/B Hindi quality + latency. NOTE in live mode there is NO text
# checkpoint before audio, so the PII guardrail does not apply (fintech caveat),
# and it uses Gemini's separate Live quota.
VOICE_MODE = os.getenv("VOICE_MODE", "cascaded").lower()
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "models/gemini-2.0-flash-live-001")
GEMINI_LIVE_VOICE = os.getenv("GEMINI_LIVE_VOICE", "Charon")
# Vertex AI (preferred for prod — billed, far higher limits than AI Studio's
# 20/day free tier). Auths via a service-account JSON + project + region, NOT an
# API key. If VERTEX_PROJECT_ID is set, the voice LLM uses Vertex; else AI Studio.
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-east4")
# Path to the service-account JSON. Falls back to ADC (GOOGLE_APPLICATION_CREDENTIALS).
VERTEX_CREDENTIALS_PATH = os.getenv("VERTEX_CREDENTIALS_PATH", "") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_MODEL = os.getenv("CARTESIA_MODEL", "sonic-3.5")
# Replace with a voice_id from YOUR Cartesia account (this is a public sample).
# For a Hindi/Indian accent, pick a Hindi voice in the Cartesia voice library.
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091")
# TTS synthesis language — "hi" gives Hindi pronunciation (Hinglish-friendly).
CARTESIA_LANGUAGE = os.getenv("CARTESIA_LANGUAGE", "hi")
# Cartesia uses base codes ("hi"); Sarvam STT requires region codes ("hi-IN").
_CARTESIA_LANG = {"hi": Language.HI, "en": Language.EN}.get(CARTESIA_LANGUAGE, Language.HI)
_STT_LANG = {"hi": Language.HI_IN, "en": Language.EN_IN}.get(SARVAM_STT_LANGUAGE, Language.HI_IN)

# Proactive behaviour toggles — both OFF by default. The bot must NOT speak before
# the user asks: it should not announce screens (NAV) nor errors (ERROR). When a
# technical issue erupts the backend still CAPTURES it into session state
# immediately (/state/error → record_error), and the bot can answer about it the
# moment the user asks (get_current_screen_context returns active_error). It just
# stays silent until then. Set PROACTIVE_ERROR=true in .env to re-enable announcing.
def _flag(name, default):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")
PROACTIVE_NAV = _flag("PROACTIVE_NAV", "false")
PROACTIVE_ERROR = _flag("PROACTIVE_ERROR", "false")


# ─── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """\
You are Blostem, a friendly and knowledgeable voice-based Indian financial advisor and onboarding assistant.

CRITICAL RULES:
- Adapt to the user's language. If they speak Hindi or Hinglish, reply in natural \
HINGLISH — conversational Hindi in Roman/Latin script mixed with common English words \
(e.g. "aapka FD account ready hai, koi tension nahi") — because the selected voice is a \
Hinglish speaker that pronounces romanized Hinglish naturally. If they speak Odia reply \
in Odia; if they speak pure English, reply in English.
- You are having a PHONE CONVERSATION — be natural, conversational, warm.
- Keep responses SHORT: 2-3 sentences max.
- NEVER use markdown, bullet points, emojis, HTML tags (no <b>), or any formatting — plain spoken words only.
- Sound like a helpful bank friend, not a robot.
- GROUNDING (critical): NEVER invent FD rates, product names, tax/TDS numbers, or definitions. If a tool returns an error or no data, tell the user you couldn't fetch it right now and to verify with the bank — do NOT make up an answer.

YOUR EXPERTISE & ROLE:
- You are assisting the user through a 9-step Fixed Deposit (FD) onboarding screen journey (KYC, Nominee, Payment, etc.).
- Fixed Deposits (FD): rates, maturity, TDS, tax-saving FDs
- Tax rules: Section 80C, 80TTA, 80TTB, new vs old regime
- Savings accounts, RD, PPF
- Senior citizen benefits

TOOL USAGE:
- For ANY policy, rule, FAQ, or when the user needs help with the current UI screen → ALWAYS call search_financial_rules
- For calculating FD maturity amounts → call calculate_fd_maturity
- For calculating income tax (old vs new regime) → call calculate_income_tax
- For calculating TDS on FD interest → call calculate_tds_on_fd_interest
- If the user asks for FD options → call recommend_fd_options
- If the user tells you their new age or investment amount → call update_user_profile. STATE-CHANGING ACTIONS NEED CONFIRMATION: first confirm the change with the user in one short sentence ("Aapki age 65 set kar doon?"); only after they say yes, call update_user_profile with confirm="true". If you call it with confirm="false" the system will ask you to confirm — never change anything without explicit user consent.
- SCREEN AWARENESS (answer in ONE turn, no tool): the latest "CURRENT SCREEN" system note is ALWAYS injected into your context and refreshed whenever the screen changes — TRUST IT as the live screen. For "which screen am I on / what do I do here / what's next", answer DIRECTLY from that note. Do NOT call get_current_screen_context for these — it adds a slow extra round-trip. Only call get_current_screen_context when you need deeper FAQ or active-error detail that the note doesn't contain.
- CRITICAL — SILENT, TEXT-FREE TOOL CALLS: When you use a tool, emit ONLY the tool call and absolutely NO spoken words in that same turn — no "Please wait", "Let me check", "Hold on", no preamble, no narration of what you are about to do. A turn is EITHER plain speech OR a single tool call, never both mixed together. After the tool result comes back, THEN speak the answer in a new turn.
- NEVER write a function name, "<function...>", JSON, or any tool/code syntax as spoken text. That is a bug. To use a tool you invoke it natively — you never type its name or arguments into your reply.
- REQUIRED INPUTS: Before calling a calculator (calculate_fd_maturity / calculate_income_tax / calculate_tds_on_fd_interest), you MUST already have every required number (e.g. principal, rate, tenure, total income, fd interest). If any is missing, ASK the user for it in ONE short sentence first — do NOT call the tool with guessed, zero, or made-up values.
- POINT TO THE SCREEN: when you're guiding the user to a specific field (e.g. explaining a PAN error, or telling them where to enter the amount), call highlight_field with the field key to visually highlight it for them while you speak.
- After getting tool results, speak the answer naturally in the user's language.
- Use the raw facts provided by the tools, do not invent numbers.
- When you receive a SYSTEM NOTE about a screen change, trust it as the latest state. Use the guidance text provided in the note to advise the user.

GREETING:
When you first connect, greet the user warmly:
"Namaste! Main Blostem hoon, aapka financial advisor. Aap abhi screen par apna FD account setup kar rahe hain. Aap screen par navigate kijiye, agar kahin atak jayein, ya FD aur tax ke baare mein kuch poochna ho, toh mujhe bataiye. Main aapki kaise madad kar sakta hoon?"
"""


# ─── Tool Definitions ──────────────────────────────────────────────────────
# Schemas live in voice_tools.py to keep this file focused on orchestration.
from voice_tools import TOOLS


# ─── Context window management ──────────────────────────────────────────────
# Chat APIs are stateless: every turn resends system prompt + tools + full
# history, so input tokens grow each turn. We keep the leading system messages
# (static → cacheable prefix) and bound the rest to the last N messages.
HISTORY_TAIL_MESSAGES = 16

# Short spoken fillers played WHILE a slow (RAG) tool runs, to mask the
# tool-exec + post-tool LLM-call gap. Spoken directly via TTS (not the LLM), so
# they don't interfere with the "silent tool calls" rule the LLM follows.
_FILLERS = ["Ek second…", "Theek hai, dekhta hoon…", "Bas abhi check karta hoon…"]

def _trim_context(context, keep_head: int, keep_tail: int = HISTORY_TAIL_MESSAGES) -> None:
    """Bound conversation history: keep the leading `keep_head` system messages +
    the last `keep_tail` messages. The tail start is advanced to a 'user'
    boundary so a tool-call/tool-result pair is never split (which APIs reject).
    Defensive: any failure just skips trimming rather than breaking the call."""
    try:
        msgs = context.get_messages()
        if len(msgs) <= keep_head + keep_tail:
            return

        def _role(m):
            return m.get("role") if isinstance(m, dict) else getattr(m, "role", None)

        head = list(msgs[:keep_head])
        tail = list(msgs[-keep_tail:])
        while tail and _role(tail[0]) != "user":
            tail.pop(0)
        if tail:
            context.set_messages(head + tail)
    except Exception as e:
        logger.warning(f"context trim skipped: {e}")


# ─── Transport Configuration ───────────────────────────────────────────────

def _make_transport_params() -> TransportParams:
    if VOICE_MODE == "gemini_live":
        # Gemini Live does turn detection + endpointing server-side (its own VAD),
        # so we only need Silero locally for snappy client interruption; no Smart Turn.
        return TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    # Cascaded: Silero VAD detects speech; Smart Turn v3 (bundled ONNX, ~12ms CPU)
    # decides semantic end-of-turn → responds faster without cutting the user off.
    return TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
        turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams(stop_secs=2.0)),
    )


transport_params = {"webrtc": lambda: _make_transport_params()}


# ─── Helper: Backend POST ──────────────────────────────────────────────────

def _session_headers(session_id: str | None) -> dict:
    return {"X-Session-Id": session_id} if session_id else {}


async def _backend_post(endpoint: str, payload: dict, session_id: str | None = None) -> dict:
    """POST to the Blostem backend (scoped to a session) and return the JSON."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BLOSTEM_BACKEND_URL}{endpoint}",
                json=payload,
                headers=_session_headers(session_id),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"Backend returned {resp.status}"}
    except Exception as e:
        logger.error(f"[BLOSTEM] Backend POST {endpoint} failed: {e}")
        return {"error": str(e)}


async def _backend_get(endpoint: str, session_id: str | None = None) -> dict:
    """GET from the Blostem backend (scoped to a session) and return the JSON."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BLOSTEM_BACKEND_URL}{endpoint}",
                headers=_session_headers(session_id),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"Backend returned {resp.status}"}
    except Exception as e:
        logger.error(f"[BLOSTEM] Backend GET {endpoint} failed: {e}")
        return {"error": str(e)}


# ─── Transcript Logger ─────────────────────────────────────────────────────

class TranscriptLogger(FrameProcessor):
    """Intercepts transcription frames and POSTs them to the backend
    so the frontend can display the conversation as chat bubbles.

    Captures:
      - TranscriptionFrame  → user speech text (from Gemini STT)
      - TTSTextFrame         → bot speech text (from Gemini output transcription)
    """

    def __init__(self, session_id: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._bot_buffer = ""
        self._session_id = session_id
        self._spec_last_words = 0   # word-count of the last speculated partial

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

        # Speculation (Phase C): on interim STT, fire SAFE RAG early on the user's
        # in-progress words so the final answer is already warm. Throttled — only
        # when the partial grows by ≥2 words — and fire-and-forget (never blocks
        # the audio pipeline). Unsafe tools stay commit-gated, so this is safe.
        if isinstance(frame, InterimTranscriptionFrame) and frame.text:
            words = frame.text.split()
            if len(words) >= 3 and len(words) - self._spec_last_words >= 2:
                self._spec_last_words = len(words)
                asyncio.create_task(_backend_post(
                    "/speculate", {"query": frame.text.strip()}, session_id=self._session_id))

        if isinstance(frame, TranscriptionFrame) and frame.text and frame.text.strip():
            self._spec_last_words = 0  # reset for the next utterance
            logger.info(f"[TRANSCRIPT] User: {frame.text.strip()}")
            await _backend_post("/state/transcript", {
                "role": "user",
                "text": frame.text.strip(),
            }, session_id=self._session_id)

        elif isinstance(frame, TTSTextFrame) and frame.text and frame.text.strip():
            # Cartesia emits word-level TTSTextFrames with no spaces → join with a
            # space, but not before punctuation (avoid "hoon ,").
            chunk = frame.text
            if (self._bot_buffer and not self._bot_buffer.endswith(" ")
                    and not chunk[:1] in (" ", ",", ".", "!", "?", "।", "’", "'")):
                self._bot_buffer += " "
            self._bot_buffer += chunk
            if any(self._bot_buffer.rstrip().endswith(c) for c in ".!?।"):
                text = self._bot_buffer.strip()
                if text:
                    logger.info(f"[TRANSCRIPT] Bot: {text}")
                    await _backend_post("/state/transcript", {
                        "role": "bot",
                        "text": text,
                    }, session_id=self._session_id)
                self._bot_buffer = ""

    async def cleanup(self):
        # Flush any remaining buffered bot text
        if self._bot_buffer.strip():
            await _backend_post("/state/transcript", {
                "role": "bot",
                "text": self._bot_buffer.strip(),
            }, session_id=self._session_id)
            self._bot_buffer = ""
        await super().cleanup()


# ─── Guardrail Gate (pre-TTS) ──────────────────────────────────────────────

class GuardrailGate(FrameProcessor):
    """Masks PII (Aadhaar/PAN/phone) in the text stream BEFORE it reaches TTS.

    This is the pre-speech guardrail the cascaded pipeline makes possible — with
    S2S there was no text checkpoint between the model and the audio. Per-frame
    best-effort; a fuller version would buffer to a sentence and run the full
    app.guardrails checks (compliance/citation) before speaking.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text:
            import re
            from app.pii_masker import mask_pii
            # Strip HTML/markup so tags like <b> aren't spoken or break word tracking.
            frame.text = re.sub(r"<[^>]+>", "", frame.text)
            frame.text = mask_pii(frame.text)
        await self.push_frame(frame, direction)


class LatencyTracker(FrameProcessor):
    """Measures the ENTIRE pipeline per turn: from when the user STOPS speaking to
    when the FIRST AUDIO CHUNK is produced (what the user actually hears), with a
    per-stage breakdown (STT → LLM#1 → tool → LLM#2 → TTS) and a tool-turn tag.

    Must sit AFTER the TTS service so it sees the audio output frames (which are
    produced downstream of the LLM). All upstream markers — UserStoppedSpeaking,
    the user TranscriptionFrame, function-call frames, and LLM text tokens — flow
    down through here too, so one processor captures every milestone.
    """

    def __init__(self):
        super().__init__()
        self._reset()

    def _reset(self):
        self.t0 = None            # user stopped speaking
        self.t_stt = None         # final user transcript
        self.t_tool_start = None  # LLM emitted the tool call
        self.t_tool_end = None    # tool result came back
        self.t_token = None       # first LLM answer token
        self.tools: list[str] = []
        self.logged = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        now = time.perf_counter()

        if isinstance(frame, UserStoppedSpeakingFrame):
            self._reset()
            self.t0 = now
        elif self.t0 is not None and not self.logged:
            if isinstance(frame, TranscriptionFrame) and self.t_stt is None:
                self.t_stt = now
            elif isinstance(frame, (FunctionCallsStartedFrame, FunctionCallInProgressFrame)):
                if self.t_tool_start is None:
                    self.t_tool_start = now
                n = getattr(frame, "function_name", None)
                cand = [n] if n else []
                cand += [getattr(fc, "function_name", None) or getattr(fc, "name", None)
                         for fc in (getattr(frame, "function_calls", None) or [])]
                for name in cand:
                    if name and name not in self.tools:
                        self.tools.append(name)
            elif isinstance(frame, FunctionCallResultFrame) and self.t_tool_end is None:
                self.t_tool_end = now
            elif isinstance(frame, LLMTextFrame) and self.t_token is None:
                self.t_token = now
            elif isinstance(frame, TTSAudioRawFrame):
                self.logged = True
                self._log(now)

        await self.push_frame(frame, direction)

    def _log(self, t_audio: float):
        def ms(a, b):
            return f"{(b - a) * 1000:.0f}" if (a and b and b >= a) else "-"
        total = (t_audio - self.t0) * 1000
        parts = [f"stt={ms(self.t0, self.t_stt)}"]
        if self.tools:
            parts += [f"llm1={ms(self.t_stt, self.t_tool_start)}",
                      f"tool={ms(self.t_tool_start, self.t_tool_end)}",
                      f"llm2={ms(self.t_tool_end, self.t_token)}"]
        else:
            parts.append(f"think={ms(self.t_stt, self.t_token)}")
        parts.append(f"tts={ms(self.t_token, t_audio)}")
        tag = f"TOOL[{','.join(self.tools)}]" if self.tools else "no-tool"
        logger.info(f"[LATENCY] user→first-audio {total:.0f}ms · {tag} · " + " ".join(parts))


# ─── Bot Pipeline ──────────────────────────────────────────────────────────

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting Blostem Voice Agent with Gemini 3.1 Flash Live Preview")

    # Claim the session this voice connection belongs to. The frontend registers
    # its session_id as "pending" just before opening the voice iframe; we adopt
    # it here so all state/tool calls land in the right user's session.
    claim = await _backend_post("/session/voice-claim", {})
    session_id = claim.get("session_id", "default")
    logger.info(f"[BLOSTEM] Voice connection bound to session: {session_id}")

    # Fetch the user profile ONCE → a SEPARATE context message. The big system
    # prompt stays static (a cacheable prefix across turns AND across sessions).
    # The screen is deliberately NOT baked in here — it goes stale; the bot gets
    # the live screen from get_current_screen_context + SYSTEM NOTE messages.
    state_note = None
    try:
        data = await _backend_get("/state/get", session_id=session_id)
        if "error" not in data:
            state = data.get("user_state", {})
            state_note = (
                "USER PROFILE (can change via update_user_profile): "
                f"Age {state.get('age')}, Senior Citizen {state.get('senior_citizen')}, "
                f"Available Cash {state.get('cash')}, Language {state.get('language')}."
            )
            logger.info("Fetched user profile for LLM context.")
    except Exception as e:
        logger.error(f"Failed to fetch state: {e}")

    # STT + TTS are only used by the CASCADED pipeline. In gemini_live mode the
    # single Live model does STT+LLM+TTS, so we skip building them.
    stt = tts = None
    if VOICE_MODE != "gemini_live":
        # ── Cascaded: STT (Sarvam) → LLM (Gemini text) → guardrail → TTS (Cartesia) ──
        stt = SarvamSTTService(
            api_key=SARVAM_API_KEY,
            model=SARVAM_STT_MODEL,
            params=SarvamSTTService.InputParams(language=_STT_LANG),
        )
        tts = CartesiaTTSService(
            api_key=CARTESIA_API_KEY,
            voice_id=CARTESIA_VOICE_ID,
            model=CARTESIA_MODEL,
            params=CartesiaTTSService.InputParams(language=_CARTESIA_LANG),
        )

    # ── LLM selection ──
    if VOICE_MODE == "gemini_live":
        # Audio-native: one model ingests mic audio and emits speech directly — no
        # separate STT/TTS. system_instruction + tools go on the service (not the
        # context). CAVEAT: no text checkpoint before audio → PII guardrail N/A.
        logger.info(f"Voice LLM: Gemini Live (audio-native) model={GEMINI_LIVE_MODEL} voice={GEMINI_LIVE_VOICE}")
        llm = GeminiLiveLLMService(
            api_key=GEMINI_LLM_API_KEY,
            model=GEMINI_LIVE_MODEL,
            voice_id=GEMINI_LIVE_VOICE,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=TOOLS,
        )
    elif VERTEX_PROJECT_ID:
        logger.info(f"Voice LLM: Vertex AI (project={VERTEX_PROJECT_ID}, location={VERTEX_LOCATION})")
        llm = GoogleVertexLLMService(
            project_id=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
            credentials_path=VERTEX_CREDENTIALS_PATH or None,  # None → ADC
            model=GEMINI_MODEL,
        )
    else:
        logger.info("Voice LLM: AI Studio (GEMINI_LLM_API_KEY)")
        llm = GoogleLLMService(api_key=GEMINI_LLM_API_KEY, model=GEMINI_MODEL)

    # ── Tool Wrappers ──

    async def _filler():
        """Speak a short filler via TTS to mask slow-tool latency. Best-effort.
        Cascaded-only: TTSSpeakFrame targets the Cartesia TTS; Gemini Live emits
        its own audio and has no such injection point."""
        if VOICE_MODE == "gemini_live":
            return
        try:
            await task.queue_frames([TTSSpeakFrame(random.choice(_FILLERS))])
        except Exception:
            pass

    async def on_search_financial_rules(params: FunctionCallParams):
        query = params.arguments.get("query", "")
        logger.info(f"[BLOSTEM] RAG Search: '{query}'")
        await _filler()  # RAG is the slow path — cover the gap with a brief filler
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": f"🔍 Searching knowledge base: \"{query}\"",
        }, session_id=session_id)
        result = await _backend_post("/tools/rag", {"query": query}, session_id=session_id)

        # Push the image path to the chat transcript so the user sees what the bot is referencing
        image_path = result.get("image_path")
        if image_path and os.path.exists(image_path):
            await _backend_post("/state/transcript", {
                "role": "bot",
                "text": f"[IMAGE: {image_path}]",
            }, session_id=session_id)
            logger.info(f"[UI] Pushed image {image_path} to frontend chat.")
        await params.result_callback(result)

    async def on_calculate_fd_maturity(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] FD Maturity Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Calculating FD maturity amount…",
        }, session_id=session_id)
        result = await _backend_post("/tools/fd_maturity", params.arguments, session_id=session_id)
        await params.result_callback(result)

    async def on_recommend_fd_options(params: FunctionCallParams):
        payload = {
            "goal_type": params.arguments.get("goal_type", "growth"),
            "liquidity_need": params.arguments.get("liquidity_need", "medium"),
            "senior_citizen": params.arguments.get("senior_citizen", False),
        }
        logger.info(f"[BLOSTEM] FD Recommendation: {payload}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "📊 Finding best FD options…",
        }, session_id=session_id)
        result = await _backend_post("/tools/fd_recommendation", payload, session_id=session_id)
        await params.result_callback(result)

    async def on_update_user_profile(params: FunctionCallParams):
        payload = {
            "new_cash_amount": params.arguments.get("new_cash_amount"),
            "new_age": params.arguments.get("new_age"),
            "confirm": params.arguments.get("confirm", "false"),  # commit-point gate
        }
        logger.info(f"[BLOSTEM] Profile Update (confirm={payload['confirm']}): {payload}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "👤 Updating your profile…",
        }, session_id=session_id)
        result = await _backend_post("/tools/update_profile", payload, session_id=session_id)
        await params.result_callback(result)

    async def on_calculate_income_tax(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Income Tax Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Calculating income tax liability…",
        }, session_id=session_id)
        result = await _backend_post("/tools/income_tax", params.arguments, session_id=session_id)
        await params.result_callback(result)

    async def on_calculate_tds(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] TDS Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Checking TDS applicability…",
        }, session_id=session_id)
        result = await _backend_post("/tools/tds", params.arguments, session_id=session_id)
        await params.result_callback(result)

    async def on_get_screen_context(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Fetching screen context for user...")
        try:
            # Single fast state read; guidance is served O(1) from the in-memory
            # screen graph (screen_brief) — no embed / Pinecone / BM25 on this path.
            data = await _backend_get("/state/get", session_id=session_id)
            if "error" not in data:
                screen = data.get("current_screen", "Unknown Screen")
                brief = data.get("screen_brief") or {}
                pos = data.get("position") or {}
                # UI transcript is cosmetic — fire-and-forget so it never blocks
                # the tool result.
                asyncio.create_task(_backend_post("/state/transcript", {
                    "role": "tool",
                    "text": f"📱 Checking screen context: {screen}",
                }, session_id=session_id))
                result = {"current_screen": screen}
                if brief:
                    result["purpose"] = brief.get("purpose")
                    result["what_to_do"] = brief.get("do_here")
                    result["key_fields"] = brief.get("key_fields")
                    result["faqs"] = brief.get("faqs")
                    result["flow_position"] = brief.get("flow")
                else:
                    result["screen_guidance"] = data.get("current_rag_text") or "No specific guidance available for this screen."
                if pos.get("next_name"):
                    result["next_screen"] = pos["next_name"]
                if pos.get("seq") and pos.get("total"):
                    result["progress"] = f"step {pos['seq']} of {pos['total']}"
                # Live error the user is seeing → actionable remedy (classified).
                err = data.get("active_error")
                if err:
                    result["active_error"] = {
                        "what_happened": err.get("user_message"),
                        "what_to_do": err.get("suggested_action"),
                        "error_class": err.get("error_class"),
                    }
                    # Grounded KB detail (BM25) so the bot can elaborate if asked.
                    details = [d.get("text", "")[:300] for d in (err.get("kb_details") or [])]
                    if details:
                        result["active_error"]["details"] = details
                # Page-aware: exact focused field + field-level errors from the SDK
                # PageContext (WebSocket) → precise, situated help.
                page = data.get("page") or {}
                if page.get("focused_field"):
                    result["focused_field"] = page["focused_field"]
                if page.get("errors"):
                    result["field_errors"] = page["errors"]
                await params.result_callback(result)
            else:
                await params.result_callback({"error": "Failed to get screen context"})
        except Exception as e:
            await params.result_callback({"error": str(e)})

    async def on_highlight_field(params: FunctionCallParams):
        field = params.arguments.get("field", "")
        message = params.arguments.get("message")
        logger.info(f"[BLOSTEM] UI action → highlight_field: {field}")
        await _backend_post("/state/ui-action", {
            "action": {"type": "highlight_field", "field": field, "message": message},
        }, session_id=session_id)
        await params.result_callback({"ok": True, "highlighted": field})

    async def on_explain_term(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Explaining term: {params.arguments}")
        term = params.arguments.get("term", "")
        await _filler()  # RAG-backed → cover the gap with a brief filler
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": f"📖 Finding explanation for '{term}'…",
        }, session_id=session_id)
        result = await _backend_post("/tools/explain_term", params.arguments, session_id=session_id)
        await params.result_callback(result)

    # Register tool handlers SYNCHRONOUSLY (cancel_on_interruption=True): the LLM
    # waits for the result, injected as a standard `tool` message. Async mode
    # (False) uses `developer`/async_tool messages that Groq rejects.
    llm.register_function("search_financial_rules", on_search_financial_rules, cancel_on_interruption=True)
    llm.register_function("calculate_fd_maturity", on_calculate_fd_maturity, cancel_on_interruption=True)
    llm.register_function("recommend_fd_options", on_recommend_fd_options, cancel_on_interruption=True)
    llm.register_function("update_user_profile", on_update_user_profile, cancel_on_interruption=True)
    llm.register_function("calculate_income_tax", on_calculate_income_tax, cancel_on_interruption=True)
    llm.register_function("calculate_tds_on_fd_interest", on_calculate_tds, cancel_on_interruption=True)
    llm.register_function("get_current_screen_context", on_get_screen_context, cancel_on_interruption=True)
    llm.register_function("explain_term", on_explain_term, cancel_on_interruption=True)
    llm.register_function("highlight_field", on_highlight_field, cancel_on_interruption=True)

    # ── Pipeline (cascaded: STT → LLM → guardrail → TTS) ──
    # User transcripts now come from the STT TranscriptionFrame (handled by
    # TranscriptLogger); the Gemini-Live transcription hook is no longer needed.
    # Static system prompt first (cacheable prefix); profile as a separate tail
    # message. keep_head = number of leading messages the trimmer must preserve.
    # In gemini_live mode the system prompt is passed to the service (above), so
    # the context starts with only the profile note; in cascaded it leads with the
    # static system prompt (cacheable prefix).
    init_messages = []
    if VOICE_MODE != "gemini_live":
        init_messages.append({"role": "system", "content": SYSTEM_INSTRUCTION})
    if state_note:
        init_messages.append({"role": "system", "content": state_note})
    keep_head = len(init_messages)
    context = LLMContext(messages=init_messages, tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    transcript_logger = TranscriptLogger(session_id=session_id)
    latency = LatencyTracker()

    if VOICE_MODE == "gemini_live":
        # Audio-native: the Live model is STT+LLM+TTS in one. No Sarvam/Cartesia,
        # no guardrail (no text checkpoint), no Smart Turn (server-side VAD).
        pipeline = Pipeline([
            transport.input(),
            user_aggregator,
            llm,                 # Gemini Live: audio in → speech out (+ tool calls)
            transcript_logger,
            transport.output(),
            assistant_aggregator,
        ])
    else:
        guardrail = GuardrailGate()
        pipeline = Pipeline([
            transport.input(),       # Mic audio (WebRTC) + Silero VAD turn detection
            stt,                     # Sarvam Saarika v2.5 → user transcription
            user_aggregator,         # Aggregate user turn into context
            llm,                     # Gemini text LLM + tool calling
            guardrail,               # Mask PII BEFORE it is spoken
            tts,                     # Cartesia Sonic → speech audio
            latency,                 # Full-pipeline timing: user-stop → first audio chunk
            transcript_logger,       # Capture user/bot transcriptions → backend
            transport.output(),      # Speaker audio to browser
            assistant_aggregator,    # Track assistant response turns
        ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=300,
    )

    # ── Events ──

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected — triggering greeting")
        # Clear old conversation transcript for a fresh session
        await _backend_post("/state/clear-transcript", {}, session_id=session_id)
        context.add_message({
            "role": "user",
            "content": "Please introduce yourself using the greeting from your system instructions. Speak in Hinglish.",
        })
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    # ── Background Polling Task ──
    import asyncio

    def _screen_note(d: dict) -> str:
        """Compact current-screen context injected into the LLM so 'where am I /
        what do I do here / what's next' is answered in ONE call — no
        get_current_screen_context tool round-trip (which cost ~1s / a 2nd LLM call)."""
        sb = d.get("screen_brief") or {}
        pos = d.get("position") or {}
        parts = [f"CURRENT SCREEN: {d.get('current_screen', '?')}."]
        if sb.get("purpose"):
            parts.append(f"Purpose: {sb['purpose']}")
        if sb.get("do_here"):
            parts.append(f"What the user does here: {sb['do_here']}")
        if pos.get("seq") and pos.get("total"):
            parts.append(f"Step {pos['seq']} of {pos['total']}.")
        if d.get("next_screen"):
            parts.append(f"Next screen: {d['next_screen']}.")
        return " ".join(parts)

    async def poll_screen_changes():
        last_screen = None
        last_error_ts = None
        error_baselined = False  # don't announce an error that existed pre-connect
        while True:
            try:
                data = await _backend_get("/state/get", session_id=session_id)
                if "error" not in data:
                    current = data.get("current_screen")
                    if current and current != last_screen:
                        if last_screen is not None:
                            logger.info(f"[UI] Screen changed: {last_screen} → {current}")
                        # Inject the live screen context into the LLM so screen/nav
                        # questions are answered in ONE call (no tool round-trip).
                        try:
                            await task.queue_frames([LLMMessagesAppendFrame(
                                [{"role": "system", "content": _screen_note(data)}], run_llm=False)])
                        except Exception as e:
                            logger.error(f"[screen-inject] {e}")
                        # Speak on an ACTUAL change only if PROACTIVE_NAV is enabled
                        # (default off → quiet on navigation; helps only when asked).
                        if last_screen is not None and PROACTIVE_NAV:
                            spos = data.get("position") or {}
                            line = f"Aap ab {current} screen par hain."
                            if spos.get("next_name"):
                                line += f" Iske baad {spos['next_name']} ka step aayega."
                            await task.queue_frames([TTSSpeakFrame(line)])

                    # Proactively help when a NEW error appears (gated by PROACTIVE_ERROR,
                    # default off → silent unless enabled).
                    err = data.get("active_error")
                    err_ts = err.get("timestamp") if err else None
                    if PROACTIVE_ERROR and error_baselined and err and err_ts != last_error_ts:
                        logger.info(f"[UI] Error surfaced: {err.get('error_class')} on {err.get('screen')}")
                        eline = f"{err.get('user_message','')} {err.get('suggested_action','')}".strip()
                        if eline:
                            await task.queue_frames([TTSSpeakFrame(eline)])
                    last_error_ts = err_ts
                    error_baselined = True  # subsequent ticks announce only NEW errors

                    last_screen = current
                    _trim_context(context, keep_head)  # bound history each tick
            except Exception as e:
                logger.error(f"[Polling Error] {e}")
            await asyncio.sleep(1.5)

    poll_task = asyncio.create_task(poll_screen_changes())

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)
    
    poll_task.cancel()


# ─── Entry Point ────────────────────────────────────────────────────────────

async def bot(runner_args: RunnerArguments):
    """Main bot entry point compatible with Pipecat Cloud."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
