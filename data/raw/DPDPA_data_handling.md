# DPDPA & Data Handling for Fintech Projects
**Builder-Pack Reference.**

The Digital Personal Data Protection Act, 2023 is now the operative privacy law in India. Even at hackathon stage, your project should *demonstrate* DPDPA-aware design — judges and partner-banks notice this.

---

## 1. Core obligations under DPDPA

- **Consent must be free, specific, informed, unconditional, and unambiguous,** with a clear affirmative action.
- **Notice in plain language**, in any of the 22 official languages the user can choose. Must list: purpose, categories of data, retention period, grievance officer.
- **Purpose limitation:** Personal data may only be used for the purpose disclosed at collection.
- **Storage limitation:** Delete personal data when the purpose is served, unless retention is required by law (e.g., PMLA's 5-year rule).
- **Right to correction, erasure, grievance redressal, nominee** — must be exposed in your UX.
- **Children's data:** Verifiable parental consent for users < 18; no behavioural tracking or targeted advertising directed at children.
- **Significant Data Fiduciaries (SDFs):** Higher obligations including DPIA and independent data auditor — most fintechs handling KYC/financial data will likely be classified as SDFs.

## 2. What this means for your synthetic data + your build

- For the hackathon, **never use real PII**. If you accidentally have real customer data on your laptop, scrub it before demo day.
- Synthetic data is your friend: the users_master.csv in this pack is fully synthetic.
- If your demo shows masking/redaction features, demonstrate it on the synthetic data — *do not* paste real screenshots of real customer support tickets.
- Build a "Data minimisation" toggle into your UX: collect only the fields the current step actually needs. Judges flag projects that over-collect.

## 3. PII handling patterns (recommended for your build)

- **Tokenise / hash PAN, Aadhaar, account numbers** at rest. Show only last-4 in UI.
- **Aadhaar masking is mandatory** anywhere it's displayed — show only last 4 digits, never the full 12.
- **Phone & email** — show partially masked (e.g., +91-XXXXX-X1234, j****@gmail.com).
- **Free-text inputs** (customer support tickets, chat messages) — run a PII redaction pipeline before sending to LLMs. Common entities: name, phone, email, PAN, account number, IFSC, address, DOB, Aadhaar, UPI VPA, card numbers.
- **Logging:** never log full PII in app logs / error messages. Sentry/CloudWatch should redact.
- **LLM provider boundary:** if you're sending data to an LLM API, treat the API as a third-party data fiduciary — disclose in your privacy notice.

## 4. Cross-border data transfer

- DPDPA permits cross-border transfer except to countries the government explicitly notifies as restricted (a "negative list" model). For sensitive financial data, partner-banks usually contractually require **data residency in India** regardless.
- If you're using OpenAI / Anthropic / Gemini in your demo, explicitly note that LLM calls may leave India for processing — this is a real concern for partner-banks evaluating your project.

## 5. Useful citations

- Digital Personal Data Protection Act, 2023 · https://meity.gov.in
- Draft DPDP Rules, 2025 (consultation) · https://meity.gov.in
- RBI circular on storage of payment system data (2018) — payment data must be stored in India · https://rbi.org.in

---

*Last updated: builder-pack v0.1 (May 7, 2026).*
