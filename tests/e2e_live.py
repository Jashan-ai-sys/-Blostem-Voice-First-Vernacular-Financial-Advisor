"""
End-to-end smoke test against a LIVE backend (uvicorn on :8000).
Drives the real HTTP API the way the frontend + voice agent do.

Run:  (term 1)  .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
      (term 2)  .venv/Scripts/python.exe tests/e2e_live.py
"""

import os
import sys

import httpx

BASE = os.getenv("BLOSTEM_BACKEND_URL", "http://localhost:8000")
A = {"X-Session-Id": "e2e-userA"}
B = {"X-Session-Id": "e2e-userB"}

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


c = httpx.Client(base_url=BASE, timeout=120)

# 1. health
r = c.get("/health").json()
check("health", r.get("status") == "healthy", r)

# 2. voice handshake
c.post("/session/voice-pending", json={"session_id": "e2e-userA"})
claim = c.post("/session/voice-claim").json()
check("voice handshake claims session", claim.get("session_id") == "e2e-userA", claim)

# 3. screen sync (journey step -> KYC)
r = c.post("/state/screen", json={"step": 2, "mode": "journey"}, headers=A).json()
check("screen sync (int step)", "KYC" in r.get("current_screen", ""), r)

# 4. FD maturity calculator
r = c.post("/tools/fd_maturity", json={"principal": 100000, "annual_rate_percent": 7.5,
                                       "tenure_years": 5, "compounding_frequency": "quarterly"}).json()
check("fd_maturity computes", r.get("maturity_amount", 0) > 100000 and r.get("interest_earned", 0) > 0, r)

# 5. income tax — real FY25-26 slabs (deterministic, no API)
r = c.post("/tools/income_tax", json={"total_income": 1600000, "age": 35, "regime": "new"}).json()
check("income_tax new-regime 16L = 124800", r.get("total_tax_liability") == 124800.0, r)

# 6. TDS — corrected FY25-26 senior threshold (₹1L)
r = c.post("/tools/tds", json={"age": 65, "fd_interest": 80000, "pan_available": True}).json()
check("tds senior 80k = no TDS", r.get("threshold_hit") is False, r)

# 7. FD recommendation engine
r = c.post("/tools/fd_recommendation", json={"goal_type": "tax_saving", "liquidity_need": "high",
                                             "senior_citizen": True}).json()
check("fd_recommendation returns options", len(r.get("top_recommendations", [])) > 0, r)

# 8. profile update -> state changes (session A)
c.post("/tools/update_profile", json={"new_age": 70}, headers=A)
st = c.get("/state/get", headers=A).json()
check("profile update age=70 senior", st["user_state"]["age"] == 70 and st["user_state"]["senior_citizen"], st["user_state"])

# 9. self-serve PDF upload -> chat-ready
with open("data/FN-121.pdf", "rb") as f:
    r = c.post("/ingest/upload", files={"file": ("FN-121.pdf", f, "application/pdf")}).json()
check("PDF upload ingested + bm25 ready", r.get("chunks_added", 0) > 0 and r.get("bm25_ready"), r)

# 10. RAG tool retrieves real content (BM25, no API needed)
r = c.post("/tools/rag", json={"query": "DICGC deposit insurance cover"}, headers=A).json()
check("rag returns KB content", "No specific rules found" not in r.get("results", ""), r.get("results", "")[:80])

# 11. /chat — guardrailed + grounded + citations (generation may be quota-limited)
r = c.post("/chat", json={"query": "What are Form 15G and 15H used for?", "language": "English"}, headers=A).json()
check("chat returns grounded + citations", r.get("grounded") is True and isinstance(r.get("citations"), list) and len(r["citations"]) > 0, r)

# 12. PII masking on the stored conversation
c.post("/chat", json={"query": "my PAN is ABCDE1234F please note", "language": "English"}, headers=A)
conv = c.get("/state/get", headers=A).json()["conversation"]
joined = " ".join(m["text"] for m in conv)
check("PII masked in stored conversation", "ABCDE1234F" not in joined and "[MASKED_PAN]" in joined)

# 13. session isolation — B unaffected by A's profile/transcript
stB = c.get("/state/get", headers=B).json()
check("session isolation (B default age, no A leak)", stB["user_state"]["age"] == 65 and "ABCDE1234F" not in str(stB), stB["user_state"])

print(f"\n{passed} passed, {failed} failed")
c.close()
sys.exit(1 if failed else 0)
