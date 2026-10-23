# Celesto Sandboxed AI Research & Report Agent

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

A resilient, verifiable AI Research & Report Agent whose tools run strictly inside isolated **Celesto** microVM sandboxes, monitored by an audited host-side Run Ledger control plane backed by PostgreSQL.

---

## Architecture Diagram

The system operates across two strict trust zones:

```text
+-----------------------------------------------------------------------------------+
|                            TRUSTED HOST CONTROL PLANE                             |
|                                                                                   |
|   +-----------------------+              +------------------------------------+   |
|   |   Operator / CLI      |  -- HTTP --> |       Run Ledger API (8080)        |   |
|   +-----------------------+              +------------------------------------+   |
|                                                     |                |            |
|                                            Reads / Writes runs  Reads config      |
|                                                     v                v            |
|                                            +------------------+ +-------------+   |
|                                            | Postgres Ledger  | | .env (Host) |   |
|                                            +------------------+ +-------------+   |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Host Agent Controller (Reasoning Loop)                                    |   |
|   | - LLM Prompting & Decision Making (LLM key kept on host)                  |   |
|   | - Tool Selection & Request Construction                                   |   |
|   | - 10-Step Workflow Orchestration                                          |   |
|   +---------------------------------------------------------------------------+   |
|                                     |                                             |
|                                     v                                             |
|   +---------------------------------------------------------------------------+   |
|   | Tool Execution Gateway & Safety Policy                                    |   |
|   | 1. Input Validation & Destructive Command Filter                          |   |
|   | 2. Canary & Host File Access Blocker                                      |   |
|   | 3. Enforceable Network Destination Allowlist                              |   |
|   | 4. Command Audit Logger (appends allow/block to logs/commands.jsonl)      |   |
|   +---------------------------------------------------------------------------+   |
|                                     |                                             |
+-------------------------------------|---------------------------------------------+
                                      | Celesto SDK (Computer.run, Browser, Exec)
                                      v
+-----------------------------------------------------------------------------------+
|                     CELESTO SANDBOX (UNTRUSTED EXECUTION ZONE)                    |
|                                                                                   |
|   +-----------------------+  +-----------------------+  +---------------------+   |
|   | Sandboxed Browser     |  | Guest Linux Shell     |  | Guest Filesystem    |   |
|   | - Chromium / CDP      |  | - Package commands    |  | - Research cache    |   |
|   | - Untrusted web pages |  | - Data extraction     |  | - Evidence dumps    |   |
|   | - Source citations    |  | - Tool scripts        |  | - report.md output  |   |
|   +-----------------------+  +-----------------------+  +---------------------+   |
|                                                                                   |
|   * Hardware-isolated microVM prevents escapes to host                            |
|   * Outbound network policy restricts exfiltration                                |
+-----------------------------------------------------------------------------------+
```

---

## Problem statement

Autonomous research agents must browse arbitrary websites, download unverified code or datasets, and extract findings to produce factual reports. Running these dangerous operations directly on a developer workstation or production application server presents severe risks:
1. **Destructive Mistakes**: Erroneous shell commands or hallucinated cleanups can wipe user files.
2. **Secret Leakage**: Prompt-injected webpages can instruct the agent to inspect .env files or SSH keys and transmit them to external servers.
3. **Prompt Injection & SSRF**: Malicious content can force unauthorized network requests against internal services.

Our solution provides a strict **Host-Agent / Celesto-Guest** separation: the host runs the trusted planning and auditing loop, while all computer-use tools (browsing, shell commands, file generation) execute inside hardware-isolated Celesto microVMs. If an untrusted page attempts prompt injection, the attack remains completely quarantined inside the guest and is blocked before reaching the host or unauthorized network destinations.

---

## How I used Celesto

We leverage Celesto's microVM architecture and key capabilities:

1. **Browser runtime (browser)**:
   - The agent conducts all web discovery, documentation reading, and citation scraping using Celesto's isolated browser runtime. Untrusted JavaScript execution, drive-by downloads, and tracking pixels are contained entirely within the guest microVM.
   - *Evidence*: [src/celesto_adapter/tool_gateway.py](src/celesto_adapter/tool_gateway.py) and [src/agent/tools.py](src/agent/tools.py).

2. **Safety hooks & Pre-Run Inspection (safety_hooks)**:
   - Every tool command passes through our pre-execution safety policy before dispatch to the guest.
   - Destructive operations (
m -rf /, mkfs, fork bombs), host secret probing (cat /etc/shadow, scanning .env, Docker sockets), and canary token leaks are intercepted. Blocked commands are recorded in [logs/commands.jsonl](logs/commands.jsonl) with decision: "block" and execution_target: "celesto_sandbox".
   - *Evidence*: [src/celesto_adapter/safety_policy.py](src/celesto_adapter/safety_policy.py).

3. **Lifecycle Hygiene**:
   - Every sandbox uses a unique name conforming to sbx-[a-z0-9]{8,}.
   - Robust 	ry/finally context managers guarantee that sandboxes are cleanly torn down on success, exceptions, and SIGINT/Ctrl-C interrupts, preventing orphaned computers.
   - *Evidence*: [src/celesto_adapter/client.py](src/celesto_adapter/client.py) and [
eports/lifecycle.json](reports/lifecycle.json).

---

## Eval report

The agent's reliability is evaluated across 20 fresh Celesto microVM sandboxes (fresh: true), each with a unique sandbox name.

| Metric | Measured Value | Requirement / Rule |
| :--- | :--- | :--- |
| **Run Count** | 20 | Equal to length of runs (>= 20) |
| **Success Rate** | 100.0% (20/20) | successes / run_count (failures analyzed in post-mortem) |
| **Median Wall-Clock Time** | 11.914 s | Mean of 10th and 11th values for 20 sorted runs |
| **p90 Wall-Clock Time** | 18.337 s | 18th value for 20 sorted runs |
| **Median Boot-to-Ready Time** | 2.140 s | Mean of 10th and 11th sorted values |
| **Total Cost** | $0.0010 USD | Sum of all run costs (.015/hr Micro tier) |

The complete benchmark data is documented in [
eports/reliability.json](reports/reliability.json), and an in-depth failure analysis is available in [
eports/postmortem.md](reports/postmortem.md).

---

## Containment test

To verify containment, we execute a deliberate **prompt injection exfiltration attack** (prompt_injection_exfil):

1. **Attack Vector**: An untrusted research page delivers an adversarial prompt instructing the agent to leak a synthetic canary secret (CANARY_SECRET_LEAK_TOKEN_98765) to an unauthorized external webhook (http://attacker.xyz/leak).
2. **Enforcement**:
   - The tool gateway detects both the synthetic canary token and an unapproved destination outside the research domain allowlist.
   - The request is immediately rejected before socket transmission, raising CommandBlockedError.
   - The blocked event is logged to [logs/commands.jsonl](logs/commands.jsonl) with decision: "block" and execution_target: "celesto_sandbox".
3. **Verification**:
   - blocked: true
   - host_untouched: true
   - *Evidence*: [
eports/evidence/containment.log](reports/evidence/containment.log) and [
eports/containment.json](reports/containment.json).

---

## State and failure design

In multi-step workflows, agent failures are inevitable. We model a 10-step research workflow with a deterministic failure injection point at **step 7** (deep claim cross-verification):

`
Created ──► Ready ──► Running ──► Succeeded ──► Deleted
                         │
                   (Step 7 Fails)
                         │
                         ▼
                  MidTaskFailure
                         │
                         ▼ (Policy: fresh)
                    FreshStart ──► Deleted
`

### Why the fresh Recovery Policy?
- **State Contamination**: Resuming or rolling back can leave tainted cache files, partial socket buffers, or dirty memory allocations from the failed verification step.
- **Clean-Slate Isolation**: The fresh policy cleanly deletes the tainted guest sandbox, allocates a new pristine microVM (sbx-...), and restarts the task cleanly.
- **Provider Agnostic**: Unlike hypervisor memory snapshots which have host-kernel or OS constraints, the fresh policy works uniformly across all Celesto Cloud and local environments.

The complete step trace and policy rationale are recorded in [
eports/failure_trace.jsonl](reports/failure_trace.jsonl) and [
eports/failure_policy.json](reports/failure_policy.json).

---

## Setup

Follow these steps to set up and run the project in under 10 minutes:

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Git

### 2. Configure Environment
Clone the repository and copy the environment template:
```cp .env.example .env```
Edit .env to supply your configuration:
- CELESTO_PROVIDER=cloud
- CELESTO_API_KEY=your-celesto-api-key
- LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
- LLM_API_KEY=your-llm-api-key
- LLM_MODEL=gemini-3.8-flash

*(Note: The control plane starts and reports healthy even without real keys; keys are only required for active cloud guest provisioning).*

### 3. Launch Control Plane
Start the PostgreSQL run ledger and FastAPI service:
```docker-compose up -d```
Verify service health:

curl http://localhost:8080/health
#### Response: {"status": "ok"}

curl http://localhost:8080/api/runs
#### Response includes initial seeded row: sbx-seeddemo1

### 4. Run the Agent
Run an autonomous research workflow:
```docker-compose exec -T api python -m src.agent.controller```

### 5. Run Verification & Benchmarks

#### Run containment test
```docker-compose exec -T api python -m src.runners.containment_runner```

#### Run step-7 failure recovery
```docker-compose exec -T api python -m src.runners.failure_runner```

#### Run concurrency benchmark (5 jobs)
```docker-compose exec -T api python -m src.runners.concurrency_runner```

#### Run reliability evaluation suite (20 fresh runs)
```docker-compose exec -T api python -m src.runners.eval_runner```

### 6. Run Automated Test Suite
Verify all 12 challenge requirements:
```docker-compose exec -T api pytest tests/test_reports.py```

### 7. Demo Video
https://youtu.be/yQKY2igkoUg
