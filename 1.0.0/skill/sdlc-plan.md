# SDLC Skill Chain Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the existing 4 SDLC skills and supporting files into a cohesive, English-first, standalone software development lifecycle skill chain that embeds VCMF principles and DIVE methodology.

**Architecture:** Each skill lives in its own directory with a `SKILL.md` file. Supporting files provide shared state contract, design documentation, and entrypoint documentation. All skills are self-contained and do not invoke external superpowers skills.

**Tech Stack:** Markdown documentation only.

---

## File Responsibility Map

| File / Directory | Responsibility |
|------------------|----------------|
| `vclaw/skill/README.md` | Entrypoint overview: skills table, VCMF/DIVE mapping, usage flow, artifact index |
| `vclaw/skill/sdlc-design.md` | English design document explaining decomposition, state management, human gates, and VCMF integration |
| `vclaw/skill/sdlc-state.md` | Shared `STATE.md` template with DIVE progress tracking, artifact registry, and decisions log |
| `vclaw/skill/sdlc-requirement-analysis/SKILL.md` | Phase 1-2 skill: transforms raw ideas into structured PRD + seeds Decision Log |
| `vclaw/skill/sdlc-architecture-design/SKILL.md` | Phase 3 skill: architecture selection, interface contracts, XML modeling, test case design |
| `vclaw/skill/sdlc-architecture-validation/SKILL.md` | Phase 4 skill: mock validation, real LLM validation (degraded to mock+consistency if no API key), health-check script |
| `vclaw/skill/sdlc-project-scaffolding/SKILL.md` | Phase 5 skill: generates runnable project skeleton with CI/CD, tests, docs/sync-rules.md, .env.template |

---

## Task 1: Rewrite supporting files

**Files:**
- Modify: `vclaw/skill/README.md`
- Modify: `vclaw/skill/sdlc-design.md`
- Modify: `vclaw/skill/sdlc-state.md`

- [x] **Step 1: Rewrite `vclaw/skill/README.md`**

Content must include:
1. `# SDLC Skill Chain` heading
2. One-paragraph overview
3. Skills table with columns: Skill, DIVE Stage, VCMF Principles, Purpose
4. Shared State section explaining `skill/artifacts/STATE.md` and artifact directory
5. Usage Flow numbered list (1-4)
6. VCMF Principles section with 1-sentence mapping per principle
7. File Reference table

- [x] **Step 2: Rewrite `vclaw/skill/sdlc-design.md`**

Content must include:
1. Design Objective: decompose original monolithic skill into 4 composable skills
2. Decision: chose workflow-aggregate decomposition (4 skills)
3. Scope: general-purpose software projects
4. Architecture diagram showing 4 skills with `[APPROVE]` gates
5. Core Design Principles: Composable, File-based State, Human-in-the-loop, Subagent Ready
6. Detailed Skill Design sections for all 4 skills (mirror Task 2-5)
7. Global State Management (`STATE.md`) constraints
8. Directory Structure tree
9. VCMF Integration table mapping each skill to VCMF checkpoints
10. DIVE Cycle Mapping table
11. Implementation Path (3 steps)
12. Constraints and Principles summary

- [x] **Step 3: Rewrite `vclaw/skill/sdlc-state.md`**

Content must be the English template with `Current Phase`, `DIVE Cycle Progress`, `Artifacts`, `Decisions Log`, and `Next Action`.

---

## Task 2: Rewrite `sdlc-requirement-analysis/SKILL.md`

**Files:**
- Modify: `vclaw/skill/sdlc-requirement-analysis/SKILL.md`

- [x] **Step 1: Write YAML frontmatter**

`name: sdlc-requirement-analysis`, `description: Use when a user provides an initial product idea or goal and needs a structured PRD with user stories, acceptance criteria, interface boundaries, and functional requirements`

- [x] **Step 2: Write Overview, VCMF Checkpoints, When to Use, Precondition Check**

- [x] **Step 3: Write Workflow (numbered checklist)**

Includes: methodology alignment, context gathering, cross-module interaction mapping, PRD generation, Decision Log seeding, state update, human gate with exact Chinese phrase.

- [x] **Step 4: Write `<HARD-GATE>`**

Do NOT proceed until user replies `[APPROVE]`.

- [x] **Step 5: Write Output Specification and Red Flags**

Must include Cross-Module Interactions, observable acceptance criteria, no placeholders.

---

## Task 3: Rewrite `sdlc-architecture-design/SKILL.md`

**Files:**
- Modify: `vclaw/skill/sdlc-architecture-design/SKILL.md`

- [x] **Step 1: Write YAML frontmatter**

`name: sdlc-architecture-design`, `description: Use when a PRD has been approved and the user needs system architecture, interface contracts, test case design, and XML-based architecture modeling`

- [x] **Step 2: Write Overview, VCMF Checkpoints, When to Use, Precondition Check**

- [x] **Step 3: Write Workflow**

Includes: architecture selection (6 patterns), interface contract design, state ownership mapping, test case design, XML modeling with `<StateModel>`, documentation write, Decision Log update, state update, human gate.

- [x] **Step 4: Write `<HARD-GATE>`**

Do NOT proceed until user replies `[APPROVE]`.

- [x] **Step 5: Write Output Specification and Red Flags**

Must include `INTERFACE_CONTRACT.md`, strict XML schema, no invented requirements.

---

## Task 4: Rewrite `sdlc-architecture-validation/SKILL.md`

**Files:**
- Modify: `vclaw/skill/sdlc-architecture-validation/SKILL.md`

- [x] **Step 1: Write YAML frontmatter**

`name: sdlc-architecture-validation`, `description: Use when a system architecture XML and interface contracts have been approved and the user wants to validate them through LLM-based sandbox simulation with mock data`

- [x] **Step 2: Write Overview, VCMF Checkpoints, When to Use, Precondition Check**

- [x] **Step 3: Write Workflow**

Includes: API readiness check (degrade gracefully), consistency checks (XML vs Interface Contract, XML vs PRD), mock injection, module-by-module simulation, real-LLM validation on minimal coverage set, trace logging, self-healing loop (`[RETRY]` on failure), health-check script generation, state update, human gate.

- [x] **Step 4: Write `<HARD-GATE>`**

Do NOT proceed if validation failed. If passed, do NOT proceed until `[APPROVE]`.

- [x] **Step 5: Write Output Specification and Red Flags**

Must include `VALIDATION_REPORT.md`, `health-check.sh`, explicit simulation-vs-real notes.

---

## Task 5: Rewrite `sdlc-project-scaffolding/SKILL.md`

**Files:**
- Modify: `vclaw/skill/sdlc-project-scaffolding/SKILL.md`

- [x] **Step 1: Write YAML frontmatter**

`name: sdlc-project-scaffolding`, `description: Use when architecture design (and optional validation) is approved and the user needs concrete project scaffolding, CI/CD pipelines, transparent test fixtures, and evolution infrastructure`

- [x] **Step 2: Write Overview, VCMF Checkpoints, When to Use, Precondition Check**

- [x] **Step 3: Write Workflow**

Includes: read all artifacts, internal lightweight planning, directory tree + dependencies, core code skeleton matching interface contracts, deployment topology, CI/CD pipeline (with real-test skip logic), `.env.template`, transparent test fixtures (`tests/mock/`, `tests/real/`, `tests/end_to_end/`), `docs/sync-rules.md`, Decision Log + Changelog, internal verification, state update, human gate.

- [x] **Step 4: Write `<HARD-GATE>`**

Do NOT mark workflow complete until `[APPROVE]`.

- [x] **Step 5: Write Output Specification and Red Flags**

No placeholder text, no hard-coded secrets, signatures must match contracts, strong logging required.

---

## Task 6: Final verification

**Files:**
- Read-only verification across `vclaw/skill/`

- [x] **Step 1: Verify YAML frontmatter on all 4 SKILL.md files**

Expected: 4 matches, each description starting with `Use when`.

- [x] **Step 2: Verify `<HARD-GATE>` presence**

Expected: 4 matches.

- [x] **Step 3: Verify VCMF Checkpoints presence**

Expected: 4 matches.

- [x] **Step 4: Verify directory structure**

Expected complete structure with 4 skill directories and supporting files.

---

## Acceptance Criteria

1. All 4 `SKILL.md` files are written in English with YAML frontmatter, Overview, VCMF Checkpoints, When to Use, Precondition Check, Workflow, HARD-GATE, Output Specification, and Red Flags.
2. All 4 `SKILL.md` files contain the exact Chinese human-gate phrases specified in the workflows.
3. `README.md`, `sdlc-design.md`, and `sdlc-state.md` are rewritten in English and reflect VCMF/DIVE integration.
4. The original Chinese monolithic design document `软件开发全流程智能体技能(SDLC-Skill).md` is preserved unchanged.
5. No placeholders (TBD, TODO, implement later) exist in any rewritten file.
6. Every workflow step contains concrete actions and deliverables.
