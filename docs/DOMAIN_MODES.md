# Domain Modes - Multi-Purpose Agent System

## Overview

The codex-swarm system now supports multiple workflow domains beyond just coding. Each domain has specialized pattern extraction and tailored instructions for the Swarm agent.

## Available Domains

### 1. **Code** (default)
Software development, scripting, and coding tasks.

**Use for:**
- Building applications and features
- Refactoring code
- Running tests
- Creating git commits

**Example:**
```bash
./run.sh crossrun run "add a new API endpoint for user profiles" \
  --task-type=code
```

### 2. **Research**
Literature review, web research, citation gathering, and synthesis.

**Use for:**
- Gathering information from documents
- Creating literature reviews
- Extracting citations
- Synthesizing research findings

**Example:**
```bash
./run.sh crossrun run "Research recent advances in plant phenotyping, create literature review" \
  --task-type=research
```

### 3. **Writing**
Long-form content creation including articles, reports, and documentation.

**Use for:**
- Drafting articles and reports
- Technical documentation
- Content editing and refinement
- Document formatting

**Example:**
```bash
./run.sh crossrun run "Write methods section for research paper referencing data in results.csv" \
  --task-type=writing
```

### 4. **Document Processing**
Batch document conversion, formatting, and transformation.

**Use for:**
- Converting document formats (DOCX → PDF, etc.)
- Batch processing multiple files
- Applying templates to documents
- Extracting and transforming content

**Example:**
```bash
./run.sh crossrun run "Convert all SOPs in ./plant-sops/ from old template to new template per guidelines.md" \
  --task-type=document_processing
```

### 5. **Data Analysis**
Python analysis, data visualization, and statistical computing.

**Use for:**
- Loading and analyzing datasets
- Running simulations
- Creating visualizations
- Generating analysis reports

**Example:**
```bash
./run.sh crossrun run "Run Monte Carlo simulation with params.json, save results to output.csv" \
  --task-type=data_analysis
```

## Domain-Specific Features

### Pattern Extraction

Each domain has a specialized pattern extractor that identifies domain-relevant variables:

- **Code**: File ranges, substitution patterns, file references
- **Research**: Citations, URLs, search queries, source documents
- **Writing**: Tone, audience, structure, word count, style guides
- **Document Processing**: Format conversions, batch patterns, templates, directories
- **Data Analysis**: DataFrame operations, chart types, datasets, statistical methods

### Instruction Templates

Each domain loads specialized instructions that guide the Swarm agent:

- Located in: `src/app/domains/instructions/`
- Automatically selected based on `task_type`
- Define best practices and workflow patterns for each domain

### Pattern Reuse Across Domains

Patterns can be reused within the same domain:

```bash
# First run: establish pattern
run1=$(./run.sh crossrun run "Research topic X, create summary" --task-type=research)

# Second run: reuse research pattern
./run.sh crossrun run "Research topic Y, create summary" \
  --task-type=research \
  --reference-run-id=$run1
```

### Workspace Continuity

Workspaces can be cloned across runs in any domain:

```bash
# Run 1: Simulation
run1=$(./run.sh crossrun run "Run simulation, save to data.csv" --task-type=data_analysis)

# Run 2: Analysis (continues from same workspace)
run2=$(./run.sh crossrun run "Analyze data.csv, create charts" \
  --task-type=data_analysis \
  --from-run-id=$run1)

# Run 3: Write report (references previous work)
./run.sh crossrun run "Write report about simulation and analysis" \
  --task-type=writing \
  --from-run-id=$run2
```

## Architecture

### Task Type Flow

1. **Project Creation**: Project is created with `task_type`
2. **Pattern Extraction**: When extracting patterns, domain-specific extractor is used
3. **Run Execution**: Domain instructions are loaded and merged with pattern block
4. **Codex Execution**: All domains use Codex CLI as the execution engine

### Configuration

Domain configurations are defined in:
- `src/app/domains/config.py` - Domain metadata and settings
- `src/app/services/patterns/extractors/` - Pattern extraction logic
- `src/app/domains/instructions/` - Agent instruction templates

## Examples by Use Case

### Research → Writing Pipeline

```bash
# 1. Research phase
research_run=$(./run.sh crossrun run "Research deep learning in agriculture" \
  --task-type=research \
  --project-id=ag-paper)

# 2. Write introduction using research
./run.sh crossrun run "Write introduction section using research findings" \
  --task-type=writing \
  --project-id=ag-paper \
  --from-run-id=$research_run
```

### Data Analysis → Reporting

```bash
# 1. Run analysis
analysis_run=$(./run.sh crossrun run "Analyze crop_data.csv, create visualizations" \
  --task-type=data_analysis \
  --project-id=crop-study)

# 2. Generate report
./run.sh crossrun run "Create analysis report with findings and charts" \
  --task-type=writing \
  --project-id=crop-study \
  --from-run-id=$analysis_run
```

### Document Batch Processing

```bash
# Process multiple SOPs with pattern learning
./run.sh crossrun run "Convert SOP-001.docx to new format per template.md" \
  --task-type=document_processing \
  --project-id=sop-migration

# Reuse pattern for remaining SOPs
./run.sh crossrun run "Convert all remaining SOPs in ./old-sops/" \
  --task-type=document_processing \
  --project-id=sop-migration \
  --reference-run-id=<previous-run-id>
```

## API Usage

### Creating Domain-Specific Projects

```python
import httpx

client = httpx.Client(base_url="http://localhost:5050")

# Create research project
client.put("/projects/my-research", json={
    "id": "my-research",
    "name": "Literature Review Project",
    "task_type": "research"
})

# Create run
response = client.post("/projects/my-research/runs", json={
    "project_id": "my-research",
    "name": "Review deep learning papers",
    "instructions": "Search for and summarize recent deep learning papers"
})
```

## Migration from Old Codex-Only System

Existing projects default to `task_type: "code"` after migration. To change:

```bash
# Update task type via API
curl -X PUT http://localhost:5050/projects/my-project \
  -H "Content-Type: application/json" \
  -d '{"id": "my-project", "name": "My Project", "task_type": "research"}'
```

## Implementation Details

### Database Schema

Added fields to `projects` table:
- `task_type` (VARCHAR, default: "code")
- `domain_config` (JSON, nullable)

### Pattern Extraction

Pattern extraction now accepts an `extractor` parameter:
```python
from app.services.patterns import extract_pattern_from_steps
from app.services.patterns.extractors import ResearchExtractor

pattern = extract_pattern_from_steps(
    run_id=run_id,
    steps=steps,
    extractor=ResearchExtractor()
)
```

### Swarm Instructions

Instructions are built dynamically:
```python
# In runner
def build_instructions(context_variables):
    task_type = context_variables.get("task_type", "code")
    domain_instructions = _load_domain_instructions(task_type)
    # Merge pattern block + domain instructions + tool usage
    return merge_instructions(...)
```

## Future Enhancements

Potential additions:
- Custom domain configurations via `domain_config` JSON field
- Multi-tool support (different executors per domain)
- LLM-based pattern extraction for complex workflows
- Cross-domain pattern transfer
- Domain-specific artifact viewers in UI
