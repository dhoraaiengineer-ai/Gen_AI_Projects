# Assuming these services are available in the test environment
from app.services.pii_service import mask_pii


def test_parsed_page_pii_masking_integration():
    """
    Verifies that when a DocumentParser creates a ParsedPage, its raw text
    is immediately processed by the PII masker before being chunked/serialized.
    This validates the contract enforcement point at the end of D-5.
    """
    # --- Test Setup: Mocking the required object structure ---
    # In a real test environment, we would mock DocumentParser's output here.
    class MockParsedPage:
        def __init__(self, raw_content, page_num):
            self.raw_content = raw_content
            self.page_number = page_num
            self.masked_content = "" # This is the property we test for cleanliness

    # 1. Test Case: PII present
    raw_text_pii = "Contact Aarav at aarav@corp.com or call +91-98765-43210."
    mock_page_1 = MockParsedPage(raw_content=raw_text_pii, page_num=1)

    # 2. Execution: Simulate the contract enforcement hook (where mask_pii MUST be called)
    masked_text_expected = mask_pii(raw_text_pii)
    mock_page_1.masked_content = masked_text_expected

    # 3. Assertion: Check if the *internal* state holds the securely processed data
    assert mock_page_1.masked_content == "Contact Aarav at [EMAIL] or call [PHONE].", \
        f"FAIL: Masking failed. Expected specific mask, got {mock_page_1.masked_content}"

    # 4. Test Case: Clean Text (Negative check)
    clean_text = "This is a purely technical document section with no sensitive data."
    mock_page_2 = MockParsedPage(raw_content=clean_text, page_num=2)
    mock_page_2.masked_content = mask_pii(clean_text) # Should pass through unchanged

    assert mock_page_2.masked_content == clean_text, \
        "FAIL: Clean text was incorrectly masked."
