# Error Contract (RFC 9457) — for actionable, voice-explainable errors

So the voice/chat assistant can tell a user **what happened** and **what to do**, every error API response should be **structured and stable**. This follows the industry standard:

- **RFC 9457** — *Problem Details for HTTP APIs* (obsoletes RFC 7807): the IETF standard for machine-readable error bodies.
- **Stripe error model** — the fintech reference: a stable machine `code` separate from a human `message`.
- **Google AIP-193** — standardized, enumerated error `reason`s.

## The shape

Return a JSON body with `Content-Type: application/problem+json` and the right HTTP status:

```json
{
  "type": "https://errors.blostem.app/payment-declined",
  "title": "Payment declined",
  "status": 402,
  "detail": "Your bank declined the payment.",
  "code": "PAYMENT_DECLINED",
  "reason": "issuer_declined",
  "user_message": "Aapke bank ne payment decline kiya.",
  "suggested_action": "Doosra bank ya UPI app try karein. Koi charge nahi laga."
}
```

| Field | Source | Purpose | Required |
|---|---|---|---|
| `status` | HTTP status | coarse class (fallback if no `code`) | ✅ (it's the HTTP code) |
| `code` | **stable enum** | the IDENTIFIER the assistant maps to a remedy | ✅ strongly |
| `reason` | enum | finer cause (Google AIP-193 style) | ◻ recommended |
| `title` / `detail` | RFC 9457 | machine/dev-facing | ✅ (`title`) |
| `user_message` | you | safe, user-facing "what happened" | ◻ recommended |
| `suggested_action` | you | "what to do" (the actionable bit) | ◻ recommended |

## Rules that make errors actionable

1. **`code` must be a STABLE, enumerated string** (e.g. `INVALID_PAN`, `SESSION_EXPIRED`, `PAYMENT_DECLINED`). The assistant's remedy mapping ([data/error_taxonomy.json](../data/error_taxonomy.json)) keys off it. Never reuse a code for a different meaning.
2. **Separate machine `code` from human `message`** — never make the assistant parse free text to guess the cause.
3. **Never leak PII or internals** in `detail`/`user_message` (no stack traces, no PAN/account numbers). The client also masks, but don't rely on it.
4. **Use the right HTTP status** — it's the fallback class when `code` is missing (`401`→session, `402`→payment, `422`→validation, `5xx`→server…). A bare `500` with no `code` can only get *generic* help.
5. **One code per failure mode.** If a screen can fail three ways, that's three codes.

## How it flows into the assistant

```
API error (code + status + message)
   └─► client captures it (API interceptor / SDK reportError / role="alert")
        └─► POST /state/error
             └─► app/error_service.classify():  code → status → keyword → unknown
                  └─► {error_class, reason, user_message, suggested_action}
                       └─► voice bot: "Yeh hua… aur aap yeh karein…" (actionable, grounded)
```

- **Recognized `code`** → specific, actionable answer.
- **Unknown `code` / opaque `5xx`** → honest *class-level* remedy ("temporary issue, nothing charged, retry"). The assistant **never fabricates** a specific cause.

## The canonical code set (extend as needed)

Mirror the codes the assistant already maps (see `data/error_taxonomy.json` → `codes`):

`SESSION_EXPIRED`, `INVALID_PAN`, `INVALID_AADHAAR`, `KYC_FAILED`, `DETAILS_MISMATCH`,
`PAYMENT_FAILED`, `PAYMENT_DECLINED`, `INSUFFICIENT_FUNDS`, `NETBANKING_UNAVAILABLE`,
`BANK_CONNECTION_ERROR`, `AGENT_NOT_AVAILABLE`, `DUPLICATE_NOMINEE`, `BANK_ALREADY_ADDED`,
`REQUEST_NOT_PROCEEDED`, `SERVICE_UNAVAILABLE`.

**To add a new error:** pick a stable `code`, choose its `class` (network/session/validation/payment/server/permission/…), add an entry to `data/error_taxonomy.json` → `codes` with a `reason` and (optionally) a code-specific `suggested_action`. No code change needed — the classifier picks it up.

## Bottom line for the backend team
Return **`application/problem+json`** with a **stable `code`** + correct **HTTP status**, and ideally `reason` / `user_message` / `suggested_action`. That single contract is what lets the assistant give precise, actionable, voice-friendly help instead of "please verify with the bank."
