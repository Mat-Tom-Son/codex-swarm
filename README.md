# Codex-Swarm 🧠

> **A self-learning automation system powered by OpenAI Swarm + Anthropic Codex that remembers what works.**

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

Codex-Swarm is a domain-aware agent memory system that learns from successful automation workflows and automatically reuses proven patterns in future tasks. Think of it as giving your AI agent a memory that improves with every task.

## 🎯 What Makes This Different?

Most AI automation tools forget everything after each run. Codex-Swarm:

✅ **Learns patterns** from successful runs and automatically applies them to similar tasks
✅ **Works across domains** - code, research, writing, data analysis, document processing
✅ **Maintains context** through workspace cloning and git integration
✅ **Streams live telemetry** so you can watch your automation in real-time
✅ **Runs locally** with optional offline modes for demos and testing

### Real-World Example

```bash
# First time: System learns your SOP conversion workflow
./run.sh crossrun run "Convert SOP-001.docx to new format per template.md" \
  --task-type=document_processing

# Subsequent runs: Pattern is automatically reused
./run.sh crossrun run "Convert all SOPs in ./old-sops/" \
  --task-type=document_processing \
  --reference-run-id=<previous-run>
```

The system extracts the successful workflow (copy → transform → validate), identifies variables (file format, template path), and injects this pattern into future runs automatically.

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Anthropic Codex CLI** ([install guide](https://docs.claude.com/claude-code))
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

# 4. Configure environment (create .env file)
cat > .env <<EOF
OPENAI_API_KEY=sk-your-key-here
# Optional: CROSS_RUN_FAKE_CODEX=1 for offline demos
# Optional: CROSS_RUN_FAKE_SWARM=1 to skip OpenAI
EOF

# 5. Start services
./run.sh crossrun services
```

### Your First Run

```bash
# In a new terminal, launch a task
./run.sh crossrun run "create a hello.txt file with greeting"

# Watch it execute live, then check the workspace
ls workspaces/demo/run-*
```

**What just happened?**
- Swarm planned the task
- Codex executed it in an isolated workspace
- Steps were recorded to SQLite
- Artifacts were saved (execution logs, git diffs)
- A reusable pattern was extracted

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
# Research workflow
./run.sh crossrun run "Research recent ML advances, create summary" \
  --task-type=research

# Data analysis workflow
./run.sh crossrun run "Analyze sales_data.csv, create visualizations" \
  --task-type=data_analysis

# Writing workflow
./run.sh crossrun run "Write technical blog post about findings" \
  --task-type=writing \
  --from-run-id=<analysis-run>  # Continues from same workspace
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
run1=$(./run.sh crossrun run "Run simulation, save to results.csv" \
  --task-type=data_analysis)

# Run 2: Analysis (same workspace)
run2=$(./run.sh crossrun run "Analyze results.csv, create charts" \
  --task-type=data_analysis \
  --from-run-id=$run1)

# Run 3: Report writing (references previous work)
./run.sh crossrun run "Write report about simulation and analysis" \
  --task-type=writing \
  --from-run-id=$run2
```

### 4. **Live Streaming & Observability**

Watch your automation execute in real-time via Server-Sent Events:

```bash
# Terminal-based streaming
./run.sh crossrun watch <run-id>

# Browser-based console
./run.sh crossrun ui <run-id>
```

Every event is captured:
- Status changes (queued → running → succeeded/failed)
- Assistant reasoning steps
- Tool executions with file changes
- Artifact registrations
- Git diff summaries

### 5. **Offline & Demo Modes**

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

## 📖 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Service (FastAPI)                  │
│  Projects • Runs • Patterns • Artifacts • Event Streaming   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Swarm Runner        │
              │  (OpenAI Swarm)      │
              │  • Pattern Injection │
              │  • Domain Instructions│
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Codex CLI           │
              │  • File Operations   │
              │  • Command Execution │
              │  • JSONL Streaming   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Workspace           │
              │  • Isolated Dirs     │
              │  • Git Integration   │
              │  • Artifact Storage  │
              └──────────────────────┘
```

### Components

1. **FastAPI API Service** (Port 5050)
   - CRUD for projects/runs/patterns
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

5. **Event Broker**
   - In-memory pub/sub
   - SSE streaming to clients
   - Real-time progress updates

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

### Task Types

Configure domain-specific behavior via `--task-type`:

- `code` - Software development (default)
- `research` - Literature review, citation gathering
- `writing` - Long-form content creation
- `data_analysis` - Python analysis, visualization
- `document_processing` - Batch conversion, formatting

Each task type loads specialized:
- Pattern extractors (domain-specific variable discovery)
- Instruction templates (tailored agent behavior)
- Artifact handling preferences

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
```

### Batch Document Processing

```bash
# Process first document, establish pattern
first_run=$(./run.sh crossrun run \
  "Convert SOP-001.docx from old format to new format per new_template.md" \
  --task-type=document_processing \
  --project-id=sop-migration)

# Apply pattern to remaining documents
./run.sh crossrun run \
  "Convert all DOCX files in ./old-sops/ using same transformation" \
  --task-type=document_processing \
  --project-id=sop-migration \
  --reference-run-id=$first_run
```

### Multi-Step Code Development

```bash
# Feature development with pattern learning
./run.sh crossrun run "Add user authentication API endpoint" \
  --task-type=code \
  --project-id=my-app

# System learns: model → route → tests → run tests pattern

# Apply to next feature
./run.sh crossrun run "Add user profile API endpoint" \
  --task-type=code \
  --project-id=my-app \
  --reference-run-id=<previous-run>
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
client.put("/projects/my-research", json={
    "id": "my-research",
    "name": "Research Project",
    "task_type": "research"
})

# Launch run
response = client.post("/projects/my-research/runs", json={
    "project_id": "my-research",
    "name": "Literature review",
    "instructions": "Research recent papers on topic X",
    "reference_run_id": None,  # Optional: reuse pattern
    "from_run_id": None        # Optional: clone workspace
})

run_id = response.json()["id"]

# Stream events
with client.stream("GET", f"/runs/{run_id}/stream") as stream:
    for line in stream.iter_lines():
        if line.startswith("data:"):
            event = json.loads(line.removeprefix("data:"))
            print(event)
```

---

## 🛠️ CLI Commands

The `./run.sh crossrun` wrapper provides ergonomic commands:

```bash
# Installation & Setup
./run.sh crossrun install          # Install Python dependencies
./run.sh crossrun migrate          # Create/update database schema

# Service Management
./run.sh crossrun services         # Launch API + Runner
./run.sh crossrun services --manual # Show commands instead of running

# Running Tasks
./run.sh crossrun run "instructions" \
  [--task-type TYPE] \
  [--project-id ID] \
  [--reference-run-id ID] \
  [--from-run-id ID] \
  [--no-watch]

# Monitoring
./run.sh crossrun watch <run-id>   # Stream events to terminal
./run.sh crossrun ui <run-id>      # Open browser console

# Quick Demo
./run.sh crossrun quickstart       # Install, migrate, run demo
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

### Areas for Improvement

- [ ] **Multi-tool support** - Add executors beyond Codex
- [ ] **Authentication** - Add API key/OAuth support
- [ ] **Pattern quality** - LLM-based pattern extraction
- [ ] **UI enhancements** - Rich artifact viewers, pattern editor
- [ ] **Workspace optimization** - Snapshot dedupe, compression
- [ ] **Cross-domain patterns** - Transfer patterns between domains
- [ ] **Batch operations** - Run multiple tasks in parallel
- [ ] **Export/import** - Share patterns across instances

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/codex-swarm.git
cd codex-swarm

# Install dev dependencies
./run.sh crossrun install

# Run tests
PYTHONPATH=src python3.11 -m pytest

# Make changes, add tests, submit PR
```

### Guidelines

- Add tests for new features
- Update documentation
- Follow existing code style (Ruff, Black)
- Keep backward compatibility when possible

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

---

## 📬 Support

- **Documentation**: See [docs/](docs/) for architecture details and guides
- **Issues**: [GitHub Issues](https://github.com/Mat-Tom-Son/codex-swarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Mat-Tom-Son/codex-swarm/discussions)

---

## 🗺️ Roadmap

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

Made with ❤️ by the community

</div>
