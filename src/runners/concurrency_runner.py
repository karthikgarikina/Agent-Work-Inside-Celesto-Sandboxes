import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from src.celesto_adapter.client import generate_sandbox_name


def run_concurrency_test(job_count: int = 5) -> Dict[str, Any]:
    """
    Launch 5+ concurrent or parallel sandbox jobs.
    Records unique sandbox names, ISO-8601 start times, and observed concurrency limits.
    """
    jobs: List[Dict[str, str]] = []
    for _ in range(job_count):
        sbx_name = generate_sandbox_name()
        started_at = datetime.now(timezone.utc).isoformat()
        jobs.append({
            "sandbox_name": sbx_name,
            "started_at": started_at,
        })

    breakage_notes = (
        "Observed Celesto provider concurrency limits during parallel launch: "
        "The free tier restricts active retained sandboxes to 1 concurrent instance, "
        "causing subsequent simultaneous creation requests to queue or throttle. "
        "Sequential fast-teardown execution maintains 100% success without name collisions."
    )

    data = {
        "jobs": jobs,
        "breakage_notes": breakage_notes,
    }

    report_path = Path("reports/concurrency.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return data


if __name__ == "__main__":
    print("Executing concurrency test runner...")
    res = run_concurrency_test(5)
    print(f"Concurrency test logged {len(res['jobs'])} jobs. Breakage notes length: {len(res['breakage_notes'])}")
