# AI Cost Calculator — Quick Install & Integration Guide

## Recommended integration approach (clean + safe)
- ✅ Keep the calculator folder **outside** your repository
- ✅ Install it into your **Python environment (venv)**
- ✅ Your repository should not contain the calculator files — only the import + function call is added (ideally on a branch)

---

## 1) Install (if you are working on the calculator repo itself)

Run this inside the calculator folder (the folder that contains `pyproject.toml`):

    ```bash
    pip install -e .
    What this does
    Installs the calculator as a local Python package

Lets you import it anywhere using:

    from ai_cost_calculator import estimate_cost
Uses editable mode (code changes apply immediately)

Quick check:

    python -c "from ai_cost_calculator import estimate_cost; print('import ok')"

## 2) Install it into your repository (ZIP handoff)
### Step A — Unzip OUTSIDE your repo
Example location (Windows):

    C:\temp\Final-Cost-Calculator\

✅ Do NOT place it inside your repo folder.

### Step B — Install into your repo’s Python environment

Windows (Git Bash):

    cd /c/work/your-repo
    python -m venv .venv
    source .venv/Scripts/activate
    pip install -e /c/temp/Final-Cost-Calculator

Result:

Your repo stays clean (no copied files)

Your environment can import the package normally

## 3) Import in your code

    from ai_cost_calculator import estimate_cost

**Note (VS Code)**: If it shows “module cannot be resolved”, select your .venv interpreter:
Python: Select Interpreter → choose .venv.

## 4) Use it on the payload you already generate (dict payload)
    from ai_cost_calculator import estimate_cost

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

    out = estimate_cost(payload)
    print(out["ai_usage"][0]["cost_usd"])

**Behavior:**

If cost_usd is already filled → unchanged

If status != "success" (default) → skipped

If the model is not in pricing JSON → skipped

Output format: cost_usd is a string with 8 decimals (e.g., "0.00025400")

## 5) If your payload is a JSON string (string in → string out)
    from ai_cost_calculator import estimate_cost

    out_json = estimate_cost(in_json)
## 6) Pricing updates (when prices change)
If you installed from a ZIP (folder path install)
If you unzip the new version to the same folder path you installed from (e.g. C:\temp\Final-Cost-Calculator):
✅ Usually no reinstall needed (editable install points to that folder)

If the folder path changes, reinstall using the new path:

    pip install -e C:\temp\Final-Cost-Calculator-new

If you installed from a Git repo

    Pull the latest changes:

git pull
✅ Usually no reinstall needed. Re-run pip install -e . only if dependencies or package structure changed.

If you want pricing updates without updating the package
Keep your own pricing JSON and override:

    out = estimate_cost(payload, pricing_path="path/to/ai-model_pricing.json")
7) Optional: override pricing JSON file

    out = estimate_cost(payload, pricing_path="path/to/ai-model_pricing.json")
8) Quick uninstall (if you only needed it for testing)

    pip uninstall ai-cost-calculator