import csv
import sys
import platform
import datetime as dt
from pathlib import Path

import pytest


# -----------------------------
# 1) Make project root importable
# -----------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# -----------------------------
# 2) CSV reporting (informative)
# -----------------------------
def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def pytest_addoption(parser):
    parser.addoption(
        "--csv-report",
        action="store",
        default="reports/test_report.csv",
        help="Path to write CSV test report (default: reports/test_report.csv)",
    )
    parser.addoption(
        "--csv-append",
        action="store_true",
        default=False,
        help="Append to existing CSV instead of overwriting.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config._csv_rows = []
    config._run_meta = {
        "run_id": dt.datetime.now().strftime("%Y%m%d_%H%M%S"),
        "run_started_at": _now_iso(),
        "cwd": str(Path.cwd()),
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "pytest_version": getattr(pytest, "__version__", ""),
    }


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    # Identify file/line
    file_path = str(getattr(report, "fspath", "") or "")
    line_no = ""
    try:
        line_no = str(item.location[1] + 1)  # 1-based
    except Exception:
        pass

    # Markers
    try:
        markers = ",".join(sorted({m.name for m in item.iter_markers()}))
    except Exception:
        markers = ""

    # Param id (if any)
    param_id = ""
    try:
        if "[" in report.nodeid and report.nodeid.endswith("]"):
            param_id = report.nodeid.split("[", 1)[1].rstrip("]")
    except Exception:
        pass

    # Status
    if report.passed:
        status = "passed"
    elif report.failed:
        status = "failed"
    elif report.skipped:
        status = "skipped"
    else:
        status = "unknown"

    # Details (traceback for failures, skip reason, etc.)
    details = ""
    if report.failed or report.skipped:
        try:
            details = str(report.longrepr)
        except Exception:
            details = ""

    # Duration
    duration = ""
    try:
        duration = f"{report.duration:.6f}"
    except Exception:
        pass

    item.config._csv_rows.append(
        {
            # run meta
            **item.config._run_meta,
            # per row
            "timestamp": _now_iso(),
            "nodeid": report.nodeid,
            "phase": report.when,          # setup/call/teardown
            "status": status,
            "duration_sec": duration,
            "file": file_path,
            "line": line_no,
            "markers": markers,
            "param": param_id,
            "details": details,
        }
    )


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    report_path = Path(config.getoption("--csv-report")).resolve()
    append = bool(config.getoption("--csv-append"))

    report_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "run_id",
        "run_started_at",
        "cwd",
        "python",
        "platform",
        "pytest_version",
        "timestamp",
        "nodeid",
        "phase",
        "status",
        "duration_sec",
        "file",
        "line",
        "markers",
        "param",
        "details",
    ]

    write_header = True
    if append and report_path.exists() and report_path.stat().st_size > 0:
        write_header = False

    mode = "a" if append else "w"
    with report_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if write_header:
            writer.writeheader()
        for row in getattr(config, "_csv_rows", []):
            writer.writerow(row)

    tr = config.pluginmanager.get_plugin("terminalreporter")
    if tr:
        tr.write_line(f"CSV report written to: {report_path}")
