"""
AutoRAG Architect — Runtime Guardrails
=======================================
3-layer safety pipeline: Input → Retrieval → Output

All guardrail functions must be called in order via GuardrailPipeline.
Do NOT scatter individual guard calls across routes, agents, or repositories.

Layer 1 — Input: PII masking, prompt injection, jailbreak detection
Layer 2 — Retrieval: poisoning detection, source validation, vector anomaly
Layer 3 — Output: hallucination scoring, moderation, citation validation

See middleware/guardrail_pipeline.py for the integration entry point.
"""
