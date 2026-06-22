/*!
 * Blostem Voice Assistant — embeddable floating-button widget (VOICE-ONLY).
 * Drop-in, framework-agnostic, no build step. Include once on any page:
 *
 *   <script
 *     src="https://your-cdn/blostem-widget.js"
 *     data-backend="https://api.yourco.com"      // FastAPI backend
 *     data-voice="https://voice.yourco.com"       // voice agent (WebRTC /api/offer)
 *     data-language="Hinglish"
 *     defer></script>
 *
 * Or configure programmatically:
 *   window.BlostemConfig = { backend: "...", voice: "...", autoInit: true };
 *
 * Behaviour: a single floating "Need help?" button. Tap it → a live voice call
 * starts and the button morphs IN PLACE into a small "Listening…" pill (pulsing
 * mic + equalizer + end button). There is NO chat panel, no text input — you only
 * talk. Tap the end button to hang up; it shrinks back to the button.
 *
 * Public API (window.BlostemWidget):
 *   .init(cfg)            – mount manually (if autoInit:false)
 *   .start() / .stop()    – begin / end the voice call (aliases: open/close)
 *   .setScreen(screenId, step)  – tell the assistant which screen the user is on
 *   .reportError({code,message,http_status,screen}) – surface a runtime error
 *   .destroy()            – remove the widget
 *
 * It talks to the backend the same way the React app does: /session/voice-pending,
 * /api/offer (voice), /state/screen, /state/error — all scoped by an X-Session-Id
 * the widget persists in localStorage.
 */
(function () {
  "use strict";

  if (window.__blostemWidgetLoaded) return;
  window.__blostemWidgetLoaded = true;

  // ── Config ────────────────────────────────────────────────────────────────
  function readConfig() {
    var s = document.currentScript || (function () {
      var all = document.getElementsByTagName("script");
      for (var i = 0; i < all.length; i++) if (/blostem-widget\.js/.test(all[i].src)) return all[i];
      return null;
    })();
    var d = (s && s.dataset) || {};
    var g = window.BlostemConfig || {};
    return {
      backend: (g.backend || d.backend || "http://localhost:8000").replace(/\/$/, ""),
      voice: (g.voice || d.voice || "http://localhost:7860").replace(/\/$/, ""),
      language: g.language || d.language || "Hinglish",
      label: g.label || d.label || "Need help?",
      autoInit: g.autoInit != null ? g.autoInit : (d.autoinit !== "false"),
    };
  }
  var CFG = readConfig();

  // ── Session identity (persisted; sent as X-Session-Id) ──────────────────────
  var SKEY = "blostem_session_id";
  function sessionId() {
    var id = null;
    try { id = localStorage.getItem(SKEY); } catch (e) {}
    if (!id) {
      id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : "sess-" + Math.random().toString(36).slice(2) + "-" + Date.now();
      try { localStorage.setItem(SKEY, id); } catch (e) {}
    }
    return id;
  }
  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "X-Session-Id": sessionId() }, opts.headers || {});
    return fetch(CFG.backend + path, opts);
  }

  // ── State ───────────────────────────────────────────────────────────────────
  var state = { voice: "idle", conn: null, els: {} };

  // ── Styles (scoped, injected once) ──────────────────────────────────────────
  var CSS = "" +
    ".blostem-root{position:fixed;bottom:20px;right:18px;z-index:2147483000;font:600 14px system-ui,-apple-system,sans-serif}" +
    // collapsed button
    ".blostem-fab{display:flex;align-items:center;gap:8px;background:#C57708;color:#fff;border:none;border-radius:999px;padding:12px 16px;box-shadow:0 8px 24px rgba(0,0,0,.18);cursor:pointer;transition:background .15s,transform .12s}" +
    ".blostem-fab:hover{background:#A85F00}.blostem-fab:active{transform:scale(.95)}" +
    ".blostem-dot{width:8px;height:8px;border-radius:50%;background:#25AB21;animation:blostem-pulse 2s infinite}" +
    "@keyframes blostem-pulse{0%{box-shadow:0 0 0 0 rgba(37,171,33,.5)}70%{box-shadow:0 0 0 8px rgba(37,171,33,0)}100%{box-shadow:0 0 0 0 rgba(37,171,33,0)}}" +
    // active voice pill
    ".blostem-pill{display:flex;align-items:center;gap:10px;background:#fff;color:#191B1E;border:1px solid rgba(197,119,8,.3);border-radius:16px;padding:8px 10px 8px 12px;box-shadow:0 14px 40px rgba(0,0,0,.2);animation:blostem-pop .22s ease-out}" +
    "@keyframes blostem-pop{from{transform:scale(.8);opacity:0}to{transform:scale(1);opacity:1}}" +
    ".blostem-mic{position:relative;width:30px;height:30px;border-radius:50%;background:rgba(197,119,8,.15);display:flex;align-items:center;justify-content:center;flex:0 0 auto}" +
    ".blostem-mic svg{width:15px;height:15px;fill:#C57708}" +
    ".blostem-mic::after{content:'';position:absolute;inset:0;border-radius:50%;animation:blostem-ring 1.4s ease-out infinite}" +
    "@keyframes blostem-ring{0%{box-shadow:0 0 0 0 rgba(197,119,8,.45)}100%{box-shadow:0 0 0 13px rgba(197,119,8,0)}}" +
    ".blostem-eq{display:inline-flex;align-items:flex-end;gap:3px;height:18px}" +
    ".blostem-eq i{width:3px;border-radius:2px;background:#C57708;animation:blostem-eq .9s ease-in-out infinite}" +
    ".blostem-eq i:nth-child(2){animation-delay:.12s}.blostem-eq i:nth-child(3){animation-delay:.24s}.blostem-eq i:nth-child(4){animation-delay:.36s}.blostem-eq i:nth-child(5){animation-delay:.48s}" +
    "@keyframes blostem-eq{0%,100%{height:6px}50%{height:18px}}" +
    ".blostem-lbl{font-size:13px;color:#707275;white-space:nowrap}" +
    ".blostem-spin{width:16px;height:16px;border:2px solid rgba(197,119,8,.35);border-top-color:#C57708;border-radius:50%;animation:blostem-spin .8s linear infinite}" +
    "@keyframes blostem-spin{to{transform:rotate(360deg)}}" +
    ".blostem-end{width:30px;height:30px;border:none;border-radius:50%;background:rgba(215,38,61,.1);color:#D7263D;font-size:16px;line-height:1;cursor:pointer;flex:0 0 auto;display:flex;align-items:center;justify-content:center}" +
    ".blostem-end:hover{background:rgba(215,38,61,.2)}";

  function injectCSS() {
    if (document.getElementById("blostem-css")) return;
    var st = document.createElement("style");
    st.id = "blostem-css"; st.textContent = CSS;
    document.head.appendChild(st);
  }

  var MIC_SVG = '<svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg>';

  // ── Voice (WebRTC → voice agent /api/offer) ─────────────────────────────────
  function waitIce(pc) {
    return new Promise(function (res) {
      if (pc.iceGatheringState === "complete") return res();
      var t = setTimeout(res, 3000);
      pc.addEventListener("icegatheringstatechange", function chk() {
        if (pc.iceGatheringState === "complete") { clearTimeout(t); pc.removeEventListener("icegatheringstatechange", chk); res(); }
      });
    });
  }

  async function startVoice() {
    if (state.voice === "connecting" || state.voice === "live") return;
    setVoice("connecting");
    try {
      await api("/session/voice-pending", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId() }),
      }).catch(function () {});

      var pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
      pc.createDataChannel("messaging"); // SmallWebRTC expects the client to open one
      pc.ontrack = function (e) {
        if (e.streams && e.streams[0] && state.els.audio) {
          state.els.audio.srcObject = e.streams[0];
          state.els.audio.play().catch(function () {});
        }
      };
      pc.onconnectionstatechange = function () {
        var s = pc.connectionState;
        if (s === "connected") setVoice("live");
        else if (s === "failed" || s === "disconnected" || s === "closed") {
          if (state.voice !== "idle") setVoice("idle");
        }
      };

      var mic;
      try {
        mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      } catch (e) { setVoice("error"); pc.close(); return; }
      mic.getTracks().forEach(function (t) { pc.addTrack(t, mic); });

      var offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitIce(pc);

      var resp = await fetch(CFG.voice + "/api/offer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type, request_data: { session_id: sessionId() } }),
      });
      if (!resp.ok) throw new Error("offer failed: " + resp.status);
      await pc.setRemoteDescription(await resp.json());

      state.conn = { pc: pc, mic: mic };
    } catch (e) {
      setVoice("error");
      if (state.conn && state.conn.pc) { try { state.conn.pc.close(); } catch (x) {} }
      state.conn = null;
    }
  }

  function stopVoice() {
    if (state.conn) {
      try { state.conn.mic.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
      try { state.conn.pc.close(); } catch (e) {}
      state.conn = null;
    }
    setVoice("idle");
  }

  // ── Render (single root morphs button ⇄ voice pill) ─────────────────────────
  function setVoice(v) { state.voice = v; render(); }

  function render() {
    var root = state.els.root; if (!root) return;
    root.innerHTML = "";

    if (state.voice === "connecting" || state.voice === "live") {
      var pill = document.createElement("div");
      pill.className = "blostem-pill";
      if (state.voice === "connecting") {
        pill.innerHTML = '<span class="blostem-spin"></span><span class="blostem-lbl">Connecting…</span>';
      } else {
        pill.innerHTML =
          '<span class="blostem-mic">' + MIC_SVG + '</span>' +
          '<span class="blostem-eq"><i></i><i></i><i></i><i></i><i></i></span>' +
          '<span class="blostem-lbl">Listening…</span>';
      }
      var end = document.createElement("button");
      end.className = "blostem-end"; end.setAttribute("aria-label", "End call"); end.innerHTML = "&times;";
      end.onclick = stopVoice;
      pill.appendChild(end);
      root.appendChild(pill);
    } else {
      var fab = document.createElement("button");
      fab.className = "blostem-fab";
      fab.setAttribute("aria-label", "Talk to the assistant");
      var txt = state.voice === "error" ? "Mic blocked — retry" : CFG.label;
      fab.innerHTML = '<span class="blostem-dot"></span><span>' + esc(txt) + '</span>';
      fab.onclick = startVoice;
      root.appendChild(fab);
    }
  }

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  function mount() {
    injectCSS();
    if (state.els.root) return;
    var root = document.createElement("div");
    root.className = "blostem-root";
    var audio = document.createElement("audio");
    audio.style.display = "none"; audio.autoplay = true;
    document.body.appendChild(root);
    document.body.appendChild(audio);
    state.els.root = root;
    state.els.audio = audio;
    render();
  }

  // ── Public API ──────────────────────────────────────────────────────────────
  var Widget = {
    init: function (cfg) { if (cfg) Object.assign(CFG, cfg); mount(); return Widget; },
    start: startVoice,
    stop: stopVoice,
    open: startVoice,   // back-compat aliases
    close: stopVoice,
    // Host system tells us which screen the user is on (drives screen-aware help).
    setScreen: function (screenId, step) {
      return api("/state/screen", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ screen_id: screenId, step: step || 1 }),
      }).catch(function () {});
    },
    // Host system reports a runtime error → classified remedy + (optional) voice.
    reportError: function (e) {
      return api("/state/error", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(e || {}),
      }).then(function (r) { return r.json(); }).catch(function () { return null; });
    },
    destroy: function () {
      stopVoice();
      if (state.els.root) { state.els.root.remove(); state.els.root = null; }
      if (state.els.audio) { state.els.audio.remove(); state.els.audio = null; }
    },
  };
  window.BlostemWidget = Widget;

  if (CFG.autoInit) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { Widget.init(); });
    else Widget.init();
  }
})();
