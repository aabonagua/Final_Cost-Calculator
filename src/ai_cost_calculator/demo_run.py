import json
from ai_cost_calculator import estimate_cost
from dotenv import load_dotenv
import os

load_dotenv()

print("demo_run started")
print(os.getenv("NOOKO_INTERNAL_TOKEN"))

payload = {
  "ai_usage": [
      {
      "timestamp": "2026-01-23T01:08:09.462839",
      "model": "gpt-5-mini",
      "module": "product_completion_process_other_attributes",
      "status": "success",
      "input_tokens": 447,
      "output_tokens": 132,
      "cost_usd": "",
      "latency_ms": 8616.6,
      "error_message": None,
      "error_type": None
    },
    {
      "timestamp": "2026-01-23T01:08:09.462839",
      "model": "Sample",
      "module": "product_completion_process_other_attributes",
      "status": "success",
      "input_tokens": 447,
      "output_tokens": 132,
      "cost_usd": "",
      "latency_ms": 8616.6,
      "error_message": None,
      "error_type": None
    },
    {
      "timestamp": "2026-01-23T01:08:09.462839",
      "model": "Test",
      "module": "product_completion_process_other_attributes",
      "status": "success",
      "input_tokens": 447,
      "output_tokens": 132,
      "cost_usd": "",
      "latency_ms": 8616.6,
      "error_message": None,
      "error_type": None
    }

  ]
    
  
}

out = estimate_cost(payload)
print(json.dumps(out, indent=2))
