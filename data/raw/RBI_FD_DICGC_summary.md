# RBI / DICGC — Fixed Deposits & Deposit Insurance
**Builder-Pack Reference. Cite the originals before you ship anything user-facing.**

This is a working summary of the rules most relevant to FD products, partner-bank integrations, and customer disclosures. It is not legal advice. Always link out to the source circulars for production copy.

---

## 1. DICGC deposit insurance

- **Coverage limit:** ₹5,00,000 per depositor per insured bank (principal + interest combined).
- **Coverage scope:** Savings, current, recurring, and fixed deposits in scheduled commercial banks, RRBs, LABs, co-operative banks, and small finance banks. Foreign branches of Indian banks are excluded; foreign-bank branches in India are covered.
- **Claim trigger:** Cancellation of bank licence or amalgamation/scheme of arrangement. The DICGC Amendment Act 2021 introduced **interim payouts within 90 days** when a bank is placed under all-inclusive directions (AID) by RBI.
- **Per-depositor aggregation:** Multiple deposits in different branches of the *same* bank aggregate; deposits in *different* banks each get a separate ₹5L cover.
- **What's NOT covered:** Inter-bank deposits, deposits of foreign governments, central/state government deposits, deposits in branches outside India.
- **Customer-facing copy must say:** "Deposits are insured by DICGC up to ₹5,00,000 (principal + interest) per depositor per bank."
- Source: DICGC Act 1961 (as amended 2021) · https://www.dicgc.org.in

## 2. RBI Master Direction — Acceptance of Deposits (commercial banks)

- **Minimum tenor:** 7 days (term deposits below 7 days are not permitted).
- **Premature withdrawal:** Banks must allow it for individuals/HUFs (penalty rate at the bank's discretion, typically 0.5–1% below the booked rate). For deposits ≥ ₹1 crore, banks may offer non-callable variants where premature withdrawal is contractually disallowed — disclosure on booking screen is mandatory.
- **Senior citizen rates:** Banks may offer differential rates (typically +25–75 bps) for residents aged 60+. Eligibility verification at booking is mandatory.
- **Sweep / auto-FD:** Permitted; banks must disclose break terms and minimum sweep amount.
- **Renewal:** Auto-renewal is permitted only with prior written/digital consent. Default behaviour after maturity if no instruction: credit to linked SB account at savings rate.

## 3. TDS on FD interest (Section 194A, Income-tax Act)

- **Threshold:** TDS is deducted if aggregate FD interest from a bank exceeds ₹40,000 in a financial year (₹50,000 for senior citizens). Threshold is ₹50,000 for co-operative society payers.
- **Rate:** 10% with PAN. **20% if PAN not furnished.**
- **Form 15G/15H:** Customers below taxable income can submit 15G (under 60) / 15H (60+) to avoid TDS. Your product should let users upload these per-bank, per-FY.
- **TDS certificate:** Form 16A, downloadable per quarter. Builders should integrate with TRACES or fetch from partner-bank portals.
- **Cumulative interest pitfall:** Even if interest is *credited at maturity* (cumulative FDs), TDS is deducted *annually* on the accrued amount.

## 4. Partner-bank integration (digital FD products)

- Most digital-FD platforms operate under the **co-lending or sourcing arrangement** with a bank/SFB partner — the deposit sits on the partner-bank's books, not the platform's.
- **Customer disclosure requirement (RBI):** The partner-bank's name, IFSC, and DICGC coverage must be visible on the FD review and confirmation screens before booking.
- **KFS (Key Fact Statement)**: For digital-lending product disclosures the KFS framework is mandatory; for FDs an equivalent rate-card disclosure including premature-withdrawal penalty, TDS, nomination status, and DICGC coverage is the de-facto industry standard.
- **Rate parity:** Partner-banks typically require platforms to display rates without markup. Display all-in-yield (post-TDS) only as an *additional* projection, never as the headline rate.

## 5. Nomination

- Nomination is permitted under Section 45ZA of the Banking Regulation Act. RBI strongly encourages enabling nomination at booking.
- Single nominee per FD by default; some partner-banks allow up to 3 successive nominees with percentage allocation. Capture nominee name, relationship, DOB, and address.

## 6. Premature closure mechanics

- **Penalty:** Booked rate minus the rate that would have applied for the *actual* tenor served, minus the bank-specified penalty (0.5–1% typical). Some banks waive the penalty for amounts < ₹1L or for senior citizens.
- **Calculation example:** ₹1,00,000 booked at 7.5% for 1 year, broken at month 6 — applicable rate = 6-month rate (say 6.5%) − 0.5% penalty = 6.0% on the actual 6-month period.
- **Settlement timing:** RBI expects settlement to the source account within T+2 working days; partner-bank SLAs may differ.

## 7. Customer-protection rules to bake into your UX

- All rate disclosures must be **annualised, before TDS**, and shown alongside maturity date and maturity amount.
- Show the partner-bank name on every FD-related screen, not just at booking.
- One-click access to grievance redressal: bank's nodal officer → Banking Ombudsman (RB-IOS 2021, link below).
- For non-callable FDs, the "premature withdrawal not allowed" warning must be a separate consent step, not a checkbox in a wall of text.
- Source: RBI Integrated Ombudsman Scheme · https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=52549

## 8. Useful citations to link from your app/UI

- DICGC Act, 1961 · https://www.dicgc.org.in
- RBI Master Direction — Interest Rate on Deposits (latest amended) · https://rbi.org.in (search: Master Direction Interest Rate on Deposits)
- Income Tax Act Section 194A · https://incometaxindia.gov.in
- Banking Regulation Act 1949 (nomination) · https://rbi.org.in
- Banking Ombudsman / RB-IOS 2021 · https://rbi.org.in

---

*Last updated: builder-pack v0.1 (May 7, 2026). Cross-check the latest circulars before launch — RBI tweaks rate-direction master circulars annually.*
