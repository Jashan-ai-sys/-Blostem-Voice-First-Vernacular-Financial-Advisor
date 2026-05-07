# SEBI — Mutual Funds, AIFs, SIFs, SIPs
**Builder-Pack Reference. Cross-check the SEBI Master Circulars before shipping.**

---

## 1. Mutual Funds (SEBI MF Regulations, 1996, as amended)

### Categories
- **Equity:** Large-cap, large- & mid-cap, mid-cap, small-cap, multi-cap, flexi-cap, ELSS, sectoral/thematic, dividend-yield, value/contra, focused.
- **Debt:** Liquid, ultra-short, low-duration, money-market, short, medium, long-duration, gilt, corporate-bond, credit-risk, banking & PSU, dynamic-bond, floater, overnight.
- **Hybrid:** Conservative, balanced, aggressive, dynamic-asset-allocation, multi-asset, arbitrage, equity-savings.
- **Solution-oriented:** Retirement, children's fund (5-year lock-in or until majority).
- **Other:** Index funds, ETFs, FoF (domestic/international).

### Key disclosure & compliance
- **Riskometer:** 6-level scale; updated monthly. Must be displayed wherever the scheme is sold.
- **Total Expense Ratio (TER) caps:** Equity 2.25% (slab-based by AUM), Debt 2.00%, Index/ETF 1.00%, FoF 2.25%. Direct plan TER is lower than Regular by the distribution-trail commission (typically 0.5–1.0% lower).
- **Direct vs Regular plans:** Mandatory since 2013. Builders that help customers switch from Regular → Direct must clearly disclose exit-load and tax implications of the switch.
- **Cut-off times:** Equity/hybrid 3:00 PM, Debt 1:30 PM (₹2L+), Liquid 1:30 PM. Same-day NAV applies only if funds are realised by cut-off.
- **NAV disclosure:** End-of-day, by 11:00 PM (liquid 9:00 AM next day).

### KYC for MFs
- **CKYC + PAN-Aadhaar linked** is mandatory. Re-KYC required if last KYC > 7 years and there are new attributes.
- **eKYC:** OTP-based eKYC permitted up to ₹50,000/year per scheme; full biometric/VKYC needed for higher.
- **In-Person Verification (IPV):** Required for first-time MF investors; can be online (VKYC) or offline.

### Taxation (FY 25-26 framework)
- **Equity-oriented (≥65% in equity):** STCG (≤12 months) 20%, LTCG (>12 months) 12.5% above ₹1.25L exemption per FY. *(Rates per Finance Act 2024.)*
- **Debt funds (post Apr 2023):** All gains taxed at slab rate, regardless of holding period. Indexation benefit removed.
- **ELSS:** 3-year statutory lock-in; LTCG taxation applies thereafter.
- **Dividend (IDCW):** Taxed at slab rate; TDS u/s 194K @ 10% if dividend > ₹5,000/FY.

## 2. SIPs (Systematic Investment Plans)

- **Minimum SIP amount:** AMC-defined; industry-typical ₹100/month (some funds), ₹500/month (most), ₹1,000/month (others). SEBI itself does not set a floor.
- **Frequency:** Daily, weekly, monthly, quarterly. Most platforms offer monthly + weekly.
- **Mandates:** UPI AutoPay, e-NACH/eMandate, Bharat Bill Pay (BBPS). Mandate signing happens once; SIP debits run thereafter.
- **Pause/Stop:** Investors can pause SIPs (typically up to 3–6 months) or stop with 30 days' notice. Build this into your UX — many builders forget the cancel-mandate flow.
- **Step-up SIP:** Annual % or absolute increase; SEBI permits but AMC must support.

## 3. AIFs (Alternative Investment Funds, SEBI AIF Regulations 2012)

- **Three categories:**
  - **Category I:** Socially/economically beneficial — Venture Capital Funds, Angel Funds, SME Funds, Social Impact Funds, Infrastructure Funds.
  - **Category II:** Funds that don't fit I or III, take no leverage other than for operational purposes — Private Equity, Debt Funds, Real Estate Funds.
  - **Category III:** Use complex/diverse strategies; may employ leverage — Hedge Funds, PIPE Funds, Long-Short Funds.
- **Minimum investment:** **₹1 crore per investor** (₹25 lakh for managers/employees of the AIF, on certain conditions).
- **Investor count:** Max 1,000 investors per scheme (Cat I/II); Angel Funds capped at 200 angels per scheme.
- **Lock-in:** Cat I/II minimum 3 years; Cat III is open- or close-ended.
- **Accredited Investor framework** introduced via SEBI 2021 amendments — net-worth + income thresholds; lowers minimum-investment requirement for accredited individuals.

## 4. SIF (Specialised Investment Fund) — newer SEBI category

- Introduced by SEBI in **2024** to fill the gap between Mutual Funds (₹500 minimum) and PMS/AIF (₹50L / ₹1 crore minimums).
- **Minimum investment:** **₹10 lakh per investor** (across schemes of the same SIF).
- **Eligible offerers:** AMCs that meet SEBI's track-record / AUM criteria; existing MF AMCs may extend into SIFs subject to additional approvals.
- **Investment strategies allowed:**
  - Long-short equity (long bias, with capped short exposure).
  - Sector rotation.
  - Equity ex-top-100 (high-conviction, ≥ 65% in stocks beyond Nifty 100).
  - Debt long-short.
  - Hybrid long-short.
- **Disclosure:** SEBI has prescribed product-level disclosures including a separate riskometer, exposure limits, and performance benchmarks.
- **Tax treatment:** Pass-through depends on fund constitution; verify with the scheme's SID.

For a builder: SIFs are interesting because they're a *retail-accessible* alpha-seeking product. If your project pitches "professional strategies for ₹10L+ retail investors," SIF positioning is the right framing.

## 5. PMS (Portfolio Management Services) — for completeness

- **Minimum investment:** **₹50 lakh** (raised from ₹25L in 2020).
- Discretionary, non-discretionary, or advisory. SEBI-registered Portfolio Manager required.
- Higher disclosure burden than MFs; performance reported to client + SEBI.

## 6. Disclosure boilerplate every product MUST show

- **Mutual Fund:** "Mutual fund investments are subject to market risks. Read all scheme-related documents carefully."
- **AIF/SIF/PMS:** Risk disclosure + acknowledgment that the product is for sophisticated/qualified investors. Suitability gate (income, net worth, investment horizon) before checkout.
- **Past performance** must always be accompanied by "Past performance is not indicative of future returns."
- **Direct plan disclosure** (MF) must be present whenever Regular plan is the default.

## 7. Citations

- SEBI MF Regulations 1996 · https://www.sebi.gov.in
- SEBI Master Circular on Mutual Funds (latest) · https://www.sebi.gov.in
- AIF Regulations 2012 · https://www.sebi.gov.in
- SEBI consultation paper / regulations on Specialised Investment Funds (2024) · https://www.sebi.gov.in
- Income-tax Act provisions for capital gains: Sections 111A, 112A, 112 · https://incometaxindia.gov.in
- AMFI · https://www.amfiindia.com (categorisation circular, riskometer, monthly factsheets)

---

*Last updated: builder-pack v0.1 (May 7, 2026). MF tax rules changed in Finance Act 2024 — re-verify before customer-facing copy.*
