<p align="center">
  <h1 align="center">🌸 Blostem — Voice-First Vernacular Financial Advisor</h1>
  <p align="center">
    <strong>RAG-Powered • Voice-Interactive • India-Focused</strong>
  </p>
  <p align="center">
    A real-time, voice-enabled financial assistant that guides users through Fixed Deposit onboarding with grounded, source-cited answers in Hindi, English, Hinglish, and Odia.
  </p>
</p>

---

## 📝 Founder's Note

### The Problem

Over 65% of India's adult population is eligible for basic banking products like Fixed Deposits, yet most never move past a savings account. The barrier isn't access — it's comprehension. A first-generation investor in Tier-2 India stares at terms like "cumulative payout," "TDS u/s 194A," and "premature penalty" in English-only interfaces and walks away. Bank branches are shrinking, call centres speak corporate, and existing fintech chatbots regurgitate canned FAQs without understanding what screen the user is stuck on. The cost of this gap is real: ₹4.3 lakh crore in household savings sits in zero-interest current accounts because the last mile of guidance simply doesn't exist in a language or medium people trust.

### The Solution

Blostem is a voice-first, vernacular financial advisor that sits inside the FD onboarding journey itself. A user speaks in Hindi, Hinglish, Punjabi, or Odia; the system answers in real-time speech grounded in 35+ official RBI/bank documents — not hallucinated generalities, but cited clauses with actual numbers. It knows which screen the user is on ("PAN verification"), what they just asked ("nominee add karna zaroori hai?"), and what tool to call (maturity calculator, TDS estimator, FD recommender) — all orchestrated through a single Gemini-powered voice pipeline that masks PII before it ever reaches the LLM. Critically, the system **maintains a live user profile throughout the conversation** — when a user says "meri age 63 hai" or "main 5 lakh invest karna chahta hoon," the voice agent automatically updates their state (age, amount, senior citizen status, risk profile) so every subsequent calculation and recommendation is personalized, without ever asking the user to fill a form.

### The Approach

We rejected a pure-LLM approach early: financial advice without retrieval is a liability. We also rejected a traditional IVR tree: users don't know which menu option maps to their real question. Instead, we bet on **RAG + tool-calling inside a real-time voice loop**. Gemini 3.1 Flash Live handles speech-to-speech with sub-second latency; a hierarchical parent-child chunking strategy over Pinecone ensures the retrieved context is never a sentence fragment; and LangChain-style deterministic tools (compound interest, old-vs-new tax regime, TDS thresholds) guarantee the math is never approximate. The voice agent, the RAG engine, and the calculator tools are three separate failure domains — if one degrades, the others still return useful, honest answers.

### What's Next

With another month, the first priority is **multi-turn memory with persistent user profiles** — remembering that Ramesh is 62, a senior citizen, has ₹5L to invest, and prefers quarterly payouts — so every subsequent session picks up where the last one ended. Second is **WhatsApp delivery via the Sarvam voice API**, because India's next 200 million internet users won't install another app, but they will reply to a WhatsApp voice note. Third is **real-time compliance drift detection**: when RBI changes a TDS threshold or DICGC raises its insurance cap, the pipeline should re-chunk, re-embed, and flag stale answers automatically — not wait for a human to notice.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🎙️ **Voice-First Interaction** | Real-time speech-to-speech via Pipecat + Gemini 3.1 Flash Live |
| 📚 **RAG-Grounded Answers** | All responses backed by Pinecone vector search over 35+ official bank documents |
| 🧮 **Financial Calculators** | FD maturity, income tax (old vs new regime), TDS on FD interest |
| 🔒 **PII Masking** | Regex-based masking of Aadhaar, PAN, and phone numbers before LLM processing |
| 🗺️ **9-Step Journey Awareness** | Context-aware guidance through the FD onboarding screen flow |
| 🌐 **Vernacular Support** | Adapts to Hindi, English, Hinglish, Odia, and Punjabi |
| 💡 **Term Explainer** | Click any financial term in chat to get a RAG-grounded plain-language explanation |
| 📊 **FD Recommendation Engine** | Rule-based scoring engine that suggests FDs based on user profile |
| 🧠 **Stateful User Profile via Voice** | System extracts and maintains age, amount, tenure, risk, and senior status from natural conversation — no forms needed |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
│                                                                 │
│   ┌──────────────────┐    ┌──────────────────────────────────┐  │
│   │  Pipecat WebRTC  │    │   Next.js Frontend (YieldWise)   │  │
│   │  Voice Widget    │    │   • Landing Page                 │  │
│   │  (port 7860)     │    │   • FD Booking Journey           │  │
│   └────────┬─────────┘    │   • Chat + Term Highlighter      │  │
│            │              │   • Dashboard                    │  │
│            │              │   • RAG Context Sidebar          │  │
│            │              └──────────────┬───────────────────┘  │
│            │                             │                      │
└────────────┼─────────────────────────────┼──────────────────────┘
             │ WebRTC                      │ HTTP (polling /state/get)
             ▼                             ▼
┌────────────────────────┐    ┌──────────────────────────────────┐
│   Voice Agent          │    │   FastAPI Backend (port 8000)    │
│   (voice_agent.py)     │───▶│                                  │
│                        │    │   /tools/rag                     │
│   • Gemini 3.1 Flash   │    │   /tools/fd_maturity             │
│     Live Preview       │    │   /tools/fd_recommendation       │
│   • PII Masker         │    │   /tools/income_tax              │
│   • Tool Calling       │    │   /tools/tds                     │
│   • Transcript Sync    │    │   /tools/explain_term            │
│                        │    │   /tools/update_profile           │
└────────────────────────┘    │   /state/screen                  │
                              │   /state/get                     │
                              │   /state/transcript              │
                              │                                  │
                              │   ┌────────────────────────────┐ │
                              │   │  RAG Engine (rag.py)       │ │
                              │   │  Pinecone + Gemini Embed 2 │ │
                              │   │  Hierarchical Chunking     │ │
                              │   └────────────────────────────┘ │
                              └──────────────────────────────────┘
```

---

## 📁 Project Structure

```
ragforblostem/
├── .env                          # API keys (Google, Pinecone, Sarvam)
├── voice_agent.py                # Pipecat voice pipeline (Gemini 3.1 Flash Live)
├── requirements.txt              # Python dependencies
│
├── app/                          # FastAPI Backend
│   ├── main.py                   # API routes & state management
│   ├── config.py                 # Pydantic settings (env vars)
│   ├── models.py                 # Request/Response schemas
│   ├── rag.py                    # RAG engine (Pinecone + Gemini Embedding 2)
│   ├── tool_service.py           # LangChain tools (FD calc, tax, TDS, explainer)
│   ├── recommendation_engine.py  # Rule-based FD recommendation scorer
│   ├── pii_masker.py             # Regex PII masking (Aadhaar, PAN, Phone)
│   └── state_manager.py          # LangGraph-style typed state definitions
│
├── data/                         # Knowledge Base
│   ├── *.pdf                     # 35+ official bank/RBI documents
│   ├── products.json             # Mock FD product catalog
│   ├── journey_screens.jsonl     # 9-step FD onboarding screen metadata
│   ├── journey_screens/          # Screen images for RAG context
│   ├── chunks/                   # Pre-processed retrieval chunks
│   └── raw/                      # Raw markdown source docs
│
├── scripts/                      # One-time data ingestion scripts
│   ├── chunk_data.py             # Hierarchical chunking pipeline
│   ├── ingest_pinecone.py        # Pinecone vector upsert
│   ├── embed_journey_screens.py  # Journey screen embedding
│   └── rename_and_build.py       # PDF rename & build utility
│
└── YieldWise/frontend/           # Next.js Frontend
    ├── app/
    │   └── page.tsx              # Main page (layout + RAG sidebar)
    ├── components/
    │   ├── LandingPage.tsx       # Hero landing page
    │   ├── BookingPage.tsx       # 9-step FD journey simulator
    │   ├── ChatPage.tsx          # Voice + Chat + Term Highlighter
    │   ├── DashboardPage.tsx     # Portfolio dashboard
    │   └── Navbar.tsx            # Navigation bar
    └── lib/                      # Utility functions
```

---

## 🛠️ Tools & Capabilities

The voice agent and backend expose **7 callable tools** that the Gemini LLM invokes automatically based on conversation context:

| Tool | Trigger | Description |
|---|---|---|
| `search_financial_rules` | Policy/rule/FAQ questions | Queries Pinecone RAG index with hierarchical context expansion |
| `calculate_fd_maturity` | "How much will I get?" | Compound interest calculator (yearly/quarterly/monthly) |
| `calculate_income_tax` | Tax comparison questions | Old vs New regime tax comparison (MVP logic) |
| `calculate_tds_on_fd_interest` | TDS-related questions | TDS threshold & rate calculation based on age + PAN |
| `recommend_fd_options` | "Which FD is best for me?" | Rule-based scorer using goal, liquidity, senior status |
| `update_user_profile` | User changes age/amount | Updates backend state for contextual calculations |
| `explain_term` | Click highlighted term in UI | RAG-grounded term explanation via Gemini 2.5 Flash |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- API Keys: Google AI (Gemini), Pinecone, Sarvam AI (optional)

### 1. Clone & Setup Environment

```bash
git clone <repo-url>
cd ragforblostem

# Create Python virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key
PINECONE_API_KEY=your_pinecone_api_key
SARVAM_API_KEY=your_sarvam_api_key    # Optional (for TTS)
```

### 3. Start the Backend (Terminal 1)

```bash
uvicorn app.main:app --reload
```

Backend runs on **http://localhost:8000**

### 4. Start the Voice Agent (Terminal 2)

```bash
python voice_agent.py -t webrtc
```

Voice agent runs on **http://localhost:7860**

### 5. Start the Frontend (Terminal 3)

```bash
cd YieldWise/frontend
npm install
npm run dev
```

Frontend runs on **http://localhost:3000**

### 6. Use the App

1. Open **http://localhost:3000** in your browser
2. Navigate to the **Chat** page
3. Click **Connect** on the voice widget to start talking
4. Ask questions like:
   - *"Mera FD kitne mein mature hoga?"*
   - *"TDS ka kya rule hai senior citizens ke liye?"*
   - *"Which FD should I choose for tax saving?"*

---

## 🧠 RAG Pipeline Details

### Knowledge Base

- **35+ PDF documents**: RBI master directions, bank FAQs, KYC norms, deposit insurance guidelines
- **Hierarchical chunking**: Parent-child chunk relationships for context expansion
- **Gemini Embedding 2** (`models/gemini-embedding-2`): 768-dimensional embeddings with task-type awareness
- **Pinecone index**: `financial-knowledge` with cosine similarity

### Retrieval Strategy

1. **Query embedding** with `RETRIEVAL_QUERY` task type
2. **Top-k search** (k=3) on Pinecone
3. **Dynamic context expansion**: If a child chunk scores < 0.75 confidence, its parent chunk is fetched for fuller context
4. **Screen-aware queries**: Current UI screen is prepended to RAG queries for contextual relevance

---

## 🔒 Privacy & Security

- **PII Masking**: All user input is processed through `pii_masker.py` before reaching the LLM
  - Indian phone numbers (`+91 XXXXXXXXXX`)
  - Aadhaar numbers (`XXXX XXXX XXXX`)
  - PAN card numbers (`ABCDE1234F`)
- **No PII storage**: Conversation logs are in-memory only, capped at 50 messages
- **Local processing**: All masking happens server-side before any external API call

---

## 📡 API Reference

### Tool Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tools/rag` | RAG search with screen context |
| `POST` | `/tools/fd_maturity` | FD maturity calculation |
| `POST` | `/tools/fd_recommendation` | FD recommendation engine |
| `POST` | `/tools/income_tax` | Income tax comparison |
| `POST` | `/tools/tds` | TDS calculation |
| `POST` | `/tools/explain_term` | Term explanation (RAG-grounded) |
| `POST` | `/tools/update_profile` | Update user state |

### State Management Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/state/get` | Get full app state (user, screen, RAG, conversation) |
| `POST` | `/state/screen` | Update current journey screen |
| `POST` | `/state/transcript` | Push voice transcript message |
| `POST` | `/state/clear-transcript` | Clear conversation log |
| `GET` | `/health` | Health check |

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Voice LLM** | Gemini 3.1 Flash Live Preview (real-time speech-to-speech) |
| **Text LLM** | Gemini 2.5 Flash (tool responses, term explanations) |
| **Embeddings** | Gemini Embedding 2 (768-dim) |
| **Voice Framework** | Pipecat (WebRTC transport) |
| **Vector DB** | Pinecone (Serverless, us-east-1) |
| **Backend** | FastAPI + LangChain Tools |
| **Frontend** | Next.js 15 + TypeScript + Tailwind CSS |
| **State** | LangGraph-style TypedDict schemas |
| **PII Protection** | Regex-based masking (Aadhaar, PAN, Phone) |

---

## 📜 License

This project was built for the **Blostem Hackathon**.

---

<p align="center">
  Built with ❤️ for making financial services accessible to every Indian — in their own language.
</p>
