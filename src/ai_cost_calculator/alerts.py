import json
import os
import requests
from typing import Any, Dict, Optional, Tuple

class EmailSendError(RuntimeError):
    """Raised when the internal email API call fails."""


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default

def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on")

def _parse_email_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]

def send_internal_email_generic(
    *,
    to_email: str,
    subject: str,
    body_html: str,
    action_url: Optional[str] = None,
    action_text: Optional[str] = None,
    base_url: Optional[str] = None,
    internal_token: Optional[str] = None,
    timeout_s: float = 10.0,
    dry_run: bool = False,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Sends a 'generic' email via Nooko internal email API.

    Dry-run mode:
      - Does NOT call the API
      - Prints payload (if debug=True)
      - Returns {"success": True, "dry_run": True, ...}

    Raises:
      - ValueError for missing inputs
      - EmailSendError for network/HTTP/JSON errors (when dry_run=False)
    """

    if not to_email or not to_email.strip():
        raise ValueError("to_email is required")
    if not subject or not subject.strip():
        raise ValueError("subject is required")
    if not body_html or not body_html.strip():
        raise ValueError("body_html is required")

    url = "https://app.nooko.ai/internal/email/send"

    context: Dict[str, Any] = {"subject": subject, "body": body_html}
    if action_url:
        context["action_url"] = action_url
        context["action_text"] = action_text or "Open"

    payload = {
        "to_email": to_email,
        "subject": subject,
        "template": "generic",
        "context": context,
    }

    if dry_run:
        if debug:
            print("[EMAIL][DRY_RUN] Would POST:", url)
            print("[EMAIL][DRY_RUN] Payload:\n", json.dumps(payload, indent=2, ensure_ascii=False))
        return {
            "success": True,
            "dry_run": True,
            "url": url,
            "payload": payload,
            "message": "Dry-run: email not sent",
        }

    token = internal_token or _env("NOOKO_INTERNAL_TOKEN")
    if not token:
        raise ValueError("Missing X-Internal-Token (set NOOKO_INTERNAL_TOKEN or pass internal_token=...)")

    if debug:
        print("[EMAIL] POST:", url)
        print("[EMAIL] To:", to_email)
        print("[EMAIL] Subject:", subject)

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": token,
            },
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        raise EmailSendError(f"Email API connection error: {e}") from e

    if not resp.ok:
        raise EmailSendError(f"Email API HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        return resp.json()
    except Exception as e:
        raise EmailSendError(f"Email API returned non-JSON response: {resp.text[:300]}") from e

def build_unknown_models_email(*, models: list[Dict[str, Any]]) -> Tuple[str, str]:
    model_names = sorted({m.get("model") for m in models if isinstance(m, dict) and m.get("model")})
    bullets = "".join(f"<li><code>{name}</code></li>" for name in model_names)
    subject = f"[AI Cost Calculator] Unknown model(s): {', '.join(model_names[:3])}" + (
        f" (+{len(model_names) - 3} more)" if len(model_names) > 3 else ""
    )

    raw_models = models
    if isinstance(raw_models, str):
        raw_models = json.loads(raw_models)

    pretty = json.dumps(raw_models, indent=2, ensure_ascii=False)

    body = (
        "<p>Hello,</p>"
        "<p>The <strong>AI Cost Calculator</strong> could not compute cost for one or more AI usage records because the model name "
        "was not found in the pricing JSON.</p>"
        "<p><strong>Action needed:</strong> Please add pricing (or an alias mapping) for the model(s) below so future transactions "
        "can be priced correctly.</p>"
        "<p><strong>Unknown model(s) detected:</strong></p>"
        f"<ul>{bullets}</ul>"
        "<p><strong>Details (raw payload excerpt):</strong></p>"
        "<pre style='background:#f6f8fa;padding:12px;border-radius:6px;overflow:auto;white-space:pre;'>"
        + pretty +
        "</pre>"
        "<p>Thank you.</p>"
    )

    return subject, body

def notify_unknown_models_if_configured(
    *,
    unknown_models: list[Dict[str, Any]],
    base_url: Optional[str] = None,
    internal_token: Optional[str] = None,
    to_emails: Optional[str] = None,
    dry_run: Optional[bool] = None,
    debug: Optional[bool] = None,
) -> bool:
    """
    Sends alert email(s) ONLY if recipient list exists.
    In dry_run=True: token is NOT required; it will print payload and return True (if recipients exist).

    Returns:
      True if at least one email was successfully sent (or dry-run simulated).
      False if not configured OR all sends failed.
    """
    if not unknown_models:
        return False

    # default flags from env if not provided
    if dry_run is None:
        dry_run = _env_bool("NOOKO_ALERT_EMAIL_DRY_RUN", False)
    if debug is None:
        debug = _env_bool("NOOKO_ALERT_EMAIL_DEBUG", False)

    recipients_raw = to_emails or _env("NOOKO_ALERT_EMAIL_TO")
    recipients = _parse_email_list(recipients_raw)
    if not recipients:
        if debug:
            print("[EMAIL] No recipients configured (NOOKO_ALERT_EMAIL_TO / to_emails). Skipping.")
        return False

    subject, body = build_unknown_models_email(models=unknown_models)

    any_sent = False
    for to_email in recipients:
        try:
            # Token only needed if not dry-run
            token = internal_token or _env("NOOKO_INTERNAL_TOKEN")

            if (not dry_run) and (not token):
                if debug:
                    print("[EMAIL] Missing token and dry_run=False. Skipping send.")
                continue

            send_internal_email_generic(
                to_email=to_email,
                subject=subject,
                body_html=body,
                base_url=base_url,
                internal_token=token,
                dry_run=bool(dry_run),
                debug=bool(debug),
            )
            any_sent = True
        except Exception as e:
            print(f"Failed to send unknown models alert email to {to_email}: {e}")
            continue

    return any_sent
