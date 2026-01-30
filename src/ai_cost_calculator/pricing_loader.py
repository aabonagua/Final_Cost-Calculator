import json
from functools import lru_cache
from importlib import resources
from typing import Any, Dict, Optional


@lru_cache(maxsize=8)
def get_pricing(pricing_path: Optional[str] = None) -> Dict[str, Any]:
    if pricing_path:
        with open(pricing_path, "r", encoding="utf-8") as f:
            return json.load(f)

    with resources.files("ai_cost_calculator").joinpath("model_pricing.json").open("r", encoding="utf-8") as f:
        return json.load(f)
