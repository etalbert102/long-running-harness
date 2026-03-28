Your goal is to hand Codex a spec that is concrete enough to build the first useful version of an editorial-fit rewrite system, without pretending the whole problem is fully automatable.

Best first build: **a venue-fit compiler**, not a magical full rewriter. Codex is well-suited to long-horizon, multi-file engineering work and parallel agent workflows, which fits this kind of tool. OpenAI describes Codex as an agentic coding system for long-running software tasks, with separate work environments and support for parallel work across projects. ([OpenAI][1])

## Draft technical specification for Codex

### Project title

Editorial Fit Compiler

### Objective

Build a Python tool that analyzes a draft essay against a target venue profile and produces:

1. a structured diagnostics report
2. a paragraph-level edit plan
3. a compliance check against explicit constraints
4. an optional LLM-assisted rewrite prompt scaffold
5. a post-rewrite verifier comparing original vs revised text

The system is **not** responsible for fully autonomous publication-grade rewriting. It should handle deterministic and semi-deterministic parts of the workflow and make the final rewrite materially easier and safer.

### Primary use case

User provides:

* source draft
* target venue
* required concepts that must remain
* forbidden changes
* optional target word count or range

System returns:

* venue-fit scorecard
* top violations
* paragraph-by-paragraph action plan
* preservation audit
* candidate rewrite brief for Codex or API model
* post-rewrite verification report

---

## Product requirements

### Functional requirements

#### 1. Input handling

Accept:

* `.md`, `.txt`, `.docx`
* CLI input path or pasted text
* config file for venue profile and constraints

Input schema:

```yaml
draft_path: path/to/draft.md
target_venue: smr
constraints:
  preserve_concepts:
    - Behavioral Compression
    - Decision-Space Erosion
    - Authority Topology
  forbid:
    - em_dash
    - citations
    - new_sections
  max_new_sentences: 3
  word_count_tolerance_percent: 5
preferences:
  prioritize:
    - executive_credibility
    - concrete_language
    - sentence_rhythm_variation
```

#### 2. Venue profile system

Store venue profiles as versioned YAML or JSON.

Each profile should define:

* target audience
* tone profile
* favored opening pattern
* acceptable abstraction density
* preferred sentence length range
* paragraph length norms
* disfavored markers
* required emphasis
* banned or discouraged stylistic traits

Example venues for v1:

* `smr`
* `boston_review`
* `hdsr`
* `lawfare_like`
* `general_policy_magazine`

#### 3. Deterministic diagnostics engine

Implement analyzers for:

* word count
* sentence length distribution
* paragraph length distribution
* em dash count
* hedge density
* nominalization density
* abstraction-heavy phrase count
* discourse scaffolding phrase count
* repeated sentence opener patterns
* repeated rhetorical templates
* undefined key term detection in first N paragraphs
* concrete actor noun density
* example density
* first-example position
* section count
* bullet count
* citation pattern detection
* acronym overload
* passive voice estimate
* first-paragraph throat-clearing estimate

#### 4. Paragraph function classifier

For each paragraph, classify likely role:

* opener
* framing
* concept definition
* mechanism
* example
* evidence
* implication
* recommendation
* conclusion
* throat-clearing
* transition

Can begin as heuristic/rule-based. Optional LLM classification behind a flag.

#### 5. Constraint compliance checker

Must verify:

* preserved concepts still present
* forbidden tokens or patterns absent
* section count unchanged if required
* no added citations
* no added bullets
* new sentence count within limit
* word count within allowed range
* required distinctions not collapsed into one phrase

#### 6. Preservation audit

Compare original and revised drafts for:

* key term retention
* causal claim drift
* added unsupported claims
* removed examples
* changed institutional actors
* altered polarity of claims
* changed recommendation strength
* changed scope qualifiers

Return a diff report with severity tags:

* info
* warning
* critical

#### 7. Edit-plan generator

Generate a structured edit plan:

* top 5 global issues
* paragraph-by-paragraph edit instruction
* suggested reorder opportunities
* candidate compression targets
* paragraphs that need more concrete institutional stakes
* paragraphs that need rhythm variation

Output format:

```json
{
  "global_issues": [
    {"issue": "abstract_opening", "severity": "high"},
    {"issue": "uniform_sentence_cadence", "severity": "medium"}
  ],
  "paragraph_actions": [
    {
      "paragraph_id": 1,
      "role": "opener",
      "problems": ["too_abstract", "no concrete actor"],
      "actions": ["move concrete consequence into first 2 sentences", "cut one framing sentence"]
    }
  ]
}
```

#### 8. Rewrite brief generator

Create a Codex-ready prompt artifact that includes:

* target venue summary
* draft-specific issues
* hard constraints
* paragraph-specific instructions
* required concepts to preserve
* explicit non-goals

This should generate a file like:
`artifacts/rewrite_brief_smr.md`

#### 9. Post-rewrite verifier

Given original and revised drafts, generate:

* compliance pass/fail
* venue-fit deltas
* concept preservation results
* likely regressions
* suspicious new claims
* unresolved weak paragraphs

---

## Non-functional requirements

### Language and stack

* Python 3.11+
* `typer` for CLI
* `pydantic` for schemas
* `python-docx` for `.docx`
* `nltk` or `spacy` for sentence segmentation
* `rapidfuzz` for phrase similarity checks
* `ruamel.yaml` or `pyyaml` for profile configs
* `rich` for terminal reports
* optional `jinja2` for report templates

### Design principles

* deterministic checks first
* LLM calls optional and isolated behind interfaces
* all outputs reproducible given same inputs and config
* venue profiles editable without code changes
* easy to add new analyzers

### Performance

* analyze 3,000-word essay in under 3 seconds without LLM calls
* under 15 seconds with optional LLM paragraph classification on a standard laptop, excluding network latency

### Safety and trust

* never silently rewrite user text
* preserve original file
* all transformations logged
* every flagged issue must include evidence span when possible
* uncertain heuristics must be labeled as heuristic

---

## System architecture

### Modules

```text
editorial_fit_compiler/
  cli/
    main.py
  core/
    models.py
    config.py
    pipeline.py
  analyzers/
    structure.py
    style.py
    rhetoric.py
    venue_fit.py
    preservation.py
  classifiers/
    paragraph_roles.py
  venues/
    smr.yaml
    boston_review.yaml
    hdsr.yaml
  reports/
    console.py
    json_report.py
    markdown_report.py
  prompts/
    rewrite_brief.py
  utils/
    text.py
    diffing.py
    spans.py
  tests/
```

### Pipeline

1. ingest draft
2. normalize text
3. segment into paragraphs and sentences
4. run deterministic analyzers
5. load venue profile
6. compute venue-fit diagnostics
7. generate edit plan
8. optionally generate rewrite brief
9. if revised draft provided, run preservation and compliance audit

---

## Scoring model

### Venue-fit score

Weighted composite from:

* opening fit
* abstraction control
* sentence rhythm variation
* concreteness
* audience alignment
* conceptual overload
* actionability
* structure discipline
* forbidden marker avoidance

Example:

```yaml
smr:
  weights:
    concreteness: 0.20
    executive_actionability: 0.20
    abstraction_control: 0.15
    opening_fit: 0.15
    sentence_rhythm: 0.10
    concept_load: 0.10
    structure_discipline: 0.10
```

### Output

* overall score: 0–100
* category scores
* severity-ranked issues

---

## Heuristic definitions for v1

### AI-like tone markers

Flag patterns such as:

* repeated balanced contrast templates
* high density of abstract nouns
* repeated scaffolding phrases
* too many sentences in narrow length band
* serial “not only X, but Y” constructions
* too many summary-topic sentences without concrete actors

### Concrete language proxy

Score higher when paragraphs contain:

* named institutions
* operational actors
* tangible consequences
* measurable actions
* implementation verbs

### Throat-clearing heuristic

Flag first 1–2 paragraphs if they:

* define the topic without pressure or consequence
* lack concrete actor
* lack institutional stake
* delay mechanism or case example

---

## CLI requirements

### Commands

```bash
efc analyze draft.md --venue smr
efc analyze draft.md --venue boston_review --config job.yaml
efc verify original.md revised.md --venue smr
efc brief draft.md --venue smr --out artifacts/
efc profile show smr
```

### Example output

```bash
Overall venue fit: 71/100

Top issues:
1. Opening too abstract for SMR
2. Sentence cadence overly uniform
3. Key example appears too late
4. Concept stack too dense in paragraphs 3-4
5. Executive implications underdeveloped

Constraint status:
- em dashes: FAIL
- citations: PASS
- preserved concepts: PASS
- new sections: PASS
```

---

## Test requirements

### Unit tests

Cover:

* sentence segmentation
* word count logic
* forbidden marker detection
* concept preservation checks
* paragraph role heuristics
* venue profile loading
* diff severity classification

### Golden tests

Create fixtures for 3–5 known essays and expected diagnostics.

### Regression tests

Ensure venue scores and issue flags stay stable unless intentionally changed.

---

## V1 success criteria

System is useful if it can reliably do all of these:

* catch explicit constraint violations
* produce diagnostics that feel directionally right
* identify the 3–5 highest-ROI edit targets
* generate a rewrite brief better than a generic “rewrite this for X”
* detect when a revision accidentally drops a required concept

---

## Explicit non-goals for v1

* autonomous publication-ready rewriting
* perfect editor simulation
* deep semantic truth-checking
* source verification
* citation generation
* cross-document corpus intelligence
* GUI

---

## Stretch goals for v2

* corpus-level consistency checker across essays
* learned venue calibration from accepted/rejected drafts
* LLM-assisted paragraph role classification
* rhetorical energy scoring
* recommendation strength drift detector
* web UI
* Git diff integration
* VS Code extension

---

## Codex execution plan

Ask Codex to build in this order:

### Phase 1

* project scaffold
* text ingestion
* venue profile loader
* deterministic analyzers
* CLI analyze command

### Phase 2

* paragraph classifier
* scoring model
* markdown/json reports
* rewrite brief generator

### Phase 3

* original vs revised verifier
* preservation audit
* golden tests
* packaging and docs

---

## High-ROI Codex prompt to pair with this spec

Build a Python 3.11 CLI application called Editorial Fit Compiler.

Implement v1 only.

Prioritize deterministic analysis, venue-profile configurability, and trustworthy reporting over cleverness.

Do not attempt full autonomous rewriting.

Start by implementing:

1. file ingestion for md txt docx
2. venue profile YAML loader
3. analyzers for word count sentence length paragraph length em dash citations bullets hedge density nominalization proxy scaffolding phrase count concrete actor density
4. overall venue-fit scoring
5. markdown and JSON report output
6. CLI command `analyze`

Then add:
7. rewrite brief generator
8. verify command for original vs revised preservation audit

Use typed Python, pydantic models, typer CLI, rich terminal output, pytest tests.

Create clean module boundaries so LLM-based components can be added later without refactoring the deterministic core.

Deliver:

* runnable code
* sample venue profiles for SMR Boston Review HDSR
* tests
* README with example commands
* example analysis output on a sample text fixture

Assumptions:

* no database
* local files only
* no web app
* no external API dependency in v1

The main reason this spec is high ROI is that it tells Codex to build the part that is actually stable: analyzer, constraint engine, venue profiles, and verifier. That matches how Codex is intended to handle substantial coding workflows over multiple files rather than a single one-off script. ([OpenAI][1])

If you want, I can next compress this into a **single Codex-ready prompt** or turn it into a **repo README + task list**.


