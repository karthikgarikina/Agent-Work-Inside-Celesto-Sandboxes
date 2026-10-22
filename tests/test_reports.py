import json
import math
import re
from pathlib import Path
import pytest

SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")


def test_core_req_01_docker_compose_and_dockerfile():
    """1. The trusted control plane starts with one command and becomes healthy without manual migration."""
    compose_path = Path("docker-compose.yml")
    dockerfile_path = Path("Dockerfile")
    assert compose_path.exists(), "docker-compose.yml must exist"
    assert dockerfile_path.exists(), "Dockerfile must exist"

    content = compose_path.read_text(encoding="utf-8-sig")
    assert "api:" in content, "docker-compose.yml must define 'api' service"
    assert "ledger:" in content, "docker-compose.yml must define 'ledger' service"
    assert "8080:8080" in content, "api service must publish port 8080"
    assert "pg_isready" in content, "ledger healthcheck must use pg_isready"
    assert "http://localhost:8080/health" in content, "api healthcheck must curl http://localhost:8080/health"
    assert "./seeds" in content, "ledger must mount ./seeds init path"
    assert "service_healthy" in content, "api must wait until ledger is healthy"
    for field in ["interval:", "timeout:", "retries:", "start_period:"]:
        assert content.count(field) >= 2, f"Both healthchecks must configure {field}"


def test_core_req_02_env_example():
    """2. Environment variables are documented with placeholders, and a live .env is not committed."""
    env_example = Path(".env.example")
    gitignore = Path(".gitignore")
    assert gitignore.exists(), ".gitignore must exist"
    assert ".env" in gitignore.read_text(encoding="utf-8-sig"), ".gitignore must contain .env"

    content = env_example.read_text(encoding="utf-8-sig")
    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT",
    ]
    for key in required_keys:
        assert f"{key}=" in content, f".env.example must contain key {key}"


def test_core_req_03_problem_statement():
    """3. The project states who has the problem, what the agent does on a computer, and what output proves it."""
    prob_path = Path("reports/problem.json")
    assert prob_path.exists(), "reports/problem.json must exist"
    data = json.loads(prob_path.read_text(encoding="utf-8-sig"))

    assert "who" in data and len(data["who"]) >= 40, "who must be at least 40 characters"
    assert "agent_work" in data and len(data["agent_work"]) >= 40, "agent_work must be at least 40 characters"
    assert "proof_output" in data and len(data["proof_output"]) >= 20, "proof_output must be at least 20 characters"
    assert data.get("idea_source") in ("idea_bank", "original"), "idea_source must be idea_bank or original"


def test_core_req_04_command_audit_log():
    """4. Every command the agent requests is audited, and execution target is celesto_sandbox."""
    log_path = Path("logs/commands.jsonl")
    assert log_path.exists(), "logs/commands.jsonl must exist"

    lines = [l.strip() for l in log_path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    assert len(lines) >= 1, "logs/commands.jsonl must have at least one line"

    for idx, line in enumerate(lines):
        entry = json.loads(line)
        assert "ts" in entry, f"Line {idx} missing ts"
        assert SANDBOX_REGEX.match(entry["sandbox_name"]), f"Line {idx} invalid sandbox_name: {entry['sandbox_name']}"
        assert entry["command"].strip(), f"Line {idx} empty command"
        assert entry["decision"] in ("allow", "block"), f"Line {idx} decision must be allow or block"
        assert entry["execution_target"] == "celesto_sandbox", f"Line {idx} execution_target must be exactly celesto_sandbox"


def test_core_req_05_capabilities():
    """5. The agent uses at least two differentiating Celesto capabilities, each justified and pointed at evidence."""
    cap_path = Path("reports/capabilities.json")
    assert cap_path.exists(), "reports/capabilities.json must exist"
    data = json.loads(cap_path.read_text(encoding="utf-8-sig"))

    allowed_ids = {
        "persistence", "snapshots", "celestofs", "browser",
        "published_ports", "network_policy", "safety_hooks",
        "host_mounts", "coding_agent_preset", "agentor_durable",
    }
    caps = data.get("capabilities", [])
    assert len(caps) >= 2, "Must specify at least 2 capabilities"

    seen_ids = set()
    for cap in caps:
        cid = cap.get("id")
        assert cid in allowed_ids, f"Capability {cid} not in allowed set"
        assert cid not in seen_ids, f"Duplicate capability {cid}"
        seen_ids.add(cid)
        assert len(cap.get("why", "")) >= 80, f"Capability {cid} why must be at least 80 chars"
        ev_path = Path(cap.get("evidence_path", ""))
        assert ev_path.exists(), f"Evidence path {ev_path} for capability {cid} does not exist"


def test_core_req_06_lifecycle():
    """6. Sandboxes are cleaned up on success, failure, and interrupt, and names cannot collide."""
    lc_path = Path("reports/lifecycle.json")
    assert lc_path.exists(), "reports/lifecycle.json must exist"
    data = json.loads(lc_path.read_text(encoding="utf-8-sig"))

    assert data.get("cleanup_on_success") is True
    assert data.get("cleanup_on_failure") is True
    assert data.get("cleanup_on_interrupt") is True

    names = data.get("sandbox_names", [])
    assert len(names) >= 1, "sandbox_names must be non-empty"
    assert len(names) == len(set(names)), "sandbox_names must be unique"

    # Read names from command logs and reliability
    log_names = set()
    log_path = Path("logs/commands.jsonl")
    if log_path.exists():
        for l in log_path.read_text(encoding="utf-8-sig").splitlines():
            if l.strip():
                log_names.add(json.loads(l)["sandbox_name"])

    rel_names = set()
    rel_path = Path("reports/reliability.json")
    if rel_path.exists():
        rel_data = json.loads(rel_path.read_text(encoding="utf-8-sig"))
        for r in rel_data.get("runs", []):
            rel_names.add(r["sandbox_name"])

    valid_pool = log_names.union(rel_names)
    for name in names:
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox_name format: {name}"
        assert name in valid_pool, f"Sandbox {name} must appear in logs/commands.jsonl or reports/reliability.json"


def test_core_req_07_reliability_and_postmortem():
    """7. Reliability is measured on at least 20 fresh sandboxes, and summary statistics match rows."""
    rel_path = Path("reports/reliability.json")
    assert rel_path.exists(), "reports/reliability.json must exist"
    data = json.loads(rel_path.read_text(encoding="utf-8-sig"))

    runs = data.get("runs", [])
    n = len(runs)
    assert n >= 20, f"Expected at least 20 runs, got {n}"
    assert data.get("run_count") == n, "run_count must equal length of runs"

    seen_names = set()
    for r in runs:
        assert r["fresh"] is True, "fresh must be True"
        sname = r["sandbox_name"]
        assert SANDBOX_REGEX.match(sname), f"Invalid sandbox_name {sname}"
        assert sname not in seen_names, f"Duplicate sandbox name {sname}"
        seen_names.add(sname)

    # Success rate
    successes = sum(1 for r in runs if r["success"] is True)
    expected_success_rate = successes / float(n)
    assert abs(data["success_rate"] - expected_success_rate) <= 0.001

    # Sorted wall_clock_s
    wall_clocks = [r["wall_clock_s"] for r in runs]
    assert wall_clocks == sorted(wall_clocks), "runs must be sorted by wall_clock_s ascending"

    # Median wall clock
    if n % 2 == 0:
        expected_median_wall = (wall_clocks[(n // 2) - 1] + wall_clocks[n // 2]) / 2.0
    else:
        expected_median_wall = wall_clocks[n // 2]
    assert abs(data["median_wall_clock_s"] - expected_median_wall) <= 0.001

    # p90 wall clock
    p90_idx = math.ceil(0.90 * n) - 1
    expected_p90 = wall_clocks[p90_idx]
    assert abs(data["p90_wall_clock_s"] - expected_p90) <= 0.001

    # Median boot to ready
    boots = sorted([r["boot_to_ready_s"] for r in runs])
    if n % 2 == 0:
        expected_median_boot = (boots[(n // 2) - 1] + boots[n // 2]) / 2.0
    else:
        expected_median_boot = boots[n // 2]
    assert abs(data["median_boot_to_ready_s"] - expected_median_boot) <= 0.001

    # Total cost
    expected_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - expected_cost) <= 0.01

    # Postmortem
    pm_path = Path(data.get("postmortem_path", ""))
    assert pm_path.exists(), "postmortem_path file must exist"
    assert len(pm_path.read_text(encoding="utf-8-sig")) >= 200, "postmortem must be at least 200 characters"


def test_core_req_08_containment():
    """8. One deliberate guest misbehavior is stopped, and host is untouched."""
    c_path = Path("reports/containment.json")
    assert c_path.exists(), "reports/containment.json must exist"
    data = json.loads(c_path.read_text(encoding="utf-8-sig"))

    assert data.get("attack") in ("prompt_injection_exfil", "destructive_command", "suspicious_package")
    assert data.get("blocked") is True
    assert data.get("host_untouched") is True

    ev_paths = data.get("evidence_paths", [])
    assert len(ev_paths) >= 1
    for ep in ev_paths:
        assert Path(ep).exists(), f"Evidence path {ep} does not exist"


def test_core_req_09_failure_recovery_policy():
    """9. Step 7 failure follows recovery policy, trace matches."""
    pol_path = Path("reports/failure_policy.json")
    assert pol_path.exists(), "reports/failure_policy.json must exist"
    data = json.loads(pol_path.read_text(encoding="utf-8-sig"))

    assert data.get("failed_step") == 7
    assert data.get("total_steps") == 10
    policy = data.get("policy")
    assert policy in ("resume", "rollback", "fresh")
    assert len(data.get("rationale", "")) >= 200

    trace_path = Path(data.get("trace_path", ""))
    assert trace_path.exists(), "trace_path must exist"
    lines = [l.strip() for l in trace_path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    found_policy_applied = False
    for line in lines:
        ev = json.loads(line)
        if ev.get("event") == "policy_applied" and ev.get("policy") == policy:
            found_policy_applied = True
            break
    assert found_policy_applied, f"Expected event 'policy_applied' with policy '{policy}' in trace"


def test_core_req_10_concurrency():
    """10. At least five jobs run in uniquely named sandboxes, with notes on limits."""
    c_path = Path("reports/concurrency.json")
    assert c_path.exists(), "reports/concurrency.json must exist"
    data = json.loads(c_path.read_text(encoding="utf-8-sig"))

    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "Must have at least 5 jobs"

    seen_names = set()
    for job in jobs:
        sname = job.get("sandbox_name", "")
        assert SANDBOX_REGEX.match(sname), f"Invalid sandbox_name {sname}"
        assert sname not in seen_names, f"Duplicate job sandbox {sname}"
        seen_names.add(sname)
        assert job.get("started_at"), "started_at must be non-empty"

    notes = data.get("breakage_notes", "")
    assert len(notes) >= 40, "breakage_notes must be at least 40 characters"


def test_core_req_11_api_and_seed():
    """11. The ledger API reports health, lists runs, and accepts a sandbox run row."""
    from fastapi.testclient import TestClient
    from src.api.main import app

    client = TestClient(app)

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    # List runs includes sbx-seeddemo1
    res = client.get("/api/runs")
    assert res.status_code == 200
    runs = res.json()
    assert isinstance(runs, list)
    names = [r["sandbox_name"] for r in runs]
    assert "sbx-seeddemo1" in names, "GET /api/runs must include sbx-seeddemo1"

    # Valid run creation -> 201
    valid_payload = {
        "run_id": "run-testvalid001",
        "sandbox_name": "sbx-testvalid01",
        "problem_id": "prob-test",
        "state": "running",
        "execution_target": "celesto_sandbox",
    }
    res = client.post("/api/runs", json=valid_payload)
    assert res.status_code == 201
    assert res.json()["sandbox_name"] == "sbx-testvalid01"

    # Invalid execution_target -> 400
    invalid_target = {
        "run_id": "run-testbadtarget",
        "sandbox_name": "sbx-testbad01",
        "problem_id": "prob-test",
        "state": "running",
        "execution_target": "host",
    }
    res = client.post("/api/runs", json=invalid_target)
    assert res.status_code == 400

    # Invalid sandbox name -> 400
    bad_name = {
        "run_id": "run-testbadname",
        "sandbox_name": "bad_name",
        "problem_id": "prob-test",
        "state": "running",
        "execution_target": "celesto_sandbox",
    }
    res = client.post("/api/runs", json=bad_name)
    assert res.status_code == 400

    # Invalid state -> 400
    bad_state = {
        "run_id": "run-testbadstate",
        "sandbox_name": "sbx-testbadstate01",
        "problem_id": "prob-test",
        "state": "invalid_state",
        "execution_target": "celesto_sandbox",
    }
    res = client.post("/api/runs", json=bad_state)
    assert res.status_code == 400


def test_core_req_12_readme_headings():
    """12. README.md contains the exact required phrases."""
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md must exist"
    content = readme_path.read_text(encoding="utf-8-sig")

    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup",
    ]
    for phrase in required_phrases:
        assert phrase in content, f"README.md missing required phrase: '{phrase}'"
