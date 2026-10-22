# Demo Video Walkthrough Script (Under 3 Minutes)

This script provides the step-by-step recording sequence for the Celesto Hackathon submission video.

## Scene 1: Control Plane Initialization (0:00 - 0:30)
1. **Action**: Open terminal.
2. **Command**: docker-compose up -d
3. **Show**: Both celesto-ledger (Postgres) and celesto-api (FastAPI) become healthy within seconds.
4. **Narration**:
   > \"Here we launch the trusted control plane with Docker Compose. The control plane runs a FastAPI Run Ledger and PostgreSQL, which initializes idempotently with our verification seed row. No agent tool runs on the host—the host only decides and audits.\"

## Scene 2: Ledger Health & Seed Verification (0:30 - 0:50)
1. **Action**: Curl the API.
2. **Command**:
   `ash
   curl -s http://localhost:8080/health
   curl -s http://localhost:8080/api/runs | jq .
   `
3. **Show**: Status ok and the initial seed row sbx-seeddemo1 with execution_target: celesto_sandbox.
4. **Narration**:
   > \"The health check returns OK, and the ledger shows our audited seed sandbox. The ledger strictly enforces that execution targets must be Celesto sandboxes rather than host processes.\"

## Scene 3: Agent Research Workflow Inside Celesto Sandbox (0:50 - 1:45)
1. **Action**: Trigger the research agent on a topic:
   `ash
   python -m src.agent.controller
   `
2. **Show**:
   - The host agent controller provisions Celesto sandbox sbx-<id>.
   - The browser navigates to public documentation inside the microVM.
   - Show the Celesto viewer / console displaying the guest computer running commands in real-time.
   - Sourced Markdown report eport.md generated in /tmp/research/report.md.
3. **Narration**:
   > \"The host agent prompts the LLM and selects tools, but all computer work—browser navigation, data scraping, and Markdown report compilation—happens inside a Celesto microVM. The guest computer is hardware-isolated via KVM, ensuring zero host leakage.\"

## Scene 4: Real Safety Enforcement & Containment Test (1:45 - 2:20)
1. **Action**: Run the containment attack test:
   `ash
   python -m src.runners.containment_runner
   `
2. **Show**:
   - Injected prompt instructs exfiltration of canary token CANARY_SECRET_LEAK_TOKEN_98765 to http://attacker.xyz/leak.
   - Tool gateway intercepts the command, logs decision: block to logs/commands.jsonl, and raises CommandBlockedError.
   - Show eports/evidence/containment.log confirming host is untouched.
3. **Narration**:
   > \"When untrusted web content injects a malicious prompt to exfiltrate a secret canary, our pre-execution safety policy and network destination filters intercept the request before socket transmission. The attempt is logged as blocked in our audit trail, and the host remains completely untouched.\"

## Scene 5: Step-7 Recovery Policy & Teardown Hygiene (2:20 - 2:50)
1. **Action**: Trigger the step-7 failure simulation:
   `ash
   python -m src.runners.failure_runner
   `
2. **Show**:
   - Trace in eports/failure_trace.jsonl showing step 7 failure.
   - policy_applied: fresh tears down the tainted guest and launches a clean replacement sandbox to complete the task.
   - Both sandboxes deleted cleanly.
3. **Narration**:
   > \"When an agent fails halfway at step 7, we don't keep dirty state. Our 'fresh' recovery policy cleanly tears down the tainted sandbox and provisions a pristine microVM to complete the run. Every single sandbox is guaranteed deleted on success, failure, or interrupt.\"

## Scene 6: Wrap-up & Metrics (2:50 - 3:00)
1. **Action**: Show eports/reliability.json summary stats.
2. **Narration**:
   > \"With full command auditing, sub-second microVM boot times, and strict containment, Celesto provides the secure computer primitive modern agents need.\"
