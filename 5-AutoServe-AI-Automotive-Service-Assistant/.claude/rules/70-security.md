# 70 — Security

**Purpose:** Protect owner PII, isolate dealers, and resist prompt injection and upload abuse.

## MUST
- **AuthN:** DEMO JWT HS256 (local only, TTL ≤ 60 min, `iss`/`aud` checked, alg pinned). Prod uses OIDC RS256 via JWKS. Reject `alg=none`.
- **AuthZ:** `require_role()` on every route **and** an actor-scoped repository. Out-of-scope → 404.
- **Dealer isolation:** every staff query filters by `actor.dealer_id`. Cross-dealer tests exist for every staff route.
- **PII:** `mask_pii()` structlog processor masks name, phone, email, address, plate, and VIN (→ `***` + last 6). Location is coarse or absent in logs.
- **Uploads:** allow-list PDF/JPG/PNG; check magic bytes; ≤ 10 MB; ≤ 20 pages; strip metadata; re-encode images (Pillow);
  random storage key `ro/{ro_id}/{uuid}.{ext}`; SSE; record sha256; run the DEMO AV-scan hook before processing.
- **Prompt injection:** wrap untrusted text in `<untrusted_document>` / `<untrusted_user_input>` in the **user** turn.
  Extractors get no tools. Schema-validate the output. Instruction-like content → `risk_flag prompt_injection_suspected` (D-09).
- **Rate limiting** on login, chat, and upload (config). Uniform login error messages.
- **Secrets** from env / Secrets Manager. `.env` stays git-ignored and agents never read it.
- **Headers:** CORS allow-list, HSTS (prod), CSP for the frontend, `X-Content-Type-Options: nosniff`.
- CI runs bandit, pip-audit, and npm audit; High/Critical findings block merge.

## MUST NOT
- Put uploaded text, or text from a DB field a user can write to, into the system prompt.
- Log tokens, passwords, API keys, full VINs, or raw document text.
- Trust client-sent `role`, `dealer_id`, `owner_id`, or amounts.
- Serve uploaded files from a public bucket or by predictable URL. Use short-lived presigned URLs after an authZ check.

## Good
```python
messages = [SystemMessage(EXTRACTOR_SYSTEM_V1),
            HumanMessage(f"<untrusted_document>\n{page_text}\n</untrusted_document>\nExtract per schema.")]
result = await llm.structured(messages, schema=InvoiceExtraction, tools=None)
```

## Bad
```python
SystemMessage(f"You are an extractor. Document: {page_text}")   # injection lands in the system prompt
logger.info("checked in", vin=vin, phone=owner.phone)            # raw PII in logs
```
