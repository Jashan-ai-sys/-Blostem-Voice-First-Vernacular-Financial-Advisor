# KYC / VKYC / CKYC — Regulatory Norms
**Builder-Pack Reference.**

---

## 1. The framework

- **Master source:** RBI Master Direction — Know Your Customer (KYC) Direction, 2016 (last major update Nov 2024). PMLA 2002 + PML Rules 2005 are the parent statute.
- **CKYC:** Central KYC Records Registry (CERSAI). Once an individual completes CKYC at any RE, the record is reusable across REs via a 14-digit CKYC number. Builders should *fetch* CKYC before asking the customer to re-submit documents.
- **eKYC (Aadhaar OTP-based):** Permitted under Section 11A PMLA. UIDAI returns name, address, DOB, photograph, gender. The user must give explicit consent each time.

## 2. KYC tiers (digital onboarding)

| Tier | Method | Limit |
|------|--------|-------|
| **OTP-based eKYC** | Aadhaar + OTP, no physical verification | Aggregate balance ≤ ₹1 lakh, aggregate annual credits ≤ ₹2 lakh; can't be opened for non-residents |
| **VKYC (Video KYC)** | Live agent-led video session, OVD verification, geo-tagging, liveness, IPV | Full-KYC equivalent; no balance/credit limits beyond standard KYC |
| **Full KYC** | In-person verification (IPV) at branch or by official | No limits |

OTP-based eKYC must be **converted** to full KYC within 1 year (by VKYC or in-person), else accounts are flagged.

## 3. VKYC requirements (RBI Jan 2020 + amendments)

A VKYC session is regulator-grade only if it satisfies *all* of:

1. **Live, real-time** video — not pre-recorded.
2. **Agent of the RE** (regulated entity, e.g., partner bank) on the call — not a third-party.
3. **Liveness check:** Random questions, head-turn or blink, OTP read-out.
4. **OVD verification:** Customer shows the original (not photocopy) PAN and address proof; agent matches face on PAN/Aadhaar e-KYC photo with the live face.
5. **Geo-tagging:** Customer's geo-location captured; must be within India.
6. **End-to-end encryption + audit trail:** Session recorded, watermarked, stored for the RE's record-retention period (typically 5+ years post-relationship-closure).
7. **Random sampling for QA** by the RE's audit team.

### Common VKYC drop-off causes (from real-world customer support data)
- Poor lighting → face-mismatch from liveness model
- PAN photo blurry or laminated → reflection blocks OCR
- User on bandwidth-constrained connection → session times out
- Agent queue wait > 90 seconds → user abandons
- App permission for camera/mic denied
- Language mismatch — agent only speaks Hindi/English; user is comfortable in Tamil/Bengali only
- User not understanding consent screen → drops at the legalese step

If you're building a VKYC-related project, the *agent queue + language router + liveness UX* are the three highest-leverage points.

## 4. CKYC fetch flow (recommended UX)

1. Customer enters PAN.
2. Backend hits CERSAI: returns CKYC number if exists.
3. If CKYC exists → fetch record → pre-fill the form → ask only for confirmation + missing fields → optional re-VKYC if data is stale (>3 yrs) or partner-bank policy requires.
4. If CKYC doesn't exist → run fresh eKYC/VKYC → push the new CKYC record to CERSAI within 10 days (regulatory requirement).

Builders very often skip the CKYC pre-check, force users to re-submit everything, and lose them at the 4th screen. Pre-fill from CKYC reduces drop-off by 25–40% in published industry case studies.

## 5. Re-KYC

- **Periodicity:** Every 2 years for high-risk customers, 8 years for medium, 10 years for low — counted from last KYC update.
- **Triggers for early re-KYC:** Change in address, name, signature, beneficial-owner structure, or material change in transaction profile.
- **Self-declaration mode:** Allowed if no change — customer simply confirms via OTP / video. Saves a lot of friction.

## 6. PMLA record-keeping

- All KYC documents + transaction records: **minimum 5 years** post account-closure.
- Suspicious Transaction Reports (STR), Cash Transaction Reports (CTR): filed with FIU-IND.
- Transaction monitoring rules (sample): single cash deposit ≥ ₹10L, multiple deposits aggregating ≥ ₹10L in a month, any transaction inconsistent with stated profile, any link to listed UN/OFAC entities.

## 7. Useful citations

- RBI Master Direction — KYC, 2016 (latest amended) · https://rbi.org.in
- Prevention of Money-laundering Act, 2002 · https://www.fiuindia.gov.in
- CERSAI / CKYC · https://www.ckycindia.in
- UIDAI eKYC · https://uidai.gov.in

---

*Last updated: builder-pack v0.1 (May 7, 2026).*
