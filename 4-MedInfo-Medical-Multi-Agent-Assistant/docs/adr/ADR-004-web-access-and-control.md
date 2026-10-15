# ADR-004 - Web access and control

**Status:** Accepted (2026-10-14)

## Context
Web content is valuable for research but is untrusted, may be outdated, may carry prompt injection, and may
come from low-quality sites.

## Decision
- Web search only in **research mode** (clinician and admin), through **Tavily**.
- **Allow-list** of medical domains (`WEB_ALLOWED_DOMAINS`: who.int, nice.org.uk, cdc.gov, nih.gov,
  ncbi.nlm.nih.gov, medlineplus.gov, nhs.uk, fda.gov, ema.europa.eu, cochranelibrary.com), passed to the
  provider **and re-checked locally** (exact host or subdomain; look-alike hosts are rejected).
- Web results are **untrusted**: injection lines are neutralised, results are labelled "UNTRUSTED web" in
  the prompt, cited by URL, and subject to every post-answer check.
- Only the redacted question is sent to the search provider; research has its own per-user rate limit.

## Alternatives considered
- Open web search: rejected (quality and injection risk).
- No web access: rejected (the research use case needs it).
- Scraping full pages: rejected (larger attack surface; snippets are enough for citation).

## Consequences
Narrower but defensible evidence. **Allow-list enforcement is unit-tested; the live Tavily integration has
not been exercised yet.**
