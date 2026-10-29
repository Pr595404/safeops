# SafeOps

[![CI](https://github.com/Prince/safeops/actions/workflows/ci.yml/badge.svg)](https://github.com/Prince/safeops/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A production-ready incident investigation assistant built for the **AWS Strands Decider Agent Hackathon**.

SafeOps autonomously investigates **synthetic cloud incidents** using strictly guarded **read-only mock tools**. It combines a deterministic, zero-model policy layer with the **Strands Decider 2B** fast-inference classification model, steering **Amazon Bedrock** generative reasoning to prevent destructive mutations, hallucinated parameters, and premature execution.

---

## 1. Project Overview & Key Features

- **Multi-Layer Defense Guardrails**:
  1. **Deterministic Policy (Layer 1)**: Intercepts destructive actions (`terminate_instance`, `reboot_instance`, `delete_volume`, `execute_shell`) in pure code with zero model latency and 100% fail-closed guarantees.
  2. **Strands Decider 2B Classification (Layer 2)**: Classifies proposed tool calls via high-speed `noul` (yes/no) questions (`args_grounded`, `premature`, `diagnostic_appropriate`).
  3. **Strands Intervention Handler (Layer 3)**: Translates Decider probability scores into typed Strands actions (`Proceed`, `Guide`, `Deny`).
- **Zero-Cost & Offline Testing**: Core policy, tool execution, and guardrail evaluation run with ₹0 cost, zero AWS resources, and zero external API dependencies.
- **Canary Tooling**: Includes a safe stub for `terminate_instance` to empirically verify that destructive actions are blocked before execution.
- **Cross-Platform & Windows-Optimized**: Designed for Windows PowerShell (UTF-8 safe, `--set key=value` CLI ergonomics) as well as Linux and macOS.

---

## 2. Technology Stack

- **Language**: Python >= 3.10
- **Agent Framework**: [Strands Agents SDK](https://strandsagents.com) (`strands-agents`)
- **Guardrail Classifier**: [Strands Decider 2B](https://github.com/strands-labs/strands-decider) (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`)
- **LLM Reasoning (Live Path)**: Amazon Bedrock (default: `us.anthropic.claude-haiku-4-5-20251001-v1:0` via AWS SDK credential chain)
- **Data Catalog**: Local synthetic JSON store (`data/incidents.json`)
- **Packaging & CI**: PEP 517/621 `pyproject.toml`, GitHub Actions CI matrix (Ubuntu & Windows)

---

## 3. Architecture

```
User Prompt (Incident Investigation)
       │
       ▼
Strands Agent (Amazon Bedrock / Claude Haiku)
       │
       ▼
Proposed Tool Call (e.g. get_logs, terminate_instance)
       │
       ├──► [Step 1: Deterministic Policy] ──(Destructive / Unknown)──► DENY (Fast fail-closed)
       │
       ├──► [Step 2: Strands Decider 2B (/v1/systemone)]
       │        ├── args_grounded: Are argument values supported by conversation?
       │        ├── premature: Should assistant clarify before calling?
       │        └── diagnostic_appropriate: Is tool relevant to incident symptoms?
       │
       └──► [Step 3: Threshold Mapping (YES = 0.45)]
                ├── Score < Threshold or Premature ──► GUIDE (Clarify with user)
                └── All Valid ─────────────────────────► PROCEED
                                                             │
                                                             ▼
                                                Mock Synthetic Tools (data/incidents.json)
```

---

## 4. Prerequisites

- **Python**: 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Hardware (Offline Mode)**: Standard PC or Laptop (runs on 4–8 GB RAM with no GPU needed).
- **Hardware (Local Decider 2B Serving)**: 8 GB+ RAM for CPU serving.
- **AWS Credentials (Optional - Live Path Only)**: Standard AWS credentials configured via `AWS_PROFILE` or environment variables for Amazon Bedrock access.

---

## 5. Local Installation & Development

### Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/safeops.git
cd safeops
```

### Windows (PowerShell)
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install in editable mode
pip install -e .

# Or install with optional dependencies:
# pip install -e ".[strands]"   # For live Bedrock agent
```

### macOS / Linux (Bash)
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .

# Or install with optional dependencies:
# pip install -e ".[strands]"   # For live Bedrock agent
```

---

## 6. Environment Configuration

Copy `.env.example` to `.env`:

```powershell
# Windows
Copy-Item .env.example .env

# Linux/macOS
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `STRANDS_DECIDER_URL` | `http://127.0.0.1:8099` | Local Strands Decider 2B server endpoint |
| `AWS_REGION` | `us-east-1` | AWS region for Amazon Bedrock (live path) |
| `SAFEOPS_BEDROCK_MODEL_ID` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model id override |
| `SAFEOPS_DATA_PATH` | `data/incidents.json` | Path override for synthetic catalog |

---

## 7. Database & Backend Operations

> **Notice**: SafeOps uses an offline, deterministic local catalog (`data/incidents.json`) containing synthetic compute resources, CloudWatch-style alarms, metrics, and incident records. No database setup (such as PostgreSQL or Supabase) is required.

---

## 8. Testing & Verification

### Running Unit Tests (37 Tests)
SafeOps includes comprehensive unit tests covering policy, tools, decider client, guardrails, agent wiring, and CLI argument parsing:

```powershell
# Using installed package or source tree:
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -t . -v
```

### Offline Guardrail Review (₹0 Cost, No AWS)
Evaluate tool calls against deterministic policy and scripted Decider scores:

```powershell
# 1. Allowed read-only diagnostic tool
python -m safeops review --tool get_logs --set resource=web-api-prod

# 2. Blocked destructive tool (denied by deterministic policy)
python -m safeops review --tool terminate_instance --set resource_id=i-0safeops01

# 3. Ungrounded tool arguments (guided back to user)
python -m safeops review --tool get_logs --set resource=unknown-server --args-grounded 0.1
```

### Review with Live Decider 2B (Local Inference)
If you have a local Strands Decider server running (`strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --device cpu --port 8099`):

```powershell
python -m safeops review --live-decider --tool get_logs --set resource=web-api-prod
```

### Live Agent Investigation (Amazon Bedrock)
*Requires active AWS credentials and a running local Decider server:*

```powershell
python -m safeops investigate --prompt "INC-001: checkout latency is high on web-api-prod. Investigate with read-only tools only."
```

---

## 9. Deployment Instructions

### Package Build
Build standard PEP 517 source distribution and wheel:
```powershell
python -m pip install --upgrade build
python -m build
```
This generates `.whl` and `.tar.gz` in `dist/`.

### Containerized Deployment (Docker)
SafeOps can be packaged as a lightweight container for deployment to AWS ECS, AWS App Runner, or Kubernetes:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY data/ ./data/
COPY src/ ./src/
RUN pip install --no-cache-dir .
ENTRYPOINT ["safeops"]
CMD ["review", "--tool", "get_logs", "--set", "resource=web-api-prod"]
```

---

## 10. License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.
