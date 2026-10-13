# SDLC Skill Chain Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the 4-skill SDLC chain from a "role relay race" to a "single thinker's iterative drafts" model, by refactoring state management, architecture-design parallel evaluation, adding a new adversarial design-review skill, and enhancing scaffolding with full-context grounding.

**Architecture:** This is a documentation refactor. All deliverables are Markdown skill definition files and supporting templates under `skill/`. No code compilation or runtime tests. Quality assurance is via structural verification (grep for required sections, YAML frontmatter validity, no placeholders).

**Tech Stack:** Markdown, YAML frontmatter, shell verification scripts.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `skill/sdlc-state.md` | Modify | Shared state template upgraded to 4-category reasoning anchor |
| `skill/sdlc-requirement-analysis/SKILL.md` | Modify | Read STATE.md at start; write Immutable Goal; append Completed Steps |
| `skill/sdlc-architecture-design/SKILL.md` | Modify | Orchestrator-worker parallel evaluation; DecisionTrace in XML; full reasoning chain in DECISION_LOG |
| `skill/sdlc-architecture-validation/SKILL.md` | Modify | Narrow scope to technical consistency + mock flow only; remove adversarial inspection |
| `skill/sdlc-design-review/SKILL.md` | Create | New skill: adversarial inspection with Attacker/Operator/Extender lenses |
| `skill/sdlc-project-scaffolding/SKILL.md` | Modify | Read DESIGN_REVIEW.md; generate code reasoning comments + ADR + traceability audit |
| `skill/README.md` | Modify | Add sdlc-design-review to skills table; update flow diagram |
| `skill/sdlc-design.md` | Modify | Update design philosophy to reflect "single thinker" model |

---

## Verification Approach

Since all deliverables are Markdown files, there are no unit tests. Instead, each task ends with a **structural verification**:

1. `grep -c "^---"` — YAML frontmatter present (count == 2)
2. `grep -c "<HARD-GATE>"` — Hard gate present (count >= 1)
3. `grep -c "VCMF Checkpoints"` — VCMF section present
4. `grep -c -i "TODO\|TBD\|implement later\|fill in"` — No placeholders (count == 0)

---

### Task 1: Update `skill/sdlc-state.md` to 4-Category Reasoning Anchor

**Files:**
- Modify: `skill/sdlc-state.md`

- [ ] **Step 1: Write the new state template**

Replace the entire content of `skill/sdlc-state.md` with:

```markdown
---
title: SDLC State
description: Template for the file-based state used by the SDLC skill chain
---

# SDLC State

## 1. Immutable Goal (Never Overwritten)
> Read at the start of every skill invocation to prevent drift.

- Original product idea: [verbatim from user]
- Core success metrics: [quantifiable criteria]
- Scope boundary (in-scope / out-of-scope): [...]

## 2. Completed Steps (Append-Only, Never Overwritten)
> Each skill appends its key decisions here after completion.

- [YYYY-MM-DD HH:MM] sdlc-requirement-analysis: [key decision summary]
- [YYYY-MM-DD HH:MM] sdlc-architecture-design: [key decision summary]

## 3. Current State (Overwritten)
> Reflects the latest progress.

- phase: [requirement_analysis_completed | architecture_design_completed | architecture_validated | scaffolding_completed]
- DIVE: Design: [pending|in_progress|completed], Implement: [pending|in_progress|completed], Verify: [pending|in_progress|completed], Evolve: [pending|in_progress|completed]
- Next skill: [sdlc-architecture-design | sdlc-architecture-validation | sdlc-design-review | sdlc-project-scaffolding]

## 4. Known Pitfalls & Risks (Append-Only)
> Every skill MUST append risks discovered during its unfold.

- [YYYY-MM-DD] Risk: [description]. Mitigation: [strategy].
```

- [ ] **Step 2: Verify structure**

Run:
```bash
grep -c "## 1. Immutable Goal" skill/sdlc-state.md
grep -c "## 2. Completed Steps" skill/sdlc-state.md
grep -c "## 3. Current State" skill/sdlc-state.md
grep -c "## 4. Known Pitfalls" skill/sdlc-state.md
```
Expected: Each outputs `1`.

- [ ] **Step 3: Stage the change**

```bash
git add skill/sdlc-state.md
```

---

### Task 2: Refactor `skill/sdlc-requirement-analysis/SKILL.md`

**Files:**
- Modify: `skill/sdlc-requirement-analysis/SKILL.md`

- [ ] **Step 1: Read current file**

Read `skill/sdlc-requirement-analysis/SKILL.md` to understand current content.

- [ ] **Step 2: Add STATE.md interaction to Workflow**

After the existing Workflow Step 1 (Methodology alignment), insert a new Step 2 and renumber subsequent steps:

Find the line:
```
2. **Context gathering**
```

Replace with:
```
2. **State initialization**
   - Read `skill/artifacts/STATE.md` if it exists
   - If starting fresh, create `STATE.md` and populate the **Immutable Goal** section with the user's product idea, success metrics, and scope boundary
   - If `STATE.md` exists and `phase` is already `requirement_analysis_completed` or later, confirm with user whether to overwrite or continue

3. **Context gathering**
```

Then renumber all subsequent workflow steps (3→4, 4→5, 5→6, 6→7, 7→8).

- [ ] **Step 3: Update State update step**

Find the existing Step 6 (which becomes Step 7 after renumbering):
```
6. **State update**
   - Read `skill/artifacts/STATE.md`
   - Set `phase: requirement_analysis_completed`
   - Set DIVE `Design: in_progress`, others `pending`
   - Update artifact statuses
```

Replace with:
```
7. **State update**
   - Read `skill/artifacts/STATE.md`
   - Write the **Immutable Goal** section if not already present (verbatim user idea + success metrics + scope boundary)
   - Append to **Completed Steps**: `[YYYY-MM-DD HH:MM] sdlc-requirement-analysis: Locked P0/P1/P2 scope. Key decisions: [list]`
   - Set `phase: requirement_analysis_completed`
   - Set DIVE `Design: in_progress`, others `pending`
   - Update artifact statuses
```

- [ ] **Step 4: Verify structure**

```bash
grep -c "^---" skill/sdlc-requirement-analysis/SKILL.md
grep -c "<HARD-GATE>" skill/sdlc-requirement-analysis/SKILL.md
grep -c "VCMF Checkpoints" skill/sdlc-requirement-analysis/SKILL.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-requirement-analysis/SKILL.md || echo "0"
```
Expected: 2, 1, 1, 0

- [ ] **Step 5: Stage the change**

```bash
git add skill/sdlc-requirement-analysis/SKILL.md
```

---

### Task 3: Refactor `skill/sdlc-architecture-design/SKILL.md`

**Files:**
- Modify: `skill/sdlc-architecture-design/SKILL.md`

- [ ] **Step 1: Read current file**

Read `skill/sdlc-architecture-design/SKILL.md` to understand current content.

- [ ] **Step 2: Update Overview and add "Parallel Exploration" section**

Find the existing Overview paragraph:
```
## Overview

Given an approved PRD, select an architecture pattern, design explicit interface contracts, define state ownership, and produce a high-dimensional system architecture in XML.
```

Replace with:
```
## Overview

Given an approved PRD and full historical context, evaluate multiple architecture patterns in parallel (orchestrator-worker), synthesize a recommendation with full reasoning, design explicit interface contracts, define state ownership, and produce a high-dimensional system architecture in XML.

## Parallel Exploration Model

This skill uses an orchestrator-worker pattern internally:
- **Orchestrator**: Reads PRD + full history, defines evaluation dimensions, dispatches parallel workers
- **Workers**: Each worker evaluates ONE architecture pattern independently
- **Synthesis**: Orchestrator compares score matrices, produces recommendation with full reasoning chain
```

- [ ] **Step 3: Update Workflow Step 1 (Architecture selection)**

Find:
```
1. **Architecture selection**
   - Ask the user if they have a preferred architecture pattern
   - If no preference, evaluate these 6 patterns against the PRD and recommend one:
     1. Layered Architecture
     2. Microservice Architecture
     3. Event-Driven Architecture
     4. Client-Server Architecture
     5. Plugin-Based Architecture
     6. Hexagonal Architecture
   - Briefly justify the recommendation using coupling, data isolation, and flow direction
```

Replace with:
```
1. **Architecture parallel exploration**
   - Read `PRD.md`, `STATE.md`, `DECISION_LOG.md` (full historical context)
   - Define evaluation dimensions from PRD requirements (e.g., coupling, data isolation, scalability, team familiarity, maintenance cost)
   - Ask the user if they have a preferred architecture pattern; if yes, evaluate that pattern plus 2 alternatives for comparison
   - If no preference, evaluate 4 patterns in parallel:
     1. Layered Architecture
     2. Hexagonal Architecture
     3. Event-Driven Architecture
     4. Microservice Architecture
   - For each pattern, produce: fit score per dimension, key strengths, key risks
   - Synthesize: score matrix, recommended pattern, and **full reasoning chain** (why chosen, why others rejected)
```

- [ ] **Step 4: Update Workflow Step 5 (XML modeling)**

Find:
```
5. **XML architecture modeling**
   - Output a strict XML file at `skill/artifacts/architecture.xml`
   - Must contain:
     - `SystemArchitecture` root with `type` attribute
     - `Module` nodes with `Interface` (Input/Output) and `Coupling` (DependsOn)
     - `DataModel` nodes with `Fields` and `CacheStrategy`
     - `StateModel` nodes with `State` (location, owner, consumer, lifecycle)
     - `Security` nodes with `Authentication` and `Encryption`
```

Replace with:
```
5. **XML architecture modeling**
   - Output a strict XML file at `skill/artifacts/architecture.xml`
   - Must contain:
     - `SystemArchitecture` root with `type` attribute
     - `DecisionTrace` node with `Decision` children (id, date, Question, Answer, Risk)
     - `Module` nodes with `Interface` (Input/Output) and `Coupling` (DependsOn)
     - `DataModel` nodes with `Fields` and `CacheStrategy`
     - `StateModel` nodes with `State` (location, owner, consumer, lifecycle)
     - `Security` nodes with `Authentication` and `Encryption`
```

- [ ] **Step 5: Update Workflow Step 7 (Decision Log update)**

Find:
```
7. **Decision Log update**
   - Append architecture decisions to `skill/artifacts/DECISION_LOG.md`
```

Replace with:
```
7. **Decision Log update**
   - Append architecture decisions to `skill/artifacts/DECISION_LOG.md`
   - Each entry MUST include:
     - Date and decision ID
     - Evaluation dimensions and score matrix
     - Full reasoning chain (why recommended, why each alternative rejected)
     - Rejected alternatives with specific reasons
```

- [ ] **Step 6: Update Workflow Step 8 (State update)**

Find:
```
8. **State update**
   - Update `STATE.md`: `phase: architecture_design_completed`
   - Set DIVE `Design: completed`, `Implement: pending`
```

Replace with:
```
8. **State update**
   - Update `STATE.md`:
     - Append to **Completed Steps**: `[YYYY-MM-DD HH:MM] sdlc-architecture-design: Evaluated N patterns. Selected [pattern]. Key reasoning: [summary]`
     - Append to **Known Pitfalls** any risks identified during evaluation
     - Set `phase: architecture_design_completed`
     - Set DIVE `Design: completed`, `Implement: pending`
```

- [ ] **Step 7: Verify structure**

```bash
grep -c "^---" skill/sdlc-architecture-design/SKILL.md
grep -c "<HARD-GATE>" skill/sdlc-architecture-design/SKILL.md
grep -c "VCMF Checkpoints" skill/sdlc-architecture-design/SKILL.md
grep -c "DecisionTrace" skill/sdlc-architecture-design/SKILL.md
grep -c "Parallel Exploration" skill/sdlc-architecture-design/SKILL.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-architecture-design/SKILL.md || echo "0"
```
Expected: 2, 1, 1, 1, 1, 0

- [ ] **Step 8: Stage the change**

```bash
git add skill/sdlc-architecture-design/SKILL.md
```

---

### Task 4: Narrow `skill/sdlc-architecture-validation/SKILL.md` Scope

**Files:**
- Modify: `skill/sdlc-architecture-validation/SKILL.md`

- [ ] **Step 1: Read current file**

Read `skill/sdlc-architecture-validation/SKILL.md`.

- [ ] **Step 2: Update Overview**

Find:
```
## Overview

Validate an approved architecture XML by simulating data flow through modules using mock data and LLM reasoning. Identify coupling gaps, schema mismatches, state inconsistencies, and security failures before writing code.
```

Replace with:
```
## Overview

Perform technical validation of an approved architecture XML: consistency checks, mock data flow simulation, topology connectivity verification. This skill focuses on "does the architecture document hang together technically?" For adversarial design inspection, use `sdlc-design-review` instead.
```

- [ ] **Step 3: Remove adversarial inspection from Workflow**

The Workflow Step 6 (Real-LLM validation) currently includes semantic validation that overlaps with design-review. Narrow it:

Find:
```
6. **Real-LLM validation (semantic validation)**
   - If API key is available, run real LLM calls on the minimal coverage set:
     - Security judgment: can the LLM refuse malicious requests?
     - Format constraint: does the LLM output match expected schema?
     - Error translation: does the LLM turn technical errors into user-friendly messages?
     - Tool selection: does the LLM choose the right tool given the prompt?
   - If API key is unavailable, skip this step and note it in the report
```

Replace with:
```
6. **Real-LLM validation (minimal coverage)**
   - If API key is available, run real LLM calls on a minimal coverage set focused on format/schema compliance only:
     - Does the LLM output match the expected XML schema when prompted?
     - Does the LLM correctly parse and return the mock data structure?
   - If API key is unavailable, skip this step and note it in the report
   - Note: Security judgment, error translation, and tool selection validation are performed by `sdlc-design-review`
```

- [ ] **Step 4: Add scope note to Red Flags**

Find the Red Flags section:
```
## Red Flags

- Do NOT skip validation failures
- Do NOT proceed to scaffolding if validation failed
- Do NOT hallucinate API responses; explicitly state what is simulated vs real
- Do NOT generate an empty or placeholder health-check script
```

Replace with:
```
## Red Flags

- Do NOT skip validation failures
- Do NOT proceed to scaffolding if validation failed
- Do NOT hallucinate API responses; explicitly state what is simulated vs real
- Do NOT generate an empty or placeholder health-check script
- Do NOT perform adversarial design inspection; delegate that to `sdlc-design-review`
```

- [ ] **Step 5: Verify structure**

```bash
grep -c "^---" skill/sdlc-architecture-validation/SKILL.md
grep -c "<HARD-GATE>" skill/sdlc-architecture-validation/SKILL.md
grep -c "VCMF Checkpoints" skill/sdlc-architecture-validation/SKILL.md
grep -c "sdlc-design-review" skill/sdlc-architecture-validation/SKILL.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-architecture-validation/SKILL.md || echo "0"
```
Expected: 2, 1, 1, 1, 0

- [ ] **Step 6: Stage the change**

```bash
git add skill/sdlc-architecture-validation/SKILL.md
```

---

### Task 5: Create `skill/sdlc-design-review/SKILL.md`

**Files:**
- Create: `skill/sdlc-design-review/SKILL.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p skill/sdlc-design-review
```

- [ ] **Step 2: Write the new skill file**

Write `skill/sdlc-design-review/SKILL.md` with the following content:

```markdown
---
name: sdlc-design-review
description: Use when a system architecture has been designed and the user wants an adversarial inspection to find design flaws before implementation begins
---

# SDLC Design Review

## Overview

Perform adversarial inspection (Red Team mode) on an approved architecture. The ONLY job of this skill is to find problems. It does NOT produce a PASS/FAIL gate. It produces a problem list for the user and subsequent skills to reference.

This skill answers: "Are there design flaws a technically correct document can still have?"
For technical consistency checks, use `sdlc-architecture-validation` instead.

## VCMF Checkpoints

| Principle | Checkpoint in this Skill |
|-----------|--------------------------|
| Design as Contract | Verify that architecture decisions trace back to PRD requirements; flag orphaned assumptions |
| Interface as Boundary | Verify that interfaces handle edge cases and failure modes, not just happy path |
| Reality as Baseline | Verify that mock data covers abnormal paths and NFR stress scenarios |
| State as Responsibility | Verify that every StateModel has complete lifecycle (create, read, update, delete, cleanup) |

## When to Use

- The user has approved an architecture and wants a skeptical second opinion
- High-stakes or complex projects where design flaws are costly
- Do NOT use if no architecture exists or has not been approved

## Precondition Check

Read `skill/artifacts/STATE.md`. If `phase` is not `architecture_design_completed` or `architecture.xml` is missing, stop and instruct the user to run `sdlc-architecture-design` first.

## Workflow

1. **Read all historical artifacts**
   - Load `PRD.md`, `STATE.md`, `DECISION_LOG.md`, `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`
   - Understand the full reasoning chain, not just conclusions

2. **Attacker Lens (Security & Robustness)**
   - Does every module validate its input boundaries?
   - Are there race conditions in state transitions?
   - What happens if an external dependency (DB, API) fails? Is there a degradation path?
   - Are there single points of failure?
   - Is data encrypted in transit and at rest?
   - Are authentication and authorization enforced at every boundary?

3. **Operator Lens (Operability & Debuggability)**
   - If a module fails, can the root cause be located quickly?
   - Does the logging strategy cover all critical paths?
   - Do config changes require a restart?
   - Is test coverage sufficient (mock + real environment)?
   - Are docs and code synchronized?
   - Can the system be monitored and alerted effectively?

4. **Extender Lens (Scalability & Evolvability)**
   - If user load grows 10x, which module becomes the bottleneck first?
   - To add a new feature module, how much existing code must change?
   - Do interface contracts allow backward-compatible evolution?
   - Is state ownership clear (who creates, writes, reads, cleans up)?
   - Can external dependencies be swapped without rewriting core logic?

5. **Consolidate issue list**
   - Categorize findings:
     - **Must Fix**: Critical flaws that would cause system failure or security breach
     - **Should Fix**: High-risk issues that should be addressed before production
     - **Nice to Fix**: Low-risk improvements
     - **Documented Risks**: Accepted risks with explicit mitigation strategy
   - Cross-reference each issue to architecture decisions in `DECISION_LOG.md`

6. **Write `DESIGN_REVIEW.md`**
   - Output file: `skill/artifacts/DESIGN_REVIEW.md`
   - Must include:
     - Review metadata (date, artifacts reviewed)
     - Issue table with ID, description, location, impact, suggested fix
     - Cross-reference table linking issues to architecture decisions
     - Human gate phrase

7. **Update `STATE.md`**
   - Append all identified risks to **Known Pitfalls & Risks**
   - Set `phase: design_review_completed` (or keep existing phase if validation not yet run)

8. **Human gate**
   - Present issue summary (count by severity)
   - Say exactly: "设计审查报告已生成。这不是'通过/不通过'的检查，而是一份问题清单。请审阅上述问题，决定哪些需要修复、哪些可以接受。回复 [APPROVE] 进入项目脚手架阶段，回复 [FIX <issue_id>] 要求修复特定问题，或提出修改意见。"
   - Do NOT proceed until [APPROVE]

<HARD-GATE>
Do NOT proceed to project-scaffolding until the user replies [APPROVE]. This skill does NOT produce a PASS/FAIL conclusion.
</HARD-GATE>

## Output Specification

- `skill/artifacts/DESIGN_REVIEW.md`
- Must include: Must Fix / Should Fix / Nice to Fix / Documented Risks sections
- Must cross-reference issues to `DECISION_LOG.md` entries
- Must NOT contain a "PASS" or "FAIL" summary

## Red Flags

- Do NOT act as a gatekeeper; produce a problem list, not a verdict
- Do NOT skip any of the three lenses
- Do NOT invent issues not supported by the artifacts
- Do NOT proceed without the human gate
- Do NOT overwrite `STATE.md` Completed Steps (append-only)
```

- [ ] **Step 3: Verify structure**

```bash
grep -c "^---" skill/sdlc-design-review/SKILL.md
grep -c "<HARD-GATE>" skill/sdlc-design-review/SKILL.md
grep -c "VCMF Checkpoints" skill/sdlc-design-review/SKILL.md
grep -c "Attacker Lens" skill/sdlc-design-review/SKILL.md
grep -c "Operator Lens" skill/sdlc-design-review/SKILL.md
grep -c "Extender Lens" skill/sdlc-design-review/SKILL.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-design-review/SKILL.md || echo "0"
```
Expected: 2, 1, 1, 1, 1, 1, 0

- [ ] **Step 4: Stage the change**

```bash
git add skill/sdlc-design-review/
```

---

### Task 6: Enhance `skill/sdlc-project-scaffolding/SKILL.md`

**Files:**
- Modify: `skill/sdlc-project-scaffolding/SKILL.md`

- [ ] **Step 1: Read current file**

Read `skill/sdlc-project-scaffolding/SKILL.md`.

- [ ] **Step 2: Update Overview**

Find:
```
## Overview

Generate hard deliverables: directory trees, dependency files, CI/CD configs, deployment topologies, and test fixtures with strong logging. The output is a runnable project skeleton with core infrastructure implemented and business logic ready for filling. This skill handles its own planning, subagent dispatch, and verification internally.
```

Replace with:
```
## Overview

Generate hard deliverables by grounding all historical conclusions into runnable code. Reads the full reasoning chain (PRD, STATE, DECISION_LOG, ARCHITECTURE, XML, INTERFACE_CONTRACT, VALIDATION_REPORT, DESIGN_REVIEW) to ensure every generated file traces back to its origin. Output includes directory trees, dependency files, CI/CD configs, deployment topologies, test fixtures, code-level reasoning comments, and an Architecture Decision Record (ADR).
```

- [ ] **Step 3: Update Workflow Step 1 (Read all artifacts)**

Find:
```
1. **Read all artifacts**
   - Load `PRD.md`, `ARCHITECTURE.md`, `architecture.xml`, `INTERFACE_CONTRACT.md`, and `VALIDATION_REPORT.md` (if present)
```

Replace with:
```
1. **Read all artifacts**
   - Load ALL historical artifacts:
     - `PRD.md` (requirements origin)
     - `STATE.md` (current phase + known pitfalls)
     - `DECISION_LOG.md` (reasoning chain)
     - `ARCHITECTURE.md` (design summary)
     - `architecture.xml` (strict schema + DecisionTrace)
     - `INTERFACE_CONTRACT.md` (I/O boundaries)
     - `VALIDATION_REPORT.md` (if present, technical validation results)
     - `DESIGN_REVIEW.md` (if present, issue list)
```

- [ ] **Step 4: Add new Workflow Step for code reasoning comments**

After Step 4 (Core code skeleton), add a new Step 5 and renumber:

Find:
```
5. **Deployment topology**
```

Replace with:
```
5. **Code reasoning comments**
   - Every core module MUST include a header comment linking it to architecture decisions:
     - Architecture Decision ID (from DECISION_LOG or XML DecisionTrace)
     - Reasoning: why this module exists, what PRD requirement it serves
     - Known Risk: any DESIGN_REVIEW issues that apply to this module
   - Every DESIGN_REVIEW issue marked "Must Fix" or "Should Fix" MUST be translated into an inline TODO with issue ID and priority

6. **Deployment topology**
```

Then renumber subsequent steps (6→7, 7→8, 8→9, 9→10, 10→11, 11→12, 12→13).

- [ ] **Step 5: Add ADR generation step**

After the renumbered Step 9 (Documentation sync rules), add:

Find:
```
10. **Decision Log and Changelog**
```

Replace with:
```
10. **Architecture Decision Record (ADR)**
    - Generate `PROJECT_SCAFFOLD/docs/ADR.md`
    - Transform `DECISION_LOG.md` entries into human-readable ADR format:
      - Status: Accepted / Deprecated / Superseded
      - Context: What forces were at play
      - Decision: What was decided
      - Consequences: Positive and negative

11. **Decision Log and Changelog**
```

Then renumber subsequent steps (11→12, 12→13, 13→14).

- [ ] **Step 6: Add traceability audit step**

After the renumbered Step 12 (Internal verification), add:

Find:
```
13. **State update**
```

Replace with:
```
13. **Traceability audit**
    - Randomly sample 3-5 generated files
    - For each file, answer:
      - What PRD requirement does this file trace back to?
      - What INTERFACE_CONTRACT entry does its signature trace back to?
      - Does its state management match the XML StateModel?
    - If any answer is untraceable, mark as traceability gap and append to STATE.md Known Pitfalls

14. **State update**
```

Then renumber the final step (14→15).

- [ ] **Step 7: Update Output Specification**

Find:
```
## Output Specification

- `skill/artifacts/PROJECT_SCAFFOLD/` containing concrete, runnable files
- `skill/artifacts/PROJECT_SCAFFOLD/.env.template`
- `skill/artifacts/PROJECT_SCAFFOLD/docs/sync-rules.md`
- `skill/artifacts/PROJECT_SCAFFOLD/CHANGELOG.md`
- No placeholder text or abstract suggestions allowed
```

Replace with:
```
## Output Specification

- `skill/artifacts/PROJECT_SCAFFOLD/` containing concrete, runnable files
- `skill/artifacts/PROJECT_SCAFFOLD/.env.template`
- `skill/artifacts/PROJECT_SCAFFOLD/docs/sync-rules.md`
- `skill/artifacts/PROJECT_SCAFFOLD/docs/ADR.md`
- `skill/artifacts/PROJECT_SCAFFOLD/CHANGELOG.md`
- Code reasoning comments in every core module header
- Inline TODOs for every DESIGN_REVIEW Must Fix / Should Fix issue
- No placeholder text or abstract suggestions allowed
```

- [ ] **Step 8: Verify structure**

```bash
grep -c "^---" skill/sdlc-project-scaffolding/SKILL.md
grep -c "<HARD-GATE>" skill/sdlc-project-scaffolding/SKILL.md
grep -c "VCMF Checkpoints" skill/sdlc-project-scaffolding/SKILL.md
grep -c "DESIGN_REVIEW.md" skill/sdlc-project-scaffolding/SKILL.md
grep -c "traceability audit" skill/sdlc-project-scaffolding/SKILL.md
grep -c "Architecture Decision Record" skill/sdlc-project-scaffolding/SKILL.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-project-scaffolding/SKILL.md || echo "0"
```
Expected: 2, 1, 1, 1, 1, 1, 0

- [ ] **Step 9: Stage the change**

```bash
git add skill/sdlc-project-scaffolding/SKILL.md
```

---

### Task 7: Update `skill/README.md`

**Files:**
- Modify: `skill/README.md`

- [ ] **Step 1: Read current file**

Read `skill/README.md`.

- [ ] **Step 2: Update Skills table**

Find:
```
| Skill | DIVE Stage | VCMF Principles | Purpose |
|-------|------------|-----------------|---------|
| `sdlc-requirement-analysis` | Design | Design as Contract, Interface as Boundary | Turn an idea into a structured PRD with user stories, acceptance criteria, and cross-module interaction points |
| `sdlc-architecture-design` | Design | Design as Contract, Interface as Boundary, State as Responsibility | Select architecture, design interface contracts, model XML architecture, and define test cases |
| `sdlc-architecture-validation` | Verify | Interface as Boundary, Reality as Baseline | Validate architecture via mock simulation, real-LLM checks, and consistency audits |
| `sdlc-project-scaffolding` | Implement + Evolve | Reality as Baseline, State as Responsibility, Design as Contract | Generate runnable project scaffolding, CI/CD, transparent test fixtures, and evolution infrastructure |
```

Replace with:
```
| Skill | DIVE Stage | VCMF Principles | Purpose |
|-------|------------|-----------------|---------|
| `sdlc-requirement-analysis` | Design | Design as Contract, Interface as Boundary | Turn an idea into a structured PRD with user stories, acceptance criteria, and cross-module interaction points |
| `sdlc-architecture-design` | Design | Design as Contract, Interface as Boundary, State as Responsibility | Evaluate architecture patterns in parallel, design interface contracts, model XML architecture with DecisionTrace, and define test cases |
| `sdlc-architecture-validation` | Verify | Interface as Boundary, Reality as Baseline | Technical validation via mock simulation, real-LLM format checks, and consistency audits |
| `sdlc-design-review` | Verify | Design as Contract, Interface as Boundary, Reality as Baseline, State as Responsibility | Adversarial inspection (Attacker/Operator/Extender lenses) to find design flaws; produces problem list, not PASS/FAIL |
| `sdlc-project-scaffolding` | Implement + Evolve | Reality as Baseline, State as Responsibility, Design as Contract | Generate runnable project scaffolding with full-context grounding, CI/CD, transparent test fixtures, ADR, and evolution infrastructure |
```

- [ ] **Step 3: Update Usage Flow**

Find:
```
## Usage Flow

1. Invoke `sdlc-requirement-analysis` with your product idea.
2. After approving the PRD, invoke `sdlc-architecture-design`.
3. (Optional but recommended) After approving the architecture, invoke `sdlc-architecture-validation`.
4. After validation, invoke `sdlc-project-scaffolding`.
```

Replace with:
```
## Usage Flow

1. Invoke `sdlc-requirement-analysis` with your product idea.
2. After approving the PRD, invoke `sdlc-architecture-design`.
3. After approving the architecture, optionally invoke `sdlc-architecture-validation` for technical consistency checks.
4. (Recommended) Invoke `sdlc-design-review` for adversarial inspection.
5. After reviewing the issue list, invoke `sdlc-project-scaffolding`.
```

- [ ] **Step 4: Update Artifact Index**

Find:
```
| Architecture XML | `skill/artifacts/architecture.xml` | `sdlc-architecture-design` |
| Validation Report | `skill/artifacts/VALIDATION_REPORT.md` | `sdlc-architecture-validation` |
```

Replace with:
```
| Architecture XML | `skill/artifacts/architecture.xml` | `sdlc-architecture-design` |
| Validation Report | `skill/artifacts/VALIDATION_REPORT.md` | `sdlc-architecture-validation` |
| Design Review | `skill/artifacts/DESIGN_REVIEW.md` | `sdlc-design-review` |
```

- [ ] **Step 5: Verify structure**

```bash
grep -c "sdlc-design-review" skill/README.md
grep -c "DecisionTrace" skill/README.md
grep -c "Adversarial inspection" skill/README.md || echo "0"
```
Expected: >=2, >=1, >=1

- [ ] **Step 6: Stage the change**

```bash
git add skill/README.md
```

---

### Task 8: Update `skill/sdlc-design.md`

**Files:**
- Modify: `skill/sdlc-design.md`

- [ ] **Step 1: Read current file**

Read `skill/sdlc-design.md`.

- [ ] **Step 2: Update Design Objective**

Find:
```
> **Design Objective**: Decompose the original monolithic skill `软件开发全流程智能体技能(SDLC-Skill).md` into four composable, responsibility-clear, standalone skills that embed VCMF principles and the DIVE cycle.
```

Replace with:
```
> **Design Objective**: Decompose the original monolithic skill `软件开发全流程智能体技能(SDLC-Skill).md` into five composable skills that embed VCMF principles and the DIVE cycle. The skill chain models a "single thinker's iterative drafts" rather than a "role relay race": each skill is the same thinker unfolding the same complex problem from a different dimension, always holding the complete intent.
```

- [ ] **Step 3: Update Architecture diagram**

Find:
```
User inputs a raw idea
    |
    v
+-----------------------------------------------------------+
|  sdlc-requirement-analysis                                |
|  DIVE: Design                                             |
|  Outputs: PRD.md + DECISION_LOG.md                        |
+-----------------------------------------------------------+
    | [APPROVE]
    v
+-----------------------------------------------------------+
|  sdlc-architecture-design                                 |
|  DIVE: Design (deepen)                                    |
|  Outputs: ARCHITECTURE.md + INTERFACE_CONTRACT.md         |
|           + architecture.xml                              |
+-----------------------------------------------------------+
    | [APPROVE]
    v
+-----------------------------------------------------------+
|  sdlc-architecture-validation  (optional, degraded OK)    |
|  DIVE: Verify                                             |
|  Outputs: VALIDATION_REPORT.md + health-check.sh          |
+-----------------------------------------------------------+
    | [APPROVE]
    v
+-----------------------------------------------------------+
|  sdlc-project-scaffolding                                 |
|  DIVE: Implement + Evolve                                 |
|  Outputs: PROJECT_SCAFFOLD/ + .env.template               |
|           + docs/sync-rules.md + CHANGELOG.md             |
+-----------------------------------------------------------+
    | [APPROVE]
    v
   Done
```

Replace with:
```
User inputs a raw idea
    |
    v
+-----------------------------------------------------------+
|  sdlc-requirement-analysis                                |
|  DIVE: Design                                             |
|  1st Unfold: Lock goal and boundaries                     |
|  Outputs: PRD.md + DECISION_LOG.md                        |
+-----------------------------------------------------------+
    | [APPROVE]
    v
+-----------------------------------------------------------+
|  sdlc-architecture-design                                 |
|  DIVE: Design (deepen)                                    |
|  2nd Unfold: Parallel exploration + synthesis             |
|  Internal: orchestrator-worker pattern                    |
|  Outputs: ARCHITECTURE.md + INTERFACE_CONTRACT.md         |
|           + architecture.xml (with DecisionTrace)         |
+-----------------------------------------------------------+
    | [APPROVE]
    v
    +-------------------------+-------------------------+
    |                         |
    v                         v
+------------------+   +---------------------------+
| sdlc-architecture|   | sdlc-design-review         |
| -validation      |   | DIVE: Verify               |
| (Optional)       |   | 3rd Unfold: Skeptical      |
| Technical        |   |    examination (NOT gate)  |
| consistency      |   | Output: DESIGN_REVIEW.md   |
+------------------+   | (problem list, no PASS/FAIL)|
    |                  +---------------------------+
    |                         | [APPROVE / FIX]
    +-------------------------+
                              v
+-----------------------------------------------------------+
|  sdlc-project-scaffolding                                 |
|  DIVE: Implement + Evolve                                 |
|  4th Unfold: Ground with full context                     |
|  Reads ALL historical artifacts                           |
|  Outputs: PROJECT_SCAFFOLD/ + .env.template               |
|           + docs/sync-rules.md + docs/ADR.md + CHANGELOG  |
+-----------------------------------------------------------+
    | [APPROVE]
    v
   Done
```

- [ ] **Step 4: Add sdlc-design-review section**

Find:
```
### 3.4 `sdlc-project-scaffolding`
```

Insert before it:

```markdown
### 3.4 `sdlc-design-review`

```yaml
---
name: sdlc-design-review
description: Use when a system architecture has been designed and the user wants an adversarial inspection to find design flaws before implementation begins
---
```

**Scope**: Adversarial inspection (Red Team mode) of approved architecture.

**Input**: All historical artifacts (PRD, STATE, DECISION_LOG, ARCHITECTURE, XML, INTERFACE_CONTRACT).

**Output**:
- `skill/artifacts/DESIGN_REVIEW.md`

**VCMF Checkpoints**:
- Design as Contract: Flag orphaned assumptions; verify decisions trace to PRD
- Interface as Boundary: Verify interfaces handle edge cases and failure modes
- Reality as Baseline: Verify mock data covers abnormal paths and NFR stress
- State as Responsibility: Verify every StateModel has complete lifecycle

**Key Workflow**:
1. Read ALL historical artifacts (full reasoning chain, not conclusions)
2. Attacker Lens: input validation, race conditions, dependency failure, encryption
3. Operator Lens: debuggability, logging, config changes, test coverage, doc sync
4. Extender Lens: 10x scalability, feature addition cost, backward compatibility, state ownership
5. Consolidate: Must Fix / Should Fix / Nice to Fix / Documented Risks
6. Cross-reference issues to DECISION_LOG architecture decisions
7. Write DESIGN_REVIEW.md
8. Update STATE.md Known Pitfalls
9. Gate: "设计审查报告已生成。这不是'通过/不通过'的检查..."

**Important**: This skill does NOT produce PASS/FAIL. It produces a problem list. The user decides what to fix.

---
```

- [ ] **Step 5: Update Core Design Principles**

Find:
```
**Core Design Principles**:
1. **Composable**: Each skill has an independent trigger and can be invoked alone or in a chain.
2. **File-based State**: Global state is persisted via `skill/artifacts/STATE.md`, not LLM context.
3. **Human-in-the-loop**: Every skill halts at `[APPROVE]`. Auto-jumping is forbidden.
4. **Subagent Ready**: Complex subtasks (code generation, multi-file refactoring) are executed via internal subagent dispatch, but the skill itself remains self-contained.
```

Replace with:
```
**Core Design Principles**:
1. **Composable**: Each skill has an independent trigger and can be invoked alone or in a chain.
2. **File-based State**: Global state is persisted via `skill/artifacts/STATE.md`, not LLM context. STATE.md is a reasoning chain anchor (4 categories: Immutable Goal, Completed Steps, Current State, Known Pitfalls).
3. **Human-in-the-loop**: Every skill halts at `[APPROVE]`. Auto-jumping is forbidden.
4. **Subagent Ready**: Complex subtasks are executed via internal subagent dispatch, but the skill itself remains self-contained.
5. **Single Thinker Model**: 5 skills = same thinker unfolding the same problem 5 times, not 5 workers passing documents. Each skill reads ALL historical artifacts, not just the previous phase's output.
6. **Adversarial Inspection**: Validation checks technical consistency; design-review finds flaws. The reviewer is a skeptic, not a successor.
```

- [ ] **Step 6: Update Directory Structure**

Find:
```
skill/
├── README.md
├── sdlc-design.md
├── sdlc-plan.md
├── sdlc-state.md
├── 软件开发全流程智能体技能(SDLC-Skill).md
├── artifacts/
│   ├── STATE.md
│   ├── PRD.md
│   ├── DECISION_LOG.md
│   ├── INTERFACE_CONTRACT.md
│   ├── ARCHITECTURE.md
│   ├── architecture.xml
│   ├── VALIDATION_REPORT.md
│   ├── health-check.sh
│   └── PROJECT_SCAFFOLD/
├── sdlc-requirement-analysis/
│   └── SKILL.md
├── sdlc-architecture-design/
│   └── SKILL.md
├── sdlc-architecture-validation/
│   └── SKILL.md
└── sdlc-project-scaffolding/
    └── SKILL.md
```

Replace with:
```
skill/
├── README.md
├── sdlc-design.md
├── sdlc-plan.md
├── sdlc-state.md
├── 软件开发全流程智能体技能(SDLC-Skill).md
├── artifacts/
│   ├── STATE.md
│   ├── PRD.md
│   ├── DECISION_LOG.md
│   ├── INTERFACE_CONTRACT.md
│   ├── ARCHITECTURE.md
│   ├── architecture.xml
│   ├── VALIDATION_REPORT.md
│   ├── DESIGN_REVIEW.md
│   ├── health-check.sh
│   └── PROJECT_SCAFFOLD/
│       └── docs/
│           ├── sync-rules.md
│           └── ADR.md
├── sdlc-requirement-analysis/
│   └── SKILL.md
├── sdlc-architecture-design/
│   └── SKILL.md
├── sdlc-architecture-validation/
│   └── SKILL.md
├── sdlc-design-review/
│   └── SKILL.md
└── sdlc-project-scaffolding/
    └── SKILL.md
```

- [ ] **Step 7: Verify structure**

```bash
grep -c "Single Thinker Model" skill/sdlc-design.md
grep -c "Adversarial Inspection" skill/sdlc-design.md
grep -c "DecisionTrace" skill/sdlc-design.md
grep -c "sdlc-design-review" skill/sdlc-design.md
grep -c "DESIGN_REVIEW.md" skill/sdlc-design.md
grep -c -i "TODO\|TBD\|implement later" skill/sdlc-design.md || echo "0"
```
Expected: 1, 1, 1, >=3, >=2, 0

- [ ] **Step 8: Stage the change**

```bash
git add skill/sdlc-design.md
```

---

### Task 9: Final Verification & Commit

**Files:**
- All files in `skill/`

- [ ] **Step 1: Run global structural verification**

```bash
# Verify all SKILL.md files have YAML frontmatter
echo "YAML frontmatter check:"
for f in skill/*/SKILL.md; do echo -n "$f: "; grep -c "^---" "$f"; done

# Verify all SKILL.md files have HARD-GATE
echo "HARD-GATE check:"
for f in skill/*/SKILL.md; do echo -n "$f: "; grep -c "<HARD-GATE>" "$f"; done

# Verify all SKILL.md files have VCMF Checkpoints
echo "VCMF Checkpoints check:"
for f in skill/*/SKILL.md; do echo -n "$f: "; grep -c "VCMF Checkpoints" "$f"; done

# Verify no placeholders
echo "Placeholder check:"
for f in skill/*/SKILL.md; do echo -n "$f: "; grep -c -i "TODO\|TBD\|implement later\|fill in" "$f" || echo "0"; done

# Verify sdlc-design-review directory exists
echo "Design review directory:"
ls -d skill/sdlc-design-review/
```
Expected:
- YAML: all 5 files output `2`
- HARD-GATE: all 5 files output `1`
- VCMF: all 5 files output `1`
- Placeholder: all 5 files output `0`
- Directory: `skill/sdlc-design-review/` exists

- [ ] **Step 2: Verify STATE.md template format**

```bash
grep -c "Immutable Goal" skill/sdlc-state.md
grep -c "Completed Steps" skill/sdlc-state.md
grep -c "Current State" skill/sdlc-state.md
grep -c "Known Pitfalls" skill/sdlc-state.md
```
Expected: All output `1`.

- [ ] **Step 3: Verify README completeness**

```bash
grep -c "sdlc-design-review" skill/README.md
grep -c "DESIGN_REVIEW.md" skill/README.md
```
Expected: >=2, >=1.

- [ ] **Step 4: Commit all changes**

```bash
git status
git add skill/
git commit -m "refactor(skill): optimize SDLC skill chain with single-thinker model

- STATE.md: upgrade to 4-category reasoning anchor
- requirement-analysis: read/write STATE.md with Immutable Goal + Completed Steps
- architecture-design: orchestrator-worker parallel evaluation + DecisionTrace in XML
- architecture-validation: narrow scope to technical consistency only
- design-review: NEW skill with Attacker/Operator/Extender adversarial lenses
- project-scaffolding: read all artifacts + code reasoning comments + ADR + traceability audit
- README + design doc: update to reflect 5-skill chain and new philosophy

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Self-Review

### Spec Coverage

| Spec Section | Implementing Task |
|--------------|-------------------|
| STATE.md 4-category structure (4.2) | Task 1 |
| Requirement-analysis reads all history (3.2) | Task 2 |
| Architecture-design parallel exploration (5) | Task 3 |
| DECISION_LOG reasoning chain (5.3) | Task 3 |
| XML DecisionTrace (5.4) | Task 3 |
| Validation scope narrowing (6.4) | Task 4 |
| New design-review skill (6) | Task 5 |
| Scaffolding reads DESIGN_REVIEW.md (7.1) | Task 6 |
| Code reasoning comments (7.2) | Task 6 |
| ADR generation (7.4) | Task 6 |
| Traceability audit (7.5) | Task 6 |
| README update (10.1) | Task 7 |
| sdlc-design.md update (10.1) | Task 8 |
| Final verification (Acceptance Criteria) | Task 9 |

**No gaps found.**

### Placeholder Scan

- No "TBD", "TODO", "implement later", "fill in" patterns found in plan steps.
- All file modifications include exact content to be written.
- All verification commands include expected outputs.

### Type Consistency

- Skill names are consistent: `sdlc-design-review` used throughout.
- File paths are consistent: `skill/artifacts/DESIGN_REVIEW.md` used throughout.
- DecisionTrace XML node name is consistent across spec and plan.
- VCMF principles are consistent across all 5 skills.

---

*Plan Version: v1.0*
*Date: 2026-04-20*
