# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

---

name: review-security
description: Perform a security review on a file, endpoint, or feature

---

# Review Security Skill

## Goal

Perform a focused security review and identify vulnerabilities or compliance gaps.

## Steps

1. Ask for: target file/feature/endpoint to review, and context (public-facing, handles PII, auth-related, etc.).
2. Review for OWASP Top 10 vulnerabilities:
   - Injection (SQL, command, template)
   - Broken authentication/authorization
   - Sensitive data exposure
   - XSS (if frontend)
   - Insecure deserialization
   - Security misconfiguration
3. Review for platform-specific concerns:
   - PII in logs or AI training data
   - Missing rate limiting on public endpoints
   - Missing RBAC checks
   - Hardcoded credentials or secrets
   - Unsafe file upload handling
   - Missing webhook signature validation
   - Unmasked sensitive data in API responses
4. Review for compliance:
   - GDPR data handling (right to deletion, data export)
   - Audit logging for privileged operations
   - Data retention policy compliance
5. Report findings with severity (critical/high/medium/low) and recommended fixes.
6. Implement fixes for critical and high severity issues.

## Quality rules

- Check every input path — form data, query params, headers, file uploads, webhook payloads.
- Verify auth and RBAC on every endpoint.
- Confirm PII is masked in logs and analytics.
- Verify secrets are in config/secrets manager, not in code.
- Flag any change that impacts auth, payments, or PII.
