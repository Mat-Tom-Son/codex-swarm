# Codex-Swarm 🧠✨

> **A self-learning automation system powered by OpenAI Swarm + Anthropic Codex with a professional UX that remembers what works.**

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Rich CLI](https://img.shields.io/badge/cli-rich%20formatted-purple)]()
[![DraftPunk Ready](https://img.shields.io/badge/DraftPunk-backend%20ready-orange)]()

Codex-Swarm is a domain-aware agent memory system that learns from successful automation workflows and automatically reuses proven patterns in future tasks. Now with **beautiful CLI**, **real-time progress tracking**, **powerful management tools**, and **DraftPunk integration**!

---

## ✨ What's New: Enhanced UX & Reliability

### 🎨 Beautiful CLI Experience
```
🚀 Run Created
━━━━━━━━━━━━━━━━━━━━━━
Run ID      run-abc123
Project     demo
Status      queued
Workspace   workspaces/demo/run-abc123

📡 Live Monitor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Streaming events for run run-abc123

⏳ [  0%] Preparing workspace...
⏳ [ 30%] Running Codex agent on your task...
🤖 I'll help you with that task...
🔧 codex_exec result
   Modified: test.py, app.py
⏳ [ 85%] Learning patterns from this run...
✅ Status: Succeeded
⏳ [100%] Run completed in 23.4s

📁 Workspace files: 8 total
   test.py (2.3KB)
   results.csv (12.1KB)
   ...
```

### 🎯 New Features

#### Better Feedback
- ✅ **Progress Tracking** - See exactly what's happening (0% → 100%)
- ✅ **Helpful Errors** - Get recovery suggestions when things fail
- ✅ **Rich CLI** - Beautiful colors, icons, tables, and panels
- ✅ **Animated UI** - Web console with live progress bars

#### Control & Visibility
- 🛑 **Run Cancellation** - Stop tasks mid-execution
- 📁 **Workspace Browser** - List and download files via API
- 📊 **File Summaries** - See what was created automatically
- 🔍 **Better Observability** - Enhanced event streaming

#### Maintenance Tools
- 🧹 **Smart Cleanup** - Delete old workspaces by age
- 📈 **Disk Stats** - Monitor space usage
- 📝 **Run Templates** - Quick start for common tasks
- 🔄 **Dry-Run Mode** - Preview before deleting

---

## 🎯 What Makes This Different?

Most AI automation tools forget everything after each run. Codex-Swarm:

✅ **Learns patterns** from successful runs and automatically applies them to similar tasks
✅ **Works across domains** - code, research, writing, data analysis, document processing
✅ **Maintains context** through workspace cloning and git integration
✅ **Beautiful UX** with progress tracking, helpful errors, and rich formatting
✅ **Full control** - cancel runs, browse workspaces, manage disk space
✅ **Runs locally** with optional offline modes for demos and testing

### Real-World Example

```bash
# Use a template for quick tasks
./run.sh crossrun run --template test

# Or provide custom instructions
./run.sh crossrun run "Convert SOP-001.docx to new format" \
  --task-type=document_processing

# Pattern is automatically learned and can be reused
./run.sh crossrun run "Convert all SOPs in ./old-sops/" \
  --task-type=document_processing \
  --reference-run-id=<previous-run>
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Anthropic Codex CLI** ([install guide](https://docs.claude.com/claude-code))
- **OpenAI Codex CLI 0.58+** (`npm i -g @openai/codex`)
- **OpenAI API key** (for Swarm planning) - or run in offline mode

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Mat-Tom-Son/codex-swarm.git
cd codex-swarm

# 2. Install dependencies
./run.sh crossrun install

# 3. Initialize database
./run.sh crossrun migrate

# 4. Configure environment
cat > .env <<EOF
OPENAI_API_KEY=sk-your-key-here
# Optional: CROSS_RUN_FAKE_CODEX=1 for offline demos
# Optional: CROSS_RUN_FAKE_SWARM=1 to skip OpenAI
EOF

# 5. Start services
./run.sh crossrun services
```

### Codex CLI Setup (headless)

Codex-Swarm now talks to the official Codex CLI directly. Do this once per workstation (and whenever you open a fresh shell):

```bash
# Install/upgrade the CLI
npm i -g @openai/codex

# Provide your API key to both Bash and Codex
export OPENAI_API_KEY=sk-your-key-here
printenv OPENAI_API_KEY | codex login --with-api-key

# Double-check authentication (exits 0 when ready)
codex login status
```

> Every terminal where you run `./run.sh …` needs `OPENAI_API_KEY` exported so the worker processes inherit it.

#### Upgrading existing installs

If you already have Codex-Swarm checked out, pull the latest changes and rerun:

```bash
PYTHONPATH=src python3.11 -m app.migrations
```

so your local SQLite database picks up the new `codex_thread_id` column.

### Your First Run

```bash
# In a new terminal, try a template
./run.sh crossrun run --template test

# Or use custom instructions
./run.sh crossrun run "create a hello.txt file with greeting"

# Check disk usage
./run.sh crossrun stats

# List available templates
./run.sh crossrun templates
```

**What just happened?**
- Swarm planned the task
- Codex executed it in an isolated workspace
- Real-time progress was displayed with percentages
- Steps were recorded to SQLite
- Artifacts were saved (execution logs, git diffs)
- A reusable pattern was extracted
- Workspace files were automatically summarized

---

## 🎨 CLI Commands

### Running Tasks

```bash
# Use a template (quick start!)
./run.sh crossrun run --template test
./run.sh crossrun run -t lint

# Custom instructions
./run.sh crossrun run "your instructions here"

# With options
./run.sh crossrun run "analyze security" \
  --task-type=code \
  --project-id=my-project \
  --reference-run-id=<pattern-to-reuse>
```

When you pass `--reference-run-id`, Codex-Swarm now resumes the original Codex session in addition to injecting the learned pattern, so follow-up runs can continue the same multi-step conversation and workspace context.

### Available Templates

```bash
./run.sh crossrun templates
```

| Template | Description |
|----------|-------------|
| `test` | Run test suite |
| `lint` | Run linter and fix issues |
| `format` | Format code |
| `doc` | Generate documentation |
| `analyze` | Code analysis |
| `refactor` | Refactor code |
| `security` | Security scan |
| `deps` | Update dependencies |

### Monitoring & Control

```bash
# Watch a run in real-time
./run.sh crossrun watch <run-id>

# Cancel a running task
./run.sh crossrun cancel <run-id>

# Open web UI
./run.sh crossrun ui <run-id>
```

### Maintenance

```bash
# Check disk usage
./run.sh crossrun stats

# Clean up old workspaces (dry-run)
./run.sh crossrun cleanup --older-than 7 --dry-run

# Actually clean up
./run.sh crossrun cleanup --older-than 7

# Force cleanup without confirmation
./run.sh crossrun cleanup --force
```

---

## 🌟 Key Features

### 1. **Domain-Aware Intelligence**

Different tasks need different approaches. Codex-Swarm adapts:

| Domain | Use Cases | Pattern Learning |
|--------|-----------|------------------|
| **Code** | App development, testing, refactoring | File operations, test patterns, git workflows |
| **Research** | Literature review, citation gathering | Search queries, source documents, citations |
| **Writing** | Articles, reports, documentation | Tone, structure, style guides |
| **Document Processing** | Format conversion, batch processing | Templates, transformations, file patterns |
| **Data Analysis** | Python scripts, visualizations, statistics | DataFrames, chart types, statistical methods |

```bash
# Domain-specific workflows
./run.sh crossrun run "Research recent ML advances" --task-type=research
./run.sh crossrun run "Analyze sales_data.csv" --task-type=data_analysis
./run.sh crossrun run "Write technical blog post" --task-type=writing
```

### 2. **Pattern Memory System**

Every successful run is distilled into a reusable `<reference_workflow>` block:

```xml
<reference_workflow id="pat-run-abc123">
What worked before: Converted document using template, validated output

Sequence:
1. Read source document with python-docx
2. Extract content sections
3. Apply new template format
4. Validate against schema
5. Save output file

Variables:
- source_format: format (ex: docx)
- target_format: format (ex: pdf)
- template: template (ex: template.md)

Apply the same sequence when it fits...
</reference_workflow>
```

This pattern is automatically injected into future runs with `--reference-run-id`.

### 3. **Workspace Continuity**

Clone entire workspaces (including `.git`) across runs:

```bash
# Run 1: Data collection
run1=$(./run.sh crossrun run "Run simulation, save to results.csv")

# Run 2: Analysis (same workspace)
run2=$(./run.sh crossrun run "Analyze results.csv, create charts" \
  --from-run-id=$run1)

# Run 3: Report writing
./run.sh crossrun run "Write report about simulation" \
  --from-run-id=$run2
```

### 4. **Live Progress & Observability**

Watch your automation execute in real-time:

```bash
# Terminal-based streaming with rich formatting
./run.sh crossrun watch <run-id>

# Browser-based console with animations
./run.sh crossrun ui <run-id>
```

Every event is captured:
- ⏳ Progress updates (0% → 100%)
- 📋 Status changes (queued → running → succeeded/failed)
- 🤖 Assistant reasoning steps
- 🔧 Tool executions with file changes
- 📄 Artifact registrations
- 📝 Git diff summaries
- 📁 Workspace file summaries

### 5. **Run Control**

Full control over your executions:

```bash
# Cancel a running task
./run.sh crossrun cancel <run-id>

# Browse workspace files via API
curl http://localhost:5050/runs/<run-id>/workspace/files | jq

# Download specific files
curl http://localhost:5050/runs/<run-id>/workspace/files/results.txt
```

### 6. **Smart Maintenance**

Keep your system clean and organized:

```bash
# Check disk usage
./run.sh crossrun stats

# Output:
📊 Disk Usage Statistics
━━━━━━━━━━━━━━━━━━━━━━━
Location      Size        Files    Notes
Workspaces    247.3 MB    342      15 runs
Artifacts     89.1 MB     45       Execution logs
Database      2.1 MB      3        SQLite DB
Total         338.5 MB    390
```

### 7. **Offline & Demo Modes**

Perfect for testing without external dependencies:

```bash
# Fake Codex (no CLI execution)
export CROSS_RUN_FAKE_CODEX=1

# Fake Swarm (no OpenAI API calls)
export CROSS_RUN_FAKE_SWARM=1

# Run completely offline
./run.sh crossrun services
```

---

## 🔌 DraftPunk Integration

Codex-Swarm can be used as a **clean, minimal backend** for DraftPunk, providing document workflows and automation services via a stable HTTP API.

### Quick Start for DraftPunk

```python
from draftpunk_client import CodexSwarmClient

# Initialize client
client = CodexSwarmClient(base_url="http://localhost:5050")

# Start a document writing task
run = client.start_run(
    project_id="my-workspace",
    instructions="Write a technical report on API design patterns",
    task_type="document_writing"
)

# Poll for completion
while run.status in ("queued", "running"):
    run = client.get_run(run.run_id)
    print(f"Progress: {run.progress}%")

# Get results
if run.machine_summary:
    print(f"Output: {run.machine_summary.primary_artifact}")
    content = client.get_file_text(run.run_id, run.machine_summary.primary_artifact)
```

### DraftPunk-Specific Features

- **📊 Machine Summary** - Structured, LLM-friendly output summaries
- **🎯 Task Types** - `document_writing`, `document_analysis`, `document_processing`
- **🛡️ Error Tracking** - Structured `errors` array with classifications
- **📁 File Management** - List and download workspace files
- **🔒 Non-Interactive** - Fail-fast on misconfiguration, no prompts
- **📈 Progress Tracking** - Real-time progress percentage (0-100%)

### Documentation

See **[docs/DRAFTPUNK_INTEGRATION.md](docs/DRAFTPUNK_INTEGRATION.md)** for:
- Complete API reference
- Client library usage
- Error handling patterns
- Service mode configuration
- Troubleshooting guide

---

## 📖 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   API Service (FastAPI)                     │
│  Projects • Runs • Patterns • Control • Event Streaming     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Swarm Runner        │
              │  (OpenAI Swarm)      │
              │  • Pattern Injection │
              │  • Domain Templates  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Codex CLI           │
              │  • File Operations   │
              │  • Command Execution │
              │  • JSONL Streaming   │
              │  • Cancellation      │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Workspace           │
              │  • Isolated Dirs     │
              │  • Git Integration   │
              │  • Artifact Storage  │
              │  • File Browser      │
              └──────────────────────┘
```

### Components

1. **FastAPI API Service** (Port 5050)
   - CRUD for projects/runs/patterns
   - Run control (cancel, browse files)
   - Orchestrates run lifecycle
   - Persists to SQLite
   - Streams events via SSE

2. **Swarm Runner Service** (Port 5055)
   - Hosts OpenAI Swarm agent
   - Loads domain-specific instructions
   - Calls Codex via `codex_exec` tool
   - Returns execution results

3. **Pattern Extraction**
   - Analyzes successful runs
   - Discovers domain-specific variables
   - Caches patterns for fast retrieval
   - Renders XML reference blocks

4. **Workspace Management**
   - Isolated directory per run
   - Optional git repository
   - Workspace cloning support
   - Git diff capture
   - File browsing API

5. **Event Broker**
   - In-memory pub/sub
   - SSE streaming to clients
   - Real-time progress updates
   - Rich event formatting

---

## 📡 API Reference

### Core Endpoints

#### Projects
- `PUT /projects/{id}` - Create/update project
- `GET /projects` - List all projects

#### Runs
- `POST /projects/{id}/runs` - Launch new run
- `GET /runs` - List runs (filterable by project)
- `GET /runs/{id}` - Get run details
- `GET /runs/{id}/steps` - Get run transcript
- `GET /runs/{id}/stream` - Server-Sent Events stream
- `GET /runs/{id}/diff` - Get git diff summary
- `POST /runs/{id}/cancel` - Cancel running execution ⭐ NEW!

#### Workspace Files ⭐ NEW!
- `GET /runs/{id}/workspace/files` - List all workspace files
- `GET /runs/{id}/workspace/files/{path}` - Download specific file

#### Patterns
- `GET /patterns/{run_id}` - Get extracted pattern

#### Artifacts
- `GET /runs/{id}/artifacts` - List artifacts
- `GET /runs/{id}/artifacts/{artifact_id}/download` - Download artifact file

### Example API Usage

```python
import httpx

client = httpx.Client(base_url="http://localhost:5050")

# Create project
client.put("/projects/my-project", json={
    "id": "my-project",
    "name": "My Project",
    "task_type": "code"
})

# Launch run
response = client.post("/projects/my-project/runs", json={
    "project_id": "my-project",
    "name": "Test run",
    "instructions": "Run the test suite",
})

run_id = response.json()["id"]

# Stream events
with client.stream("GET", f"/runs/{run_id}/stream") as stream:
    for line in stream.iter_lines():
        if line.startswith("data:"):
            event = json.loads(line.removeprefix("data:"))
            print(event)

# Cancel if needed
client.post(f"/runs/{run_id}/cancel")

# Browse workspace files
files = client.get(f"/runs/{run_id}/workspace/files").json()
print(f"Created {files['total_files']} files")
```

---

## 🧪 Testing

Run the comprehensive test suite:

```bash
# All tests
PYTHONPATH=src python3.11 -m pytest

# Specific test files
PYTHONPATH=src python3.11 -m pytest tests/test_live_api.py
PYTHONPATH=src python3.11 -m pytest tests/test_workspace_security.py

# Verbose output
PYTHONPATH=src python3.11 -m pytest -xvs
```

Tests include:
- ✅ Live API integration (boots both services, runs end-to-end workflow)
- ✅ Workspace security (path traversal prevention)
- ✅ Pattern extraction across domains
- ✅ Workspace cloning and git integration
- ✅ Artifact persistence and retrieval

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for Swarm | Required for production |
| `CROSS_RUN_FAKE_CODEX` | Skip Codex CLI execution | `0` |
| `CROSS_RUN_FAKE_SWARM` | Skip OpenAI Swarm calls | `0` |
| `CROSS_RUN_REQUIRE_GIT_REPO` | Enforce git repos in workspaces | `0` |
| `CROSS_RUN_RUNNER_URL` | Swarm runner URL | `http://localhost:5055` |
| `CROSS_RUN_WORKSPACE_ROOT` | Workspace directory | `./workspaces` |
| `CROSS_RUN_ARTIFACTS_ROOT` | Artifacts directory | `./artifacts` |
| `CROSS_RUN_DATABASE_PATH` | SQLite database path | `./data/crossrun.db` |
| `PYTHON_BIN` | Python interpreter | `python3.11` |

---

## 📚 Examples

### Research → Writing Pipeline

```bash
# 1. Research phase
research_run=$(./run.sh crossrun run \
  "Research deep learning in agriculture, create annotated bibliography" \
  --task-type=research \
  --project-id=ag-paper)

# 2. Write introduction using research
./run.sh crossrun run \
  "Write introduction section using research findings from bibliography.md" \
  --task-type=writing \
  --project-id=ag-paper \
  --from-run-id=$research_run
```

### Data Analysis → Report

```bash
# 1. Run analysis
analysis=$(./run.sh crossrun run \
  "Load crop_yield.csv, run statistical analysis, create box plots" \
  --task-type=data_analysis \
  --project-id=crop-study)

# 2. Generate report
./run.sh crossrun run \
  "Write analysis report with findings, reference charts in outputs/" \
  --task-type=writing \
  --project-id=crop-study \
  --from-run-id=$analysis

# 3. Browse results
curl http://localhost:5050/runs/$analysis/workspace/files | jq
```

### Multi-Step Code Development

```bash
# Feature development with pattern learning
./run.sh crossrun run --template test --project-id=my-app

# Cancel if needed
./run.sh crossrun cancel <run-id>

# Check what was created
curl http://localhost:5050/runs/<run-id>/workspace/files | jq
```

---

## 🔒 Security

### Workspace Isolation

- Run workspaces are percent-encoded and validated
- Path traversal prevention with resolved path checks
- All workspace operations stay within configured root
- Covered by regression tests (`tests/test_workspace_security.py`)

### API Security

- No authentication (designed for local/internal use)
- Add authentication middleware for production deployments
- Consider network isolation or VPN for sensitive workspaces

---

## 🤝 Contributing

Contributions are welcome! Here are some ways to help:

### Areas for Enhancement

- [ ] Multi-tool support - Add executors beyond Codex
- [ ] Authentication - Add API key/OAuth support
- [ ] Pattern quality - LLM-based pattern extraction
- [ ] UI enhancements - Rich artifact viewers, pattern editor
- [ ] Workspace optimization - Snapshot dedupe, compression
- [ ] Cross-domain patterns - Transfer patterns between domains
- [ ] Batch operations - Run multiple tasks in parallel
- [ ] Export/import - Share patterns across instances

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/codex-swarm.git
cd codex-swarm

# Install dev dependencies
./run.sh crossrun install

# Run tests
PYTHONPATH=src python3.11 -m pytest

# Check disk usage
./run.sh crossrun stats

# Make changes, add tests, submit PR
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [OpenAI Swarm](https://github.com/openai/swarm) - Multi-agent orchestration
- [Anthropic Codex](https://docs.claude.com/claude-code) - AI-powered coding assistant
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit
- [Rich](https://rich.readthedocs.io/) - Beautiful CLI formatting

---

## 📬 Support

- **Documentation**: See [docs/](docs/) for architecture details and guides
- **Issues**: [GitHub Issues](https://github.com/Mat-Tom-Son/codex-swarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Mat-Tom-Son/codex-swarm/discussions)

---

## 🗺️ Roadmap

### Completed ✅
- [x] Progress tracking with percentages
- [x] Rich CLI with colors and icons
- [x] Run cancellation
- [x] Workspace file browser
- [x] Cleanup tools
- [x] Run templates
- [x] Disk usage statistics
- [x] Enhanced error messages

### Short Term
- [ ] WebSocket event streaming
- [ ] Pattern editor UI
- [ ] Workflow visualization
- [ ] Artifact preview in browser

### Medium Term
- [ ] Multi-user support with authentication
- [ ] Remote workspace execution
- [ ] Pattern marketplace/sharing
- [ ] Advanced pattern matching (fuzzy search)

### Long Term
- [ ] Self-improving patterns via reinforcement learning
- [ ] Cross-instance pattern federation
- [ ] Visual workflow builder
- [ ] Enterprise deployment guides

---

<div align="center">

**[⭐ Star this repo](https://github.com/Mat-Tom-Son/codex-swarm)** if you find it useful!

Made with ❤️ and 🤖 by the community

</div>
