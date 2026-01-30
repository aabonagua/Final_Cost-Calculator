import json
from decimal import Decimal
import pytest

from ai_cost_calculator import calculator as cc


@pytest.fixture()
def pricing_stub():
    """
    Small PRICING stub so tests don't depend on your real model_pricing.json.
    We'll monkeypatch cc.PRICING to this.
    """
    return {
        "openai": {
            "billing_unit_tokens": 1_000_000,
            "models": {
                "gpt-5-mini": {
                    "input": 0.25,
                    "cached_input": 0.025,
                    "output": 2.0,
                    "aliases": [],
                },
                "gpt-5-pro": {
                    "input": 15.0,
                    "cached_input": None,  # cached not supported
                    "output": 120.0,
                    "aliases": ["gpt-5-pro-alias"],
                },
            },
        },
        "google": {
            "billing_unit_tokens": 1_000_000,
            "models": {
                "gemini-2.5-pro": {
                    "tiers": [
                        {
                            "max_input_tokens": 200000,
                            "input": 1.25,
                            "output": 10.0,
                            "context_cache": 0.125,
                            "storage_per_hour": 4.5,
                        },
                        {
                            "max_input_tokens": None,
                            "input": 2.5,
                            "output": 15.0,
                            "context_cache": 0.25,
                            "storage_per_hour": 4.5,
                        },
                    ]
                }
            },
        },
    }


@pytest.fixture(autouse=True)
def patch_pricing(pricing_stub, monkeypatch):
    """
    Automatically replace the module-global PRICING for all tests.
    """
    monkeypatch.setattr(cc, "PRICING", pricing_stub)


def dec(s: str) -> Decimal:
    return Decimal(s)


# -------------------------
# Basic behavior tests
# -------------------------

def test_estimate_cost_leaves_existing_cost_unchanged():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-mini",
                "status": "success",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": "0.12345678",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    assert out["ai_usage"][0]["cost_usd"] == "0.12345678"


def test_estimate_cost_skips_non_success_by_default():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-mini",
                "status": "error",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload, skip_non_success=True)
    assert out["ai_usage"][0]["cost_usd"] == ""  # unchanged


def test_estimate_cost_can_compute_even_if_non_success_when_disabled():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-mini",
                "status": "error",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload, skip_non_success=False)
    assert out["ai_usage"][0]["cost_usd"] != ""  # computed


def test_unknown_model_is_left_unchanged():
    payload = {
        "ai_usage": [
            {
                "model": "unknown-model",
                "status": "success",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    assert out["ai_usage"][0]["cost_usd"] == ""


def test_payload_string_roundtrip_returns_string():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-mini",
                "status": "success",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": "",
            }
        ]
    }
    raw = json.dumps(payload)
    out_raw = cc.estimate_cost(raw)
    assert isinstance(out_raw, str)

    out = json.loads(out_raw)
    assert out["ai_usage"][0]["cost_usd"] != ""


# -------------------------
# OpenAI estimator tests
# -------------------------

def test_openai_cost_computation_basic_no_cache():
    usage = {
        "model": "gpt-5-mini",
        "status": "success",
        "input_tokens": 200,
        "output_tokens": 100,
        "cached_tokens": 0,
        "cost_usd": "",
    }

    # Run full pipeline
    payload = {"ai_usage": [usage]}
    out = cc.estimate_cost(payload)
    got = dec(out["ai_usage"][0]["cost_usd"])

    # Expected (Decimal math):
    # input: (200/1e6)*0.25 = 0.00005
    # output:(100/1e6)*2.0  = 0.0002
    # total = 0.00025
    expected = Decimal("0.00025")

    # Output is quantized to 8 decimals -> 0.00025000
    assert got == Decimal("0.00025000")
    # also ensure close to the unquantized expected
    assert abs(got - expected) <= Decimal("0.00000001")


def test_openai_cached_tokens_from_input_token_details():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-mini",
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 0,
                "input_token_details": {"cached_tokens": 400},
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    got = dec(out["ai_usage"][0]["cost_usd"])

    # billable_input=600
    # input: (600/1e6)*0.25 = 0.00015
    # cached:(400/1e6)*0.025 = 0.00001
    # total=0.00016 => "0.00016000"
    assert got == Decimal("0.00016000")


def test_openai_cached_not_supported_treat_as_billable():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-pro",  # cached_input=None in pricing
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 0,
                "cached_tokens": 400,  # should be ignored (treated as 0)
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    got = dec(out["ai_usage"][0]["cost_usd"])

    # cached not supported => effective_cached=0, billable_input=1000
    # input: (1000/1e6)*15 = 0.015 => "0.01500000"
    assert got == Decimal("0.01500000")


def test_openai_alias_resolution():
    payload = {
        "ai_usage": [
            {
                "model": "gpt-5-pro-alias",  # alias of gpt-5-pro
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 0,
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    assert out["ai_usage"][0]["cost_usd"] == "0.01500000"


# -------------------------
# Gemini estimator tests
# -------------------------

def test_gemini_tier_selection_first_tier():
    payload = {
        "ai_usage": [
            {
                "model": "gemini-2.5-pro",
                "status": "success",
                "input_tokens": 100_000,   # <= 200k => first tier
                "output_tokens": 10_000,
                "cached_tokens": 20_000,
                "storage_hours": 0,
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    got = dec(out["ai_usage"][0]["cost_usd"])

    # tier1 prices: input=1.25 output=10 cache=0.125
    # billable_input = 100k - 20k = 80k
    # input:  (80k/1e6)*1.25 = 0.1
    # cache:  (20k/1e6)*0.125 = 0.0025
    # output: (10k/1e6)*10 = 0.1
    # total = 0.2025 => "0.20250000"
    assert got == Decimal("0.20250000")


def test_gemini_tier_selection_second_tier_and_storage():
    payload = {
        "ai_usage": [
            {
                "model": "gemini-2.5-pro",
                "status": "success",
                "input_tokens": 300_000,  # > 200k => second tier (max_input_tokens=None)
                "output_tokens": 0,
                "cached_tokens": 0,
                "storage_hours": 2,       # storage included
                "cost_usd": "",
            }
        ]
    }
    out = cc.estimate_cost(payload)
    got = dec(out["ai_usage"][0]["cost_usd"])

    # tier2 prices: input=2.5 output=15 cache=0.25 storage=4.5/hr
    # billable_input = 300k
    # input: (300k/1e6)*2.5 = 0.75
    # storage: 2*4.5 = 9.0
    # total = 9.75 => "9.75000000"
    assert got == Decimal("9.75000000")
