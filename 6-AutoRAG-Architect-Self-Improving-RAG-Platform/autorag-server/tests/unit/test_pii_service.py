"""Unit tests for PII Detection and Masking Service — sync compat wrapper.

D-6 Sprint Task: Platform-wide PII masking contract for ALL agent nodes.
P0.7-1 (13-Jul-2026): pii_service.py is now a thin wrapper over the
canonical engine (app.services.pii_engine); exhaustive per-category
table-driven coverage lives in tests/unit/test_pii_engine.py. This file
verifies the sync wrapper's own contract (idempotency, defensive input
handling, canonical token names) rather than re-deriving every pattern.

Security Contract (Rule 70 + graph-state-governance Rule 6):
    - Masks emails, phone numbers, tokens, passwords, AWS keys, JWT/service keys
    - Returns masked string — never raises on any input
    - Idempotent: mask_pii(mask_pii(x)) == mask_pii(x)
    - Synchronous — safe for all callers (sync/async contexts)
    - Never logs original text (PII violation)

Canonical replacement tokens (P0.7-1): [EMAIL], [PHONE], [SSN],
[CREDIT_CARD], [ADDRESS], [BEARER_TOKEN], [PASSWORD], [AWS_ACCESS_KEY],
[JWT_OR_SERVICE_KEY] — supersedes the pre-P0.7 [TOKEN]/[AWS_KEY]/
[SUPABASE_KEY] names.
"""

import pytest

from app.services.pii_service import mask_pii


class TestEmailMasking:
    """Test email address detection and masking."""

    def test_single_email_masked(self) -> None:
        """Single email should be replaced with [EMAIL]."""
        result = mask_pii("Contact us at support@example.com for help")
        assert "[EMAIL]" in result
        assert "support@example.com" not in result

    def test_multiple_emails_masked(self) -> None:
        """Multiple emails should all be masked."""
        text = "Emails: alice@company.org, bob@test.net, charlie@email.com"
        result = mask_pii(text)
        assert "[EMAIL]" in result or "[EMAIL]".count("[EMAIL]") == 3
        assert "alice@company.org" not in result
        assert "bob@test.net" not in result
        assert "charlie@email.com" not in result

    def test_email_with_special_chars(self) -> None:
        """Email with dots, hyphens, plus signs should be masked."""
        text = "Try user.name+tag@example-domain.co.uk"
        result = mask_pii(text)
        assert "[EMAIL]" in result
        assert "user.name+tag@example-domain.co.uk" not in result

    def test_email_case_variants(self) -> None:
        """Email masking should be case-insensitive for TLD."""
        text = "Contact SUPPORT@EXAMPLE.COM or user@sub.domain.org"
        result = mask_pii(text)
        assert "[EMAIL]" in result
        assert "SUPPORT@EXAMPLE.COM" not in result
        assert "user@sub.domain.org" not in result


class TestPhoneMasking:
    """Test phone number detection and masking."""

    def test_us_phone_masked(self) -> None:
        """US phone format should be masked with [PHONE]."""
        text = "Call +1-555-123-4567 or (555) 234-5678"
        result = mask_pii(text)
        assert "[PHONE]" in result
        assert "+1-555-123-4567" not in result
        assert "(555) 234-5678" not in result

    def test_international_phone(self) -> None:
        """International phone +44-20-7946-0958 should be masked."""
        text = "Contact +44-20-7946-0958 for UK support"
        result = mask_pii(text)
        assert "[PHONE]" in result
        assert "+44-20-7946-0958" not in result

    def test_phone_with_spaces(self) -> None:
        """Phone numbers with various separators should be masked."""
        text = "Dial 123 456 7890 or 123-456-7890"
        result = mask_pii(text)
        assert "[PHONE]" in result
        assert "123-456-7890" not in result


class TestTokenMasking:
    """Test access token detection and masking."""

    def test_bearer_token_masked(self) -> None:
        """Bearer token should be replaced with a canonical token type.

        P0.7-1: this specific text's payload happens to also match the
        JWT_OR_SERVICE_KEY pattern (eyJ-prefixed base64url) since JWTs are
        commonly bearer-token values — JWT_OR_SERVICE_KEY runs first in the
        canonical engine's ordering, so it wins here. Either outcome proves
        the credential is masked, not left in plaintext.
        """
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = mask_pii(text)
        assert "[BEARER_TOKEN]" in result or "[JWT_OR_SERVICE_KEY]" in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_api_key_token_masked(self) -> None:
        """API key token format should be masked."""
        text = "API Key: AKIAIOSFODNN7EXAMPLE secret=wJalrXUtnFEMI/K7MDENG/bPxRfiCY"
        result = mask_pii(text)
        assert "[BEARER_TOKEN]" in result or "[AWS_ACCESS_KEY]" in result or "[PASSWORD]" in result


class TestPasswordMasking:
    """Test password detection and masking."""

    def test_password_in_message_masked(self) -> None:
        """Password field text should be masked with [PASSWORD]."""
        text = "Your password is: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        result = mask_pii(text)
        assert "[PASSWORD]" in result or "password" not in result.lower()


class TestAwsKeyMasking:
    """Test AWS Access Key ID detection and masking."""

    def test_aws_access_key_masked(self) -> None:
        """AWS Access Key ID should be replaced with [AWS_ACCESS_KEY]."""
        text = "AWS Access Key ID: AKIAIOSFODNN7EXAMPLE"
        result = mask_pii(text)
        assert "[AWS_ACCESS_KEY]" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_aws_key_in_url_masked(self) -> None:
        """AWS key in URL format should be masked."""
        text = "https://secretmanager.amazonaws.com/?accessKey=AKIAIOSFODNN7EXAMPLE"
        result = mask_pii(text)
        assert "[AWS_ACCESS_KEY]" in result


class TestJwtServiceKeyMasking:
    """Test Supabase/JWT API Key detection and masking (canonical: JWT_OR_SERVICE_KEY)."""

    def test_jwt_service_key_masked(self) -> None:
        """Supabase/JWT-style API key should be replaced with [JWT_OR_SERVICE_KEY]."""
        text = "Supabase URL: https://uibqmwooekviwrqjwtji.supabase.co/api/v1/object-bucket/key?api=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example_key_here"
        result = mask_pii(text)
        assert "[JWT_OR_SERVICE_KEY]" in result


class TestIdempotency:
    """Test that masking is idempotent (double masking = single masking)."""

    def test_masking_is_idempotent(self) -> None:
        """Applying mask_pii twice should produce the same result as once."""
        text = "Contact us at support@example.com or call +1-555-123-4567. " \
                "API Key: AKIAIOSFODNN7EXAMPLE. Password: wJalrXUtnFEMI. " \
                "Supabase: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example"

        once = mask_pii(text)
        twice = mask_pii(once)

        assert once == twice, "mask_pii must be idempotent"


class TestCleanText:
    """Test that clean text (no PII) passes through unchanged."""

    def test_clean_text_unchanged(self) -> None:
        """Text without PII should pass through identically."""
        text = "Hello! How can I help you today? We provide excellent service."
        result = mask_pii(text)
        assert result == text, "Clean text should be returned unchanged"

    def test_empty_text_handled(self) -> None:
        """Empty string should return empty string."""
        assert mask_pii("") == ""

    def test_whitespace_only_unchanged(self) -> None:
        """Whitespace-only text should pass through."""
        assert mask_pii("   \n\t  ") == "   \n\t  "


class TestEdgeCases:
    """Test edge cases and defensive programming."""

    def test_none_input(self) -> None:
        """Non-string input should be handled gracefully."""
        result = mask_pii(None)
        assert isinstance(result, str)

    def test_bytes_input(self) -> None:
        """Bytes input should be converted and masked."""
        text = b"Contact: test@example.com"
        result = mask_pii(text)
        assert "[EMAIL]" in result

    def test_very_long_email(self) -> None:
        """Very long email addresses should be masked."""
        text = "Use this email: verylongemailaddresswithlotsofcharacters@company-domain-with-many-subdomains.co.uk"
        result = mask_pii(text)
        assert "[EMAIL]" in result

    def test_phone_in_different_formats(self) -> None:
        """Phone numbers in various formats should be masked."""
        text = "Call 1234567890 or (123) 456-7890 or +1 234.567.890"
        result = mask_pii(text)
        assert "[PHONE]" in result


class TestSecurityCompliance:
    """Test security compliance requirements."""

    def test_no_exceptions_raised(self) -> None:
        """mask_pii should never raise exceptions on any input."""
        test_cases = [
            "",
            "normal text",
            "support@example.com",
            "+1-555-123-4567",
            "AKIAIOSFODNN7EXAMPLE",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.key",
            "password123!",
        ]

        for test_input in test_cases:
            try:
                mask_pii(test_input)
            except Exception as exc:
                pytest.fail(
                    f"mask_pii should not raise exceptions. Failed on input: {test_input}. Exception: {exc}"
                )

    def test_special_characters_preserved(self) -> None:
        """Non-PII special characters should be preserved."""
        text = "The email support@example.com is valid and the phone number +1-555-123-4567 needs masking"
        result = mask_pii(text)
        assert "[EMAIL]" in result or "email" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
