---
name: live-verification
description: Verify a change against real providers and the real database with a small, announced number of calls.
---

# Live verification

1. Estimate the calls (chat ~3-5 per question; embeddings 1 per question + 1 per 64 new chunks) and tell the user.
2. Check `.env` has real values (never print them) and the target port is free.
3. Use `backend/scripts/live_check.py` (4 questions) or targeted calls; show transcripts, including failures.
4. Record what was verified live in the docs status labels; anything not run stays "not verified".
