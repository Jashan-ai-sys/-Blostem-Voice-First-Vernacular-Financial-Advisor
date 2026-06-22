# Blostem Voice Assistant — embeddable widget

A single, framework-agnostic JS file (`blostem-widget.js`) that adds the Blostem
voice assistant as a **floating button** to any existing web app — no React, no
build step, no dependencies. Include one `<script>` tag and it appears.

## Integrate (the only step your system needs)

Add this once, anywhere in your page (ideally before `</body>`):

```html
<script
  src="https://your-cdn/blostem-widget.js"
  data-backend="https://api.yourco.com"     <!-- FastAPI backend base URL -->
  data-voice="https://voice.yourco.com"      <!-- voice agent base URL (/api/offer) -->
  data-language="Hinglish"
  defer></script>
```

That's it — a floating **“Need help?”** button appears bottom-right. Tapping it
starts a one-tap **voice call** and the button morphs in place into a small
“Listening…” pill. There is **no chat panel** — it's voice only. Nothing else to wire.

### Alternative: configure in JS
```html
<script>
  window.BlostemConfig = {
    backend: "https://api.yourco.com",
    voice:   "https://voice.yourco.com",
    language: "Hinglish",
    autoInit: true,
  };
</script>
<script src="https://your-cdn/blostem-widget.js" defer></script>
```

## Optional: make it screen-aware
If you want the assistant to know which screen the user is on (so it can help
contextually), call this from your app on navigation — that's the only hook:

```js
BlostemWidget.setScreen("tenure_selection");   // your screen id
BlostemWidget.reportError({ code: "PAYMENT_DECLINED", http_status: 402 }); // surface an error
```

## Public API (`window.BlostemWidget`)
| Method | Purpose |
|---|---|
| `init(cfg)` | mount manually (only if `autoInit:false`) |
| `start()` / `stop()` | begin / end the voice call (aliases: `open()` / `close()`) |
| `setScreen(screenId, step?)` | tell the assistant the current screen |
| `reportError({code,message,http_status,screen})` | surface a runtime error |
| `destroy()` | remove the widget |

## What it does under the hood
- Persists a per-browser `X-Session-Id` (localStorage) and scopes all calls to it.
- **Voice:** mic → WebRTC offer → `POST {voice}/api/offer` → plays the agent audio.
- **Screen / errors:** `POST {backend}/state/screen` and `/state/error` (host-driven, page-aware help).
- Injects its own scoped CSS (`blostem-*` classes) so it won't clash with host styles.

## Requirements
- Served over **HTTPS** in production (microphone access requires a secure context).
- The backend must allow the host origin via **CORS**.

## Test locally
Open `embed/demo.html` (set the backend/voice URLs in it) with all three services
running, and click the floating button.
