"""
Blostem Voice Agent — Pipecat + Gemini 3.1 Flash Live Preview
=============================================================
A realtime speech-to-speech financial advisor powered by:
  - Gemini 3.1 Flash Live Preview (realtime voice model)
  - Blostem RAG backend (LangGraph + Pinecone + Gemini 2.5 Flash)
  - Pipecat WebRTC transport (browser-based voice UI)

Run:
    python voice_agent.py -t webrtc

Then open http://localhost:7860/client/ and click "Connect".
"""

import os
import sys

# Force UTF-8 for Windows console to prevent emoji crashes
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import Frame, LLMRunFrame, TranscriptionFrame, TTSTextFrame, UserImageRawFrame, LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import BaseTransport, TransportParams

load_dotenv(override=True)

BLOSTEM_BACKEND_URL = os.getenv("BLOSTEM_BACKEND_URL", "http://localhost:8000")


# ─── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """\
You are Blostem, a friendly and knowledgeable voice-based Indian financial advisor and onboarding assistant.

CRITICAL RULES:
- Adapt to the user's language automatically. If the user speaks Odia, respond \
fluently in conversational Odia. If they speak Hindi/English, use Hinglish.
- You are having a PHONE CONVERSATION — be natural, conversational, warm.
- Keep responses SHORT: 2-3 sentences max.
- NEVER use markdown, bullet points, emojis, or formatting.
- Sound like a helpful bank friend, not a robot.

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
- If the user tells you their new age or investment amount → ALWAYS call update_user_profile
- If the user asks which screen they are on, what to do, or needs help navigating → ALWAYS call get_current_screen_context FIRST. NEVER guess the screen from old context. The screen changes frequently.
- IMPORTANT: NEVER say "Please wait", "Let me check", or "Hold on" before calling a tool. Call the tool IMMEDIATELY in silence.
- After getting tool results, speak the answer naturally in the user's language.
- Use the raw facts provided by the tools, do not invent numbers.
- When you receive a SYSTEM NOTE about a screen change, trust it as the latest state. Use the guidance text provided in the note to advise the user.

GREETING:
When you first connect, greet the user warmly:
"Namaste! Main Blostem hoon, aapka financial advisor. Aap abhi screen par apna FD account setup kar rahe hain. Aap screen par navigate kijiye, agar kahin atak jayein, ya FD aur tax ke baare mein kuch poochna ho, toh mujhe bataiye. Main aapki kaise madad kar sakta hoon?"
"""


# ─── Tool Definitions ──────────────────────────────────────────────────────

SEARCH_RULES_TOOL = FunctionSchema(
    name="search_financial_rules",
    description="Search official knowledge base for rules, FDs, TDS, savings, etc.",
    properties={
        "query": {"type": "string", "description": "Search query"},
    },
    required=["query"],
)

CALC_MATURITY_TOOL = FunctionSchema(
    name="calculate_fd_maturity",
    description="Calculates final maturity amount and total interest earned for a fixed deposit.",
    properties={
        "principal": {"type": "number", "description": "Initial amount invested"},
        "annual_rate_percent": {"type": "number", "description": "Annual interest rate percentage (e.g. 7.5)"},
        "tenure_years": {"type": "number", "description": "Duration in years"},
        "compounding_frequency": {
            "type": "string",
            "enum": ["yearly", "half_yearly", "quarterly", "monthly"],
            "description": "How often interest compounds",
        },
    },
    required=["principal", "annual_rate_percent", "tenure_years", "compounding_frequency"],
)

RECOMMEND_FD_TOOL = FunctionSchema(
    name="recommend_fd_options",
    description="A rule-based scoring engine that recommends FDs based on the user's profile.",
    properties={
        "goal_type": {"type": "string", "description": "Financial goal, e.g., 'tax_saving' or 'growth'."},
        "liquidity_need": {"type": "string", "description": "Liquidity need: 'high', 'medium', or 'low'."},
        "senior_citizen": {"type": "boolean", "description": "Whether the user is a senior citizen."},
    },
    required=["goal_type", "liquidity_need", "senior_citizen"],
)

UPDATE_PROFILE_TOOL = FunctionSchema(
    name="update_user_profile",
    description="Call this tool if the user explicitly changes their age or investment amount.",
    properties={
        "new_cash_amount": {"type": "number", "description": "The new amount the user wants to invest."},
        "new_age": {"type": "number", "description": "The user's updated age."},
    },
    required=[],
)

CALC_INCOME_TAX_TOOL = FunctionSchema(
    name="calculate_income_tax",
    description="Calculates basic income tax liability using old vs new tax regimes. Use when asked to calculate tax.",
    properties={
        "total_income": {"type": "number", "description": "Total annual income."},
        "age": {"type": "number", "description": "Age of the taxpayer."},
        "regime": {"type": "string", "enum": ["old", "new", "both"], "description": "Tax regime preference. Pass 'both' to compare."},
    },
    required=["total_income", "age", "regime"],
)

CALC_TDS_TOOL = FunctionSchema(
    name="calculate_tds_on_fd_interest",
    description="Determines if TDS applies to FD interest based on age and PAN.",
    properties={
        "age": {"type": "number", "description": "Age of the individual."},
        "fd_interest": {"type": "number", "description": "Total projected FD interest."},
        "pan_available": {"type": "boolean", "description": "Whether PAN card is linked."},
    },
    required=["age", "fd_interest", "pan_available"],
)

GET_SCREEN_TOOL = FunctionSchema(
    name="get_current_screen_context",
    description="Retrieves the exact screen name and step the user is currently looking at in the UI. Call this when the user needs help navigating.",
    properties={
        "fetch_context": {"type": "boolean", "description": "Set to true to fetch context."}
    },
    required=["fetch_context"],
)

EXPLAIN_TERM_TOOL = FunctionSchema(
    name="explain_term",
    description="Explains a specific financial term in simple language. Call this when the user asks what a complex financial term means.",
    properties={
        "term": {"type": "string", "description": "The specific financial term to explain."},
        "language": {"type": "string", "description": "The language code, e.g. 'en', 'hi', or 'pa'. Defaults to 'en'."}
    },
    required=["term"],
)

TOOLS = ToolsSchema(
    standard_tools=[SEARCH_RULES_TOOL, CALC_MATURITY_TOOL, RECOMMEND_FD_TOOL, UPDATE_PROFILE_TOOL, CALC_INCOME_TAX_TOOL, CALC_TDS_TOOL, GET_SCREEN_TOOL, EXPLAIN_TERM_TOOL],
)


# ─── Transport Configuration ───────────────────────────────────────────────

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


# ─── Helper: Backend POST ──────────────────────────────────────────────────

async def _backend_post(endpoint: str, payload: dict) -> dict:
    """POST to the Blostem backend and return the JSON response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BLOSTEM_BACKEND_URL}{endpoint}", json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"Backend returned {resp.status}"}
    except Exception as e:
        logger.error(f"[BLOSTEM] Backend POST {endpoint} failed: {e}")
        return {"error": str(e)}


# ─── Transcript Logger ─────────────────────────────────────────────────────

class TranscriptLogger(FrameProcessor):
    """Intercepts transcription frames and POSTs them to the backend
    so the frontend can display the conversation as chat bubbles.

    Captures:
      - TranscriptionFrame  → user speech text (from Gemini STT)
      - TTSTextFrame         → bot speech text (from Gemini output transcription)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bot_buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text and frame.text.strip():
            logger.info(f"[TRANSCRIPT] User: {frame.text.strip()}")
            await _backend_post("/state/transcript", {
                "role": "user",
                "text": frame.text.strip(),
            })

        elif isinstance(frame, TTSTextFrame) and frame.text and frame.text.strip():
            # Buffer bot text chunks and flush on sentence boundaries
            self._bot_buffer += frame.text
            if any(self._bot_buffer.rstrip().endswith(c) for c in ".!?।"):
                text = self._bot_buffer.strip()
                if text:
                    logger.info(f"[TRANSCRIPT] Bot: {text}")
                    await _backend_post("/state/transcript", {
                        "role": "bot",
                        "text": text,
                    })
                self._bot_buffer = ""

    async def cleanup(self):
        # Flush any remaining buffered bot text
        if self._bot_buffer.strip():
            await _backend_post("/state/transcript", {
                "role": "bot",
                "text": self._bot_buffer.strip(),
            })
            self._bot_buffer = ""
        await super().cleanup()


# ─── Bot Pipeline ──────────────────────────────────────────────────────────

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting Blostem Voice Agent with Gemini 3.1 Flash Live Preview")

    # Fetch initial user state from backend to personalise the system prompt
    dynamic_instruction = SYSTEM_INSTRUCTION
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BLOSTEM_BACKEND_URL}/state/get") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = data.get("user_state", {})
                    screen = data.get("current_screen", "Unknown")
                    dynamic_instruction += (
                        f"\n\n--- CURRENT USER STATE ---\n"
                        f"Age: {state.get('age')}\n"
                        f"Senior Citizen: {state.get('senior_citizen')}\n"
                        f"Available Cash: {state.get('cash')}\n"
                        f"Language: {state.get('language')}\n"
                        f"Current Screen: {screen}\n"
                        f"--------------------------\n"
                    )
                    logger.info("Successfully fetched user state for Gemini Live prompt.")
    except Exception as e:
        logger.error(f"Failed to fetch state: {e}")

    # ── LLM (Gemini Live — server-side VAD handles turn detection) ──
    llm = GeminiLiveLLMService(
        api_key=os.environ["GOOGLE_API_KEY"],
        settings=GeminiLiveLLMService.Settings(
            system_instruction=dynamic_instruction,
            model="gemini-3.1-flash-live-preview",
        ),
        tools=TOOLS,
    )

    # ── Tool Wrappers ──

    async def on_search_financial_rules(params: FunctionCallParams):
        query = params.arguments.get("query", "")
        logger.info(f"[BLOSTEM] RAG Search: '{query}'")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": f"🔍 Searching knowledge base: \"{query}\"",
        })
        result = await _backend_post("/tools/rag", {"query": query})
        
        # Push the image path to the chat transcript so the user sees what the bot is referencing
        image_path = result.get("image_path")
        if image_path and os.path.exists(image_path):
            await _backend_post("/state/transcript", {
                "role": "bot",
                "text": f"[IMAGE: {image_path}]",
            })
            logger.info(f"[UI] Pushed image {image_path} to frontend chat.")
        await params.result_callback(result)

    async def on_calculate_fd_maturity(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] FD Maturity Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Calculating FD maturity amount…",
        })
        result = await _backend_post("/tools/fd_maturity", params.arguments)
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
        })
        result = await _backend_post("/tools/fd_recommendation", payload)
        await params.result_callback(result)

    async def on_update_user_profile(params: FunctionCallParams):
        payload = {
            "new_cash_amount": params.arguments.get("new_cash_amount"),
            "new_age": params.arguments.get("new_age"),
        }
        logger.info(f"[BLOSTEM] Profile Update: {payload}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "👤 Updating your profile…",
        })
        result = await _backend_post("/tools/update_profile", payload)
        await params.result_callback(result)

    async def on_calculate_income_tax(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Income Tax Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Calculating income tax liability…",
        })
        result = await _backend_post("/tools/income_tax", params.arguments)
        await params.result_callback(result)

    async def on_calculate_tds(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] TDS Calc: {params.arguments}")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": "🧮 Checking TDS applicability…",
        })
        result = await _backend_post("/tools/tds", params.arguments)
        await params.result_callback(result)

    async def on_get_screen_context(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Fetching screen context for user...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BLOSTEM_BACKEND_URL}/state/get") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        screen = data.get("current_screen", "Unknown Screen")
                        rag_text = data.get("current_rag_text", "")
                        rag_image = data.get("current_rag_image", "")
                        await _backend_post("/state/transcript", {
                            "role": "tool",
                            "text": f"📱 Checking screen context: {screen}",
                        })
                        result = {
                            "current_screen": screen,
                            "screen_guidance": rag_text or "No specific guidance available for this screen.",
                        }
                        if rag_image:
                            result["reference_image"] = rag_image
                        await params.result_callback(result)
                    else:
                        await params.result_callback({"error": "Failed to get screen context"})
        except Exception as e:
            await params.result_callback({"error": str(e)})

    async def on_explain_term(params: FunctionCallParams):
        logger.info(f"[BLOSTEM] Explaining term: {params.arguments}")
        term = params.arguments.get("term", "")
        await _backend_post("/state/transcript", {
            "role": "tool",
            "text": f"📖 Finding explanation for '{term}'…",
        })
        result = await _backend_post("/tools/explain_term", params.arguments)
        await params.result_callback(result)

    # Register tool handlers (don't cancel during interruption — let them finish)
    llm.register_function("search_financial_rules", on_search_financial_rules, cancel_on_interruption=False)
    llm.register_function("calculate_fd_maturity", on_calculate_fd_maturity, cancel_on_interruption=False)
    llm.register_function("recommend_fd_options", on_recommend_fd_options, cancel_on_interruption=False)
    llm.register_function("update_user_profile", on_update_user_profile, cancel_on_interruption=False)
    llm.register_function("calculate_income_tax", on_calculate_income_tax, cancel_on_interruption=False)
    llm.register_function("calculate_tds_on_fd_interest", on_calculate_tds, cancel_on_interruption=False)
    llm.register_function("get_current_screen_context", on_get_screen_context, cancel_on_interruption=False)
    llm.register_function("explain_term", on_explain_term, cancel_on_interruption=False)

    # ── Capture user speech via LLM transcription hook ──
    _original_input_handler = llm._handle_msg_input_transcription

    async def _patched_input_transcription(message):
        await _original_input_handler(message)
        try:
            text = message.server_content.input_transcription.text
            if text and text.strip():
                logger.info(f"[TRANSCRIPT] User: {text.strip()}")
                await _backend_post("/state/transcript", {
                    "role": "user",
                    "text": text.strip(),
                })
        except Exception as e:
            logger.error(f"[TRANSCRIPT] User capture error: {e}")

    llm._handle_msg_input_transcription = _patched_input_transcription

    # ── Pipeline ──
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    transcript_logger = TranscriptLogger()

    pipeline = Pipeline([
        transport.input(),       # Mic audio from browser (WebRTC)
        user_aggregator,         # Aggregate user speech turns
        llm,                     # Gemini Live: STT + LLM + TTS (server-side VAD)
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
        await _backend_post("/state/clear-transcript", {})
        context.add_message({
            "role": "developer",
            "content": "Please introduce yourself to the user using the greeting from your system instructions. Speak in Hinglish.",
        })
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    # ── Background Polling Task ──
    import asyncio
    async def poll_screen_changes():
        last_screen = None
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{BLOSTEM_BACKEND_URL}/state/get") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            current = data.get("current_screen")
                            rag_text = data.get("current_rag_text", "")
                            if last_screen is not None and current and current != last_screen:
                                logger.info(f"[UI] Screen changed: {last_screen} → {current}")
                                
                                # Build a rich context message for Gemini
                                note = f"SYSTEM NOTE: The user has just navigated to the '{current}' screen."
                                if rag_text:
                                    note += f"\n\nHere is the relevant guidance from the knowledge base for this screen:\n{rag_text}"
                                note += "\n\nBriefly guide the user on what to do on this screen."
                                
                                msg = {"role": "user", "content": note}
                                await task.queue_frames([LLMMessagesAppendFrame([msg])])
                                
                            last_screen = current
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
