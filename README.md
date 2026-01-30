# AI Cost Calculator — Quick Install & Integration Guide

This package computes `cost_usd` for AI usage records based on a bundled pricing JSON. It can optionally alert via Nooko’s internal email API when an unknown model is encountered.

---

## Recommended integration approach (clean + safe)

- ✅ Keep the calculator folder **outside** your main repository
- ✅ Install it into your **Python environment**
- ✅ Your main repo should not contain calculator source files — only imports + function calls

---

## 1) Install (working on this repo)

Run this inside the calculator folder (the folder with `pyproject.toml`):

bash

    pip install -e .

Quick check:

    python -c "from ai_cost_calculator import estimate_cost; print('import ok')"
## 2) Install into another repository (ZIP handoff)
**Step A — Unzip OUTSIDE your repo**

Example (Windows):

C:\temp\Final-Cost-Calculator\
✅ Do NOT place it inside your repo folder.

**Step B — Install into your Python environment**

Example (Windows Git Bash):

    cd /c/work/your-repo
    pip install -e /c/temp/Final-Cost-Calculator

**Result:**

Your repo stays clean (no copied package files)

Your environment can import the package normally

## 3) Import in your code
    from ai_cost_calculator import estimate_cost
**VS Code note:** If it shows ***“module cannot be resolved”***, 
- select the correct Python interpreter:

    **Python:** Select Interpreter → choose the interpreter/environment where you installed the package.

    or **Restart VS Code**

## 4) Use it (dict payload → dict output)
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
                "latency_ms": 8803.2892,
                "error_message": None,
                "error_type": None
            }
        ]
    }

    out = estimate_cost(payload)
    print(json.dumps(out, indent=2))

**Behavior**

- If cost_usd is already filled → unchanged

- If status != "success" (default) → skipped

- If model is not found in pricing → cost remains empty and will send an alert email to support

**Output format:** cost_usd is a string with 8 decimals (e.g., "0.00025400")

## 5) If your payload is a JSON string (string in → string out)
    from ai_cost_calculator import estimate_cost

    out_json = estimate_cost(in_json_string)
## 6) Pricing source and overrides
**Default pricing (built-in)**

The package reads pricing from the bundled file:

    ai_cost_calculator/model_pricing.json

**Override pricing file (optional)**

If you want pricing updates without changing the package version:

    out = estimate_cost(payload, pricing_path="path/to/model_pricing.json")

## 7) Keeping pricing updated (recommended)

If you installed the calculator from a Git repository, pull the latest changes regularly so you always have the newest pricing:

    cd /path/to/Final-Cost-Calculator
    git pull


If your main project uses an editable install pointing to that folder, the updated pricing will be used immediately (no reinstall needed).

If you are using a ZIP handoff instead of Git, you must replace the folder contents with the newest ZIP version to update pricing.

## 8) Optional: Email alerts for unknown models
The calculator can send an email alert when an unknown model is encountered.

**Configuration**

The package reads configuration from environment variables **(the caller/app should load env).**

Use **.env.example** as a template (do not commit real .env values):

    // Request for the X-Internal-Token
    NOOKO_INTERNAL_TOKEN=__SET_ME__

    // Add to the email: Boss Sandro's email, Ms. Kristina's email, support@nooko.ai
    // For Testing: Set it to oyur email
    NOOKO_ALERT_EMAIL_TO=__SET_RECIPIENTS__   # comma-separated
    
    // For testing - Does not proceed with sending an email
    NOOKO_ALERT_EMAIL_DRY_RUN=1

    // 
    NOOKO_ALERT_EMAIL_DEBUG=0`
Notes:

Do not commit real tokens or personal recipient addresses.

**NOTE:**

- For safe local testing, keep **NOOKO_ALERT_EMAIL_DRY_RUN=1** (it prints the request instead of sending email).

- To actually send: set **NOOKO_ALERT_EMAIL_DRY_RUN=0** and ensure the correct token is available in the runtime environment.

## 9) Demo / local test run
    python examples/demo_run.py

***(Ensure you installed the package first, e.g. pip install -e .)***

## 10) Pricing updates (when prices change)
If installed editable from a folder path (ZIP install)
If you replace/update the files in the same folder path you installed from:

✅ Usually no reinstall needed (editable install points to that folder)

If the folder path changes, reinstall using the new path:

    pip install -e C:\temp\Final-Cost-Calculator-new

If installed from a Git repo

**Pull latest changes:**

    git pull

✅ Usually no reinstall needed. Re-run ***pip install -e .*** only if dependencies or package structure changed.

## 11) Quick uninstall
pip uninstall ai-cost-calculator

## Pricing JSON (where to find it + how to update it)

### Where the default pricing is stored
The default pricing file is bundled inside the package:

`src/ai_cost_calculator/model_pricing.json`

This file is read automatically by `get_pricing()` when `pricing_path` is not provided.

### How to update pricing (recommended workflow)
1) Open and edit:
    
    `src/ai_cost_calculator/model_pricing.json`

2) Update/add the model entry (and aliases if needed).
3) Save the file and commit the change.

### Keeping pricing up to date (if installed from Git)
If you installed the calculator from a Git repository, pull the latest changes regularly so you always use the newest pricing:

    cd /path/to/Final-Cost-Calculator
    git pull
    
If your application installed it in editable mode **(pip install -e ...)**, pricing updates take effect immediately after pulling.

**Optional:** override pricing without changing the package
If you want to use your own pricing JSON (without modifying the package), pass pricing_path:

    out = estimate_cost(payload, pricing_path="path/to/model_pricing.json")
This is useful if pricing changes frequently and you want to manage pricing separately.


