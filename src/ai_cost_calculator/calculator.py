import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union

from .pricing_loader import get_pricing
from .alerts import notify_unknown_models_if_configured

# ----------------------------
# Simple helpers
# ----------------------------

# Helper to convert to Decimal with default
def d(x: Any, default: str = "0") -> Decimal:
    try:
        if x is None:
            return Decimal(default)
        return Decimal(str(x))
    except Exception:
        return Decimal(default)

# Helper to convert to int with default
def i(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default

# Format Decimal as USD string with 8 decimal places
def fmt_usd_8(amount: Decimal) -> str:
    q = amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return format(q, "f") 

# Check if cost_usd is empty
def is_empty_cost(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


# ----------------------------
# Mapping function (ONE place)
# ----------------------------

def get_usage_fields(usage: Dict[str, Any]) -> Dict[str, Any]:
    model = str(usage.get("model") or "")
    status = str(usage.get("status") or "")
    input_tokens = i(usage.get("input_tokens"), 0)
    output_tokens = i(usage.get("output_tokens"), 0)

    cached_tokens = i(usage.get("cached_tokens"), 0)

    # Fallback to input_token_details.cached_tokens if not present directly
    if cached_tokens == 0:
        details = usage.get("input_token_details")
        if isinstance(details, dict):
            cached_tokens = i(details.get("cached_tokens"), 0)

    storage_hours = d(usage.get("storage_hours"), "0")

    return {
        "model": model,
        "status": status,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "storage_hours": storage_hours,
    }


# ----------------------------
# Breakdown builders
# ----------------------------

# Line item builder for cost breakdown
def li(name: str, quantity: Any, unit: str, unit_price: Decimal, cost: Decimal) -> Dict[str, Any]:
    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "unit_price": float(unit_price),
        "cost": float(cost),
    }

# Cost payload builder
def build_cost_payload(
    *,
    provider: str,
    model: str,
    unit_tokens: int,
    tokens: Dict[str, Any],
    pricing: Dict[str, Any],
    line_items: List[Dict[str, Any]],
    total: Decimal,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "unit_tokens": int(unit_tokens),
        "tokens": tokens,
        "pricing": pricing,
        "line_items": line_items,
        "total": float(total),
        "meta": meta or {},
    }


# ----------------------------
# Provider/model resolver
# ----------------------------

def resolve_provider_model(pricing: Dict[str, Any], model_name: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    # OpenAI (key + aliases)
    openai_models = (pricing.get("openai") or {}).get("models") or {}
    if isinstance(openai_models, dict):
        if model_name in openai_models:
            return "openai", model_name, openai_models[model_name]
        for key, cfg in openai_models.items():
            aliases = (cfg or {}).get("aliases") or []
            if model_name in aliases:
                return "openai", key, cfg

    # Google (key + aliases if present)
    google_models = (pricing.get("google") or {}).get("models") or {}
    if isinstance(google_models, dict):
        if model_name in google_models:
            return "google", model_name, google_models[model_name]
        for key, cfg in google_models.items():
            aliases = (cfg or {}).get("aliases") or []
            if model_name in aliases:
                return "google", key, cfg

    return None, None, None


# ----------------------------
# OpenAI estimator (reference style)
# ----------------------------

def estimate_openai_cost(pricing: Dict[str, Any], model: str, usage: Dict[str, Any]) -> Dict[str, Any]:
    provider, key, cfg = resolve_provider_model(pricing, model)
    if provider != "openai" or not isinstance(cfg, dict):
        raise ValueError(f"No pricing found for OpenAI model: {model}")

    unit = i((pricing.get("openai") or {}).get("billing_unit_tokens"), 1_000_000)

    f = get_usage_fields(usage)
    input_tokens = f["input_tokens"]
    output_tokens = f["output_tokens"]
    cached_tokens = f["cached_tokens"]

    input_price = d(cfg.get("input"), "0")
    output_price = d(cfg.get("output"), "0")

    cached_input_raw = cfg.get("cached_input", None)  # can be null
    cached_price = d(cached_input_raw, "0") if cached_input_raw is not None else Decimal("0")
    effective_cached = cached_tokens if cached_input_raw is not None else 0

    billable_input = max(input_tokens - effective_cached, 0)

    input_cost = (Decimal(billable_input) / Decimal(unit)) * input_price
    cached_cost = (Decimal(effective_cached) / Decimal(unit)) * cached_price
    output_cost = (Decimal(output_tokens) / Decimal(unit)) * output_price

    total = input_cost + cached_cost + output_cost

    line_items = [
        li("input_tokens_billable", billable_input, "tokens", (input_price / Decimal(unit)), input_cost),
        li("input_tokens_cached", effective_cached, "tokens", (cached_price / Decimal(unit)), cached_cost),
        li("output_tokens", output_tokens, "tokens", (output_price / Decimal(unit)), output_cost),
    ]

    return build_cost_payload(
        provider="openai",
        model=key or model,
        unit_tokens=unit,
        tokens={
            "input": input_tokens,
            "cached": effective_cached,
            "billable_input": billable_input,
            "output": output_tokens,
        },
        pricing={
            "input": float(input_price),
            "cached_input": (float(cached_price) if cached_input_raw is not None else None),
            "output": float(output_price),
        },
        line_items=line_items,
        total=total,
        meta={},
    )


# ----------------------------
# Gemini estimator (tiered, reference style)
# ----------------------------

def select_tier(tiers: List[Dict[str, Any]], input_tokens: int) -> Dict[str, Any]:
    if not tiers:
        raise ValueError("No pricing tiers configured")

    for tier in tiers:
        mx = tier.get("max_input_tokens")
        if mx is None or input_tokens <= i(mx, 0):
            return tier
    return tiers[-1]

def estimate_gemini_cost(pricing: Dict[str, Any], model: str, usage: Dict[str, Any]) -> Dict[str, Any]:
    provider, key, cfg = resolve_provider_model(pricing, model)
    if provider != "google" or not isinstance(cfg, dict):
        raise ValueError(f"No pricing found for Gemini model: {model}")

    unit = i((pricing.get("google") or {}).get("billing_unit_tokens"), 1_000_000)

    f = get_usage_fields(usage)
    input_tokens = f["input_tokens"]
    output_tokens = f["output_tokens"]
    cached_tokens = f["cached_tokens"]
    storage_hours = f["storage_hours"]

    tiers = cfg.get("tiers") or []
    tier = select_tier(tiers, input_tokens)

    input_price = d(tier.get("input"), "0")
    output_price = d(tier.get("output"), "0")
    cache_price = d(tier.get("context_cache"), "0")
    storage_price = d(tier.get("storage_per_hour"), "0")

    billable_input = max(input_tokens - cached_tokens, 0)

    input_cost = (Decimal(billable_input) / Decimal(unit)) * input_price
    cache_cost = (Decimal(cached_tokens) / Decimal(unit)) * cache_price
    output_cost = (Decimal(output_tokens) / Decimal(unit)) * output_price
    storage_cost = storage_hours * storage_price

    total = input_cost + cache_cost + output_cost + storage_cost

    line_items = [
        li("input_tokens_billable", billable_input, "tokens", (input_price / Decimal(unit)), input_cost),
        li("context_cache_tokens", cached_tokens, "tokens", (cache_price / Decimal(unit)), cache_cost),
        li("output_tokens", output_tokens, "tokens", (output_price / Decimal(unit)), output_cost),
    ]
    if storage_hours != 0:
        line_items.append(li("storage_hours", float(storage_hours), "hours", storage_price, storage_cost))

    return build_cost_payload(
        provider="google",
        model=key or model,
        unit_tokens=unit,
        tokens={
            "input": input_tokens,
            "cached": cached_tokens,
            "billable_input": billable_input,
            "output": output_tokens,
            "storage_hours": float(storage_hours),
        },
        pricing={
            "input": float(input_price),
            "context_cache": float(cache_price),
            "output": float(output_price),
            "storage_per_hour": float(storage_price),
        },
        line_items=line_items,
        total=total,
        meta={"tier": tier},
    )


# ----------------------------
# Main entrypoint (payload-only)
# ----------------------------

def estimate_cost(
    payload: Union[str, Dict[str, Any]],
    *,
    pricing_path: Optional[str] = None,
    skip_non_success: bool = True,
    alert_unknown_models: bool = True,
) -> Union[str, Dict[str, Any]]:

    is_str = isinstance(payload, str)
    data = json.loads(payload) if is_str else payload

    if not isinstance(data, dict):
        return payload

    pricing = get_pricing(pricing_path)
    ai_usage = data.get("ai_usage")

    if isinstance(ai_usage, dict):
        ai_usage_list = [ai_usage]
    elif isinstance(ai_usage, list):
        ai_usage_list = ai_usage
    else:
        return payload

    unknown_models_map: Dict[str, Dict[str, Any]] = {}

    for usage in ai_usage_list:
        if not isinstance(usage, dict):
            continue

        if skip_non_success and usage.get("status") != "success":
            continue

        if not is_empty_cost(usage.get("cost_usd")):
            continue

        fields = get_usage_fields(usage)
        model = fields["model"]
        if not model:
            continue

        provider, _, _ = resolve_provider_model(pricing, model)
        if provider is None:
            unknown_models_map.setdefault(model, {
                "model": model,
                "provider_guess": None,
                "usage": {
                    "timestamp": usage.get("timestamp"),
                    "module": usage.get("module"),
                    "status": usage.get("status"),
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                },
            })
            continue

        try:
            if provider == "openai":
                breakdown = estimate_openai_cost(pricing, model, usage)
            elif provider == "google":
                breakdown = estimate_gemini_cost(pricing, model, usage)
            else:
                continue

            usage["cost_usd"] = fmt_usd_8(d(breakdown["total"], "0"))
        except Exception:
            continue
    
    # Once the unknown are populated, it will call the notifier with the list of the unknown models and their details
    if alert_unknown_models and unknown_models_map:
        notify_unknown_models_if_configured(
            unknown_models=list(unknown_models_map.values())
        )

    return json.dumps(data, ensure_ascii=False) if is_str else data
