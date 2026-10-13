# SDLC Skill Decomposition Design

> **Design Objective**: Decompose the original monolithic skill `软件开发全流程智能体技能(SDLC-Skill).md` into five composable skills that embed VCMF principles and the DIVE cycle. The skill chain models a "single thinker's iterative drafts" rather than a "role relay race": each skill is the same thinker unfolding the same complex problem from a different dimension, always holding the complete intent.

---

## 1. Design Decisions

### 1.1 Selection Conclusion

Adopt **Option B: Workflow-Aggregate Decomposition (4 Skills)**.

**Reasons**:
- Creates a natural skill chain where each skill maps cleanly to a DIVE stage
- Skill granularity is moderate, trigger conditions are clear, and users do not need to switch too frequently
- Aligns with the VCMF principles by inserting explicit checkpoints at every phase transition

### 1.2 Scope

**General-purpose**: Not tied to a specific architecture pattern. Applicable to Web apps, mobile apps, backend services, CLI tools, and any other software engineering scenario.

---

## 2. Overall Architecture

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

**Core Design Principles**:
1. **Composable**: Each skill has an independent trigger and can be invoked alone or in a chain.
2. **File-based State**: Global state is persisted via `skill/artifacts/STATE.md`, not LLM context. STATE.md is a reasoning chain anchor (4 categories: Immutable Goal, Completed Steps, Current State, Known Pitfalls).
3. **Human-in-the-loop**: Every skill halts at `[APPROVE]`. Auto-jumping is forbidden.
4. **Subagent Ready**: Complex subtasks are executed via internal subagent dispatch, but the skill itself remains self-contained.
5. **Single Thinker Model**: 5 skills = same thinker unfolding the same problem 5 times, not 5 workers passing documents. Each skill reads ALL historical artifacts, not just the previous phase's output.
6. **Adversarial Inspection**: Validation checks technical consistency; design-review finds flaws. The reviewer is a skeptic, not a successor.

---

## 3. Skill Detailed Design

### 3.1 `sdlc-requirement-analysis`

```yaml
---
name: sdlc-requirement-analysis
description: Use when a user provides an initial product idea or goal and needs a structured PRD with user stories, acceptance criteria, interface boundaries, and functional requirements
---
```

**Scope**: Aggregates original Phase 1 (PRD methodology alignment) + Phase 2 (agile and bulletproof PRD construction).

**Input**: A raw product idea or goal in natural language.

**Output**:
- `skill/artifacts/PRD.md`
- `skill/artifacts/DECISION_LOG.md` (seeded)

**VCMF Checkpoints**:
- Design as Contract: PRD must define closed-loop success metrics and scope boundaries
- Interface as Boundary: Identify and list all cross-module interaction points
- Reality as Baseline: Acceptance criteria must be observable and testable
- State as Responsibility: Document who owns each business state

**Key Workflow**:
1. Explain the "four-dimensional deduction" (Why / What / How / Modules)
2. State the five PRD quality standards
3. Surface edge-case questions (malicious traffic, third-party downtime)
4. Ask 3-5 targeted questions to fill context gaps
5. Identify cross-module interaction points
6. Generate structured PRD
7. Write PRD to `skill/artifacts/PRD.md`
8. Seed `skill/artifacts/DECISION_LOG.md`
9. Update `STATE.md`: `phase: requirement_analysis_completed`
10. Present summary and gate: "PRD 和决策日志已生成。请确认当前阶段输出。回复 [APPROVE] 进入架构设计阶段，或提出修改意见。"

---

### 3.2 `sdlc-architecture-design`

```yaml
---
name: sdlc-architecture-design
description: Use when a PRD has been approved and the user needs system architecture, interface contracts, test case design, and XML-based architecture modeling
---
```

**Scope**: Original Phase 3 (deep architecture modeling + dual-track test design).

**Input**: Approved `skill/artifacts/PRD.md`.

**Output**:
- `skill/artifacts/ARCHITECTURE.md`
- `skill/artifacts/INTERFACE_CONTRACT.md`
- `skill/artifacts/architecture.xml`

**VCMF Checkpoints**:
- Design as Contract: Architecture traceable back to PRD; no invented requirements
- Interface as Boundary: Every cross-module call has explicit Input/Output and error codes
- Reality as Baseline: Test cases cover happy path, abnormal path, and NFRs
- State as Responsibility: XML `<StateModel>` answers where, who writes, who reads, lifecycle

**Key Workflow**:
1. Read `STATE.md` and `PRD.md`
2. Ask user for preferred architecture; if none, evaluate 6 classic patterns and recommend one
3. Design interface contracts from PRD cross-module interactions
4. Map state ownership for every stateful entity
5. Generate test cases (happy + abnormal + NFR)
6. Output strict XML with `Module`, `DataModel`, `StateModel`, `Security`
7. Write `ARCHITECTURE.md` and `INTERFACE_CONTRACT.md`
8. Append decisions to `DECISION_LOG.md`
9. Update `STATE.md`: `phase: architecture_design_completed`
10. Gate: "架构设计、接口契约和 XML 模型已生成。请确认当前阶段输出。回复 [APPROVE] 进入架构验证阶段，或提出修改意见。"

---

### 3.3 `sdlc-architecture-validation`

```yaml
---
name: sdlc-architecture-validation
description: Use when a system architecture XML and interface contracts have been approved and the user wants to validate them through LLM-based sandbox simulation with mock data
---
```

**Scope**: Original Phase 4 (LLM sandbox simulation + architecture self-check).

**Input**:
- `skill/artifacts/PRD.md`
- `skill/artifacts/ARCHITECTURE.md`
- `skill/artifacts/INTERFACE_CONTRACT.md`
- `skill/artifacts/architecture.xml`

**Output**:
- `skill/artifacts/VALIDATION_REPORT.md`
- `skill/artifacts/health-check.sh`

**VCMF Checkpoints**:
- Design as Contract: Verify XML modules map back to PRD requirements
- Interface as Boundary: Verify every `Coupling` in XML matches `INTERFACE_CONTRACT.md`
- Reality as Baseline: Run real-LLM validation on semantic-sensitive points; degrade to mock+consistency if no API key
- State as Responsibility: Verify `StateModel` lifecycle definitions are internally consistent

**Key Workflow**:
1. Read XML and PRD
2. Check API Key / Base URL availability
   - If unavailable: state clearly that real-LLM validation is skipped; proceed with mock + consistency checks
3. Consistency check: XML vs Interface Contract
4. Consistency check: XML vs PRD
5. Mock injection and module-by-module simulation
6. Real-LLM validation on minimal coverage set (if API key available)
7. Print simulation trace
8. If any check fails: report failure and ask for `[RETRY]`; do NOT proceed to scaffolding
9. If all pass: write `VALIDATION_REPORT.md` and generate `health-check.sh`
10. Update `STATE.md`: `phase: architecture_validated`
11. Gate: "架构验证报告和健康检查脚本已生成。请确认当前阶段输出。回复 [APPROVE] 进入项目脚手架阶段，或提出修改意见。"

---

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

### 3.5 `sdlc-project-scaffolding`

```yaml
---
name: sdlc-project-scaffolding
description: Use when architecture design (and optional validation) is approved and the user needs concrete project scaffolding, CI/CD pipelines, transparent test fixtures, and evolution infrastructure
---
```

**Scope**: Original Phase 5 (scaffolding + transparent test engineering).

**Input**: All prior artifacts.

**Output**:
- `skill/artifacts/PROJECT_SCAFFOLD/` directory tree with runnable files
- `.env.template`
- `docs/sync-rules.md`
- `CHANGELOG.md`

**VCMF Checkpoints**:
- Design as Contract: Every generated file traceable to PRD or Architecture
- Interface as Boundary: Generated code signatures match `INTERFACE_CONTRACT.md`
- Reality as Baseline: Tests include both mock and real-LLM tests with `skipif`
- State as Responsibility: Generated state management matches `StateModel` ownership

**Key Workflow**:
1. Read all prior artifacts and `STATE.md`
2. Internal lightweight planning (files, tests, directories)
3. Generate directory tree and dependency configs
4. Generate core code skeleton matching interface contracts
5. Generate deployment topology (`docker-compose.yml` or K8s manifests)
6. Generate CI/CD config (install, lint, mock tests, real tests with continue-on-error)
7. Generate `.env.template`
8. Generate transparent test fixtures organized into `tests/mock/`, `tests/real/`, `tests/end_to_end/`
9. Generate `docs/sync-rules.md`
10. Update `DECISION_LOG.md` and generate `CHANGELOG.md`
11. Internal verification (signatures match, paths correct, CI references valid)
12. Update `STATE.md`: `phase: scaffolding_completed`
13. Gate: "项目脚手架已生成，包含工程目录、CI/CD 配置、测试脚本、文档同步规则和环境变量模板。请确认当前阶段输出。回复 [APPROVE] 完成全流程，或提出修改意见。"

---

## 4. Global State Management (`STATE.md`)

All skills MUST read `STATE.md` at startup and MUST update it before the human gate.

If a prerequisite artifact is missing or the phase does not match, the skill MUST stop and instruct the user to run the prerequisite skill.

The `Decisions Log` section records key decisions with:
- Date
- Decision description
- Reason
- Alternative considered
- Why the alternative was rejected

This prevents requirement drift across multi-turn conversations.

---

## 5. Directory Structure

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

---

## 6. VCMF Integration Mapping

| Skill | Design as Contract | Interface as Boundary | Reality as Baseline | State as Responsibility |
|-------|-------------------|----------------------|---------------------|------------------------|
| `sdlc-requirement-analysis` | PRD success metrics & scope boundaries | Cross-module interaction points | Observable acceptance criteria | State ownership documented |
| `sdlc-architecture-design` | Traceability to PRD; no invented reqs | Interface contracts in markdown + XML | Test cases for all paths + NFRs | `<StateModel>` in XML |
| `sdlc-architecture-validation` | XML modules traceable to PRD | `Coupling` matches Interface Contract | Real-LLM semantic validation (degraded OK) | `StateModel` consistency check |
| `sdlc-project-scaffolding` | Every file traceable to artifact | Code signatures match contracts | Mock + real tests generated | Code matches `StateModel` |

---

## 7. DIVE Cycle Mapping

| DIVE Stage | Skills | Key Activity |
|------------|--------|--------------|
| **Design** | `sdlc-requirement-analysis` + `sdlc-architecture-design` | Lock the "things that should not change": requirements, interfaces, state ownership, architecture |
| **Implement** | `sdlc-project-scaffolding` | Generate runnable project skeleton with infrastructure code |
| **Verify** | `sdlc-architecture-validation` | Mock flow validation + real-LLM semantic checks + consistency audits |
| **Evolve** | `sdlc-project-scaffolding` (docs + changelog) | Document sync rules, decision log, changelog for future iterations |

---

## 8. Implementation Path

### Step 1: Rewrite supporting files
- `README.md` — overview + VCMF + DIVE + usage flow
- `sdlc-state.md` — template with DIVE progress tracking
- `sdlc-design.md` — this document

### Step 2: Rewrite 4 `SKILL.md` files
- Follow the unified structure: YAML frontmatter, Overview, VCMF Checkpoints, When to Use, Precondition Check, Workflow, HARD-GATE, Output Specification, Red Flags
- Embed exact Chinese human-gate phrases
- Ensure no placeholders

### Step 3: Final quality verification
- Verify YAML frontmatter on all 4 skills
- Verify HARD-GATE presence
- Verify VCMF Checkpoints presence
- Verify directory structure completeness

---

## 9. Constraints and Principles (Inherited from Original Design)

- **Global memory first**: `STATE.md` and artifacts are the single source of truth
- **Gate is absolute**: Must wait for human `[APPROVE]`; auto-jumping is forbidden
- **Hard deliverables**: Phase 5 must produce actual code, YAML, CI configs, and test scripts with logging
- **Privacy management**: All API keys and tokens must live in `.env` files only

---

*Design Document Version: v1.1*
*Date: 2026-04-16*
