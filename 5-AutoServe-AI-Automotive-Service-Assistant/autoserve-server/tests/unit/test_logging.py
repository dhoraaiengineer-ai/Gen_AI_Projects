from __future__ import annotations

from app.core.logging import mask_pii, mask_text, mask_vin

SYNTHETIC_VIN = "VLX1A2B3C4D567890"  # synthetic format sample only (check digit not asserted here)


def test_mask_vin_keeps_last_six() -> None:
    assert mask_vin(SYNTHETIC_VIN) == "***567890"


def test_mask_text_masks_vin_email_phone() -> None:
    out = mask_text(f"vin {SYNTHETIC_VIN} mail priya@example.com tel +91 98765 43210")
    assert SYNTHETIC_VIN not in out and "***567890" in out
    assert "priya@example.com" not in out and "[email]" in out
    assert "98765" not in out and "[phone]" in out


def test_processor_masks_pii_keys_and_nested_values() -> None:
    event = {
        "event": "checked_in",
        "vin": SYNTHETIC_VIN,
        "phone": "+91 98765 43210",
        "display_name": "Priya",
        "payload": {"plate_number": "KA01AB1234", "note": f"see {SYNTHETIC_VIN}"},
        "odometer_km": 42000,
    }
    out = mask_pii(None, "info", dict(event))
    assert out["vin"] == "***567890"
    assert out["phone"] == "[redacted]"
    assert out["display_name"] == "[redacted]"
    assert out["payload"]["plate_number"] == "[redacted]"
    assert SYNTHETIC_VIN not in out["payload"]["note"]
    assert out["odometer_km"] == 42000
    assert out["event"] == "checked_in"
