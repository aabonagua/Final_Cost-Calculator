import json
from decimal import Decimal
import pytest

from ai_cost_calculator import calculator as cc


@pytest.fixture(autouse=True)
def patch_pricing(monkeypatch):
    """
    Provide a minimal pricing config that includes gemini-2.5-flash-image
    and patch the module-global PRICING used by your functions.
    """
    pricing_stub = {
        "google": {
            "billing_unit_tokens": 1_000_000,
            "models": {
                "gemini-2.5-flash-image": {
                    "tiers": [
                        {
                            "max_input_tokens": None,
                            "input": 0.30,          # per 1M tokens
                            "output": 2.5,          # per 1M tokens (token-based output for this test)
                            "context_cache": 0.0,
                            "storage_per_hour": 0.0
                        }
                    ]
                }
            }
        },
        "openai": {
            "billing_unit_tokens": 1_000_000,
            "models": {}
        }
    }
    monkeypatch.setattr(cc, "PRICING", pricing_stub)


def test_gemini_flash_image_payload_cost_is_computed_and_formatted():
    payload = {
        "ai_usage": [
            {
                "timestamp": "2026-01-16T03:11:06.577291",
                "model": "gemini-2.5-flash-image",
                "module": "create_image",
                "status": "success",
                "input_tokens": 673,
                "output_tokens": 1290,
                "cost_usd": None,
                "latency_ms": 8803.289200004656,
                "error_message": None,
                "error_type": None
            }
        ]
    }

    out = cc.estimate_cost(payload)

    # Expected:
    # billable_input = 673 (no cache)
    # input_cost  = (673 / 1_000_000) * 0.30  = 0.0002019
    # output_cost = (1290 / 1_000_000) * 2.5  = 0.003225
    # total = 0.0034269 -> formatted to 8 dp => "0.00342690"
    assert out["ai_usage"][0]["cost_usd"] == "0.00342690"


def test_gemini_flash_image_payload_string_input_returns_string():
    raw_payload = json.dumps({
        "ai_usage": [
            {
                "timestamp": "2026-01-16T03:11:06.577291",
                "model": "gemini-2.5-flash-image",
                "module": "create_image",
                "status": "success",
                "input_tokens": 673,
                "output_tokens": 1290,
                "cost_usd": None,
                "latency_ms": 8803.289200004656,
                "error_message": None,
                "error_type": None
            }
        ]
    })

    out_raw = cc.estimate_cost(raw_payload)
    assert isinstance(out_raw, str)

    out = json.loads(out_raw)
    assert out["ai_usage"][0]["cost_usd"] == "0.00342690"

