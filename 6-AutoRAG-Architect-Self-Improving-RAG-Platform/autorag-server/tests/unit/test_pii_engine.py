"""Unit tests for the canonical PII detection/masking engine (P0.7-1, P0.7-6).

app.services.pii_engine is the SINGLE source of truth for PII pattern
matching — pii_service.py (sync) and pii_detector.py (async) are thin
wrappers over it. These tests are table-driven across every canonical PII
category and additionally verify:
  - the original value is never present in masked_text
  - counts_by_type is accurate
  - the audit-safe result never leaks a sample of the original value
  - benign text produces no false positives
"""

from __future__ import annotations

import pytest

from app.services.pii_engine import (
    DETECTOR_VERSION,
    PIIRedactionResult,
    contains_pii,
    redact,
)

# ─────────────────────────────────────────────────────────────────────────────
# Table-driven coverage — one row per canonical PII category (P0.7-6)
# ─────────────────────────────────────────────────────────────────────────────

_CATEGORY_CASES: list[tuple[str, str, str, str]] = [
    # (case_id, pii_type, sample_text, original_value_to_confirm_absent)
    ("email", "EMAIL", "Contact us at support@example.com for help", "support@example.com"),
    ("phone_us", "PHONE", "Call +1-555-123-4567 for support", "+1-555-123-4567"),
    ("phone_intl", "PHONE", "Contact +44-20-7946-0958 for UK support", "+44-20-7946-0958"),
    ("ssn", "SSN", "My SSN is 123-45-6789 on file", "123-45-6789"),
    ("credit_card", "CREDIT_CARD", "Card number: 4111111111111111 expires soon", "4111111111111111"),
    ("address", "ADDRESS", "Ship to 742 Evergreen Street, please", "742 Evergreen Street"),
    (
        "bearer_token",
        "BEARER_TOKEN",
        "Authorization: Bearer abc123DEF456ghi789JKL012mno345PQR",
        "abc123DEF456ghi789JKL012mno345PQR",
    ),
    ("password", "PASSWORD", "password: SuperSecretPass123!", "SuperSecretPass123!"),
    ("aws_key", "AWS_ACCESS_KEY", "AWS Access Key ID: AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
    (
        "jwt_service_key",
        "JWT_OR_SERVICE_KEY",
        "api=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
    ),
]


class TestCanonicalCategoriesDetection:
    """For every canonical type: detection occurs and the canonical token appears."""

    @pytest.mark.parametrize("case_id,pii_type,text,_original", _CATEGORY_CASES, ids=[c[0] for c in _CATEGORY_CASES])
    def test_detection_occurs(self, case_id: str, pii_type: str, text: str, _original: str) -> None:
        result = redact(text)
        assert result.total_redaction_count > 0, f"{case_id}: expected at least one redaction"

    @pytest.mark.parametrize("case_id,pii_type,text,_original", _CATEGORY_CASES, ids=[c[0] for c in _CATEGORY_CASES])
    def test_canonical_token_present(self, case_id: str, pii_type: str, text: str, _original: str) -> None:
        result = redact(text)
        assert f"[{pii_type}]" in result.masked_text, (
            f"{case_id}: expected [{pii_type}] token in masked_text, got {result.masked_text!r}"
        )

    @pytest.mark.parametrize("case_id,pii_type,text,original", _CATEGORY_CASES, ids=[c[0] for c in _CATEGORY_CASES])
    def test_original_value_absent_after_masking(self, case_id: str, pii_type: str, text: str, original: str) -> None:
        result = redact(text)
        assert original not in result.masked_text, f"{case_id}: original value leaked into masked_text"

    @pytest.mark.parametrize("case_id,pii_type,text,_original", _CATEGORY_CASES, ids=[c[0] for c in _CATEGORY_CASES])
    def test_counts_by_type_correct(self, case_id: str, pii_type: str, text: str, _original: str) -> None:
        result = redact(text)
        assert result.counts_by_type.get(pii_type, 0) >= 1, (
            f"{case_id}: expected counts_by_type[{pii_type}] >= 1, got {result.counts_by_type}"
        )


class TestMultipleRedactionsInOneText:
    def test_two_emails_counted_correctly(self) -> None:
        result = redact("Contact alice@company.org or bob@test.net")
        assert result.counts_by_type["EMAIL"] == 2
        assert result.total_redaction_count == 2
        assert result.masked_text.count("[EMAIL]") == 2

    def test_mixed_categories_all_detected(self) -> None:
        text = "Email me at user@example.com or call +1-555-123-4567. SSN: 123-45-6789."
        result = redact(text)
        assert result.counts_by_type.get("EMAIL", 0) >= 1
        assert result.counts_by_type.get("PHONE", 0) >= 1
        assert result.counts_by_type.get("SSN", 0) >= 1
        assert result.total_redaction_count == sum(result.counts_by_type.values())


class TestIdempotency:
    def test_redact_is_idempotent(self) -> None:
        text = "Contact support@example.com, SSN 123-45-6789, card 4111111111111111"
        once = redact(text).masked_text
        twice = redact(once).masked_text
        assert once == twice


class TestEdgeCases:
    def test_none_input(self) -> None:
        result = redact(None)
        assert isinstance(result, PIIRedactionResult)
        assert result.masked_text == ""
        assert result.total_redaction_count == 0

    def test_empty_string(self) -> None:
        result = redact("")
        assert result.masked_text == ""
        assert result.counts_by_type == {}

    def test_bytes_input(self) -> None:
        result = redact(b"Contact: test@example.com")
        assert "[EMAIL]" in result.masked_text

    def test_never_raises(self) -> None:
        for value in ["", None, "normal text", 12345, "support@example.com"]:  # type: ignore[list-item]
            redact(value)  # must not raise


class TestNegativeFalsePositives:
    """Benign numeric/text content must not be misclassified as PII (P0.7-6)."""

    @pytest.mark.parametrize(
        "text",
        [
            "The meeting is scheduled for 10:30 AM tomorrow.",
            "We sold 4111 units last quarter.",  # short digit run, not a card number
            "Chapter 12, Section 3.4.5 covers the appendix.",
            "The temperature was 98.6 degrees.",
            "Version 1.2.3 was released on schedule.",
            "Room 742 is on the third floor.",  # digits without a street suffix
        ],
    )
    def test_benign_text_produces_no_redactions(self, text: str) -> None:
        result = redact(text)
        assert result.total_redaction_count == 0, (
            f"False positive on benign text {text!r}: {result.counts_by_type}"
        )
        assert result.masked_text == text


class TestContainsPii:
    def test_true_when_pii_present(self) -> None:
        assert contains_pii("Contact me at a@b.com") is True

    def test_false_when_no_pii(self) -> None:
        assert contains_pii("Nothing sensitive here.") is False

    def test_false_on_none(self) -> None:
        assert contains_pii(None) is False


class TestAuditSafety:
    """P0.7-6: recursively verify nothing in the audit-safe fields leaks the original value."""

    def test_result_fields_never_contain_original_value(self) -> None:
        original_values = [
            "support@example.com",
            "+1-555-123-4567",
            "123-45-6789",
            "4111111111111111",
            "AKIAIOSFODNN7EXAMPLE",
        ]
        text = (
            "Email support@example.com, call +1-555-123-4567, SSN 123-45-6789, "
            "card 4111111111111111, key AKIAIOSFODNN7EXAMPLE"
        )
        result = redact(text)

        # The only field that legitimately still contains replacement tokens
        # is masked_text -- counts_by_type/total_redaction_count/
        # detector_version must be pure metadata (str/int), never raw values.
        audit_safe_payload = {
            "total_redaction_count": result.total_redaction_count,
            "counts_by_type": result.counts_by_type,
            "detector_version": result.detector_version,
        }

        def _recursively_check(value: object) -> None:
            if isinstance(value, dict):
                for v in value.values():
                    _recursively_check(v)
            elif isinstance(value, (list, tuple)):
                for v in value:
                    _recursively_check(v)
            elif isinstance(value, str):
                for original in original_values:
                    assert original not in value, (
                        f"Original PII value {original!r} leaked into audit-safe field: {value!r}"
                    )

        _recursively_check(audit_safe_payload)

    def test_detector_version_is_stable_string(self) -> None:
        assert redact("test").detector_version == DETECTOR_VERSION
        assert isinstance(DETECTOR_VERSION, str) and DETECTOR_VERSION
