// Minimal WebRTC client for the Pipecat SmallWebRTC voice agent.
//
// Why this exists: the Pipecat prebuilt UI (the iframe) makes the user click its
// own "Connect" button. We instead drive the connection ourselves so a single
// tap in our widget connects directly — mic → SDP offer → /api/offer → answer.
//
// Contract (verified against pipecat.runner): POST {VOICE_BASE}/api/offer with
// {sdp, type:"offer", request_data} → returns the SDP answer {sdp, type}.
// We use non-trickle ICE (gather fully, then send one offer) for simplicity.

import { VOICE_BASE, getSessionId, registerVoiceSession } from "@/lib/session";

export type VoiceState = "idle" | "connecting" | "live" | "ended" | "error";

export interface VoiceConnection {
  disconnect: () => void;
}

function waitForIce(pc: RTCPeerConnection): Promise<void> {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === "complete") return resolve();
    const check = () => {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", check);
        resolve();
      }
    };
    pc.addEventListener("icegatheringstatechange", check);
    setTimeout(resolve, 3000); // fallback: don't wait forever for TURN/relay
  });
}

export async function connectVoice(opts: {
  onState: (s: VoiceState) => void;
  onRemoteStream: (stream: MediaStream) => void;
}): Promise<VoiceConnection> {
  opts.onState("connecting");

  // Tell the backend which session this voice connection belongs to (the bot
  // claims it on connect), so transcripts/state land in the right session.
  await registerVoiceSession();

  const pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });

  // Pipecat's SmallWebRTC transport waits for the CLIENT to open a data channel
  // (it listens via on("datachannel")). Without it the connection degrades and
  // the bot's app messages/handshake never complete. Create it before the offer.
  pc.createDataChannel("messaging");

  pc.ontrack = (e) => {
    if (e.streams && e.streams[0]) opts.onRemoteStream(e.streams[0]);
  };
  pc.onconnectionstatechange = () => {
    const s = pc.connectionState;
    if (s === "connected") opts.onState("live");
    else if (s === "failed" || s === "disconnected" || s === "closed") opts.onState("ended");
  };

  let mic: MediaStream;
  try {
    // Echo cancellation stops the bot's TTS (from the speakers) bleeding back
    // into the mic and being re-transcribed as garbage (a feedback loop).
    mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch {
    opts.onState("error"); // mic denied / unavailable
    pc.close();
    throw new Error("microphone unavailable");
  }
  mic.getTracks().forEach((t) => pc.addTrack(t, mic)); // sendrecv → we also receive TTS

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitForIce(pc);

  try {
    const resp = await fetch(`${VOICE_BASE}/api/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sdp: pc.localDescription!.sdp,
        type: pc.localDescription!.type,
        request_data: { session_id: getSessionId() },
      }),
    });
    if (!resp.ok) throw new Error(`offer failed: ${resp.status}`);
    const answer = await resp.json();
    await pc.setRemoteDescription(answer);
  } catch (e) {
    opts.onState("error");
    mic.getTracks().forEach((t) => t.stop());
    pc.close();
    throw e;
  }

  return {
    disconnect: () => {
      mic.getTracks().forEach((t) => t.stop());
      pc.close();
      opts.onState("idle");
    },
  };
}
