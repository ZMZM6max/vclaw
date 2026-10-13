# SDLC Skill Chain

A standalone, composable set of Claude Code skills for the full software development lifecycle. Built on the VCMF (Vibe Coding Maturity Framework) and the DIVE (Design-Implement-Verify-Evolve) cycle.

The original monolithic Chinese design document is preserved at `软件开发全流程智能体技能(SDLC-Skill).md` for reference.

## Skills

| Skill | DIVE Stage | VCMF Principles | Purpose |
|-------|------------|-----------------|---------|
| `sdlc-requirement-analysis` | Design | Design as Contract, Interface as Boundary | Turn an idea into a structured PRD with user stories, acceptance criteria, and cross-module interaction points |
| `sdlc-architecture-design` | Design | Design as Contract, Interface as Boundary, State as Responsibility | Evaluate architecture patterns in parallel, design interface contracts, model XML architecture with DecisionTrace, and define test cases |
| `sdlc-architecture-validation` | Verify | Interface as Boundary, Reality as Baseline | Technical validation via mock simulation, real-LLM format checks, and consistency audits |
| `sdlc-design-review` | Verify | Design as Contract, Interface as Boundary, Reality as Baseline, State as Responsibility | Adversarial inspection (Attacker/Operator/Extender lenses) to find design flaws; produces problem list, not PASS/FAIL |
| `sdlc-project-scaffolding` | Implement + Evolve | Reality as Baseline, State as Responsibility, Design as Contract | Generate runnable project scaffolding with full-context grounding, CI/CD, transparent test fixtures, ADR, and evolution infrastructure |

## VCMF Principles

- **Design as Contract** — Code must obey documents, not the other way around. Every artifact must be traceable back to a requirement or design decision.
- **Interface as Boundary** — Any cross-module or cross-layer call must have an explicitly defined input/output schema and error contract before implementation begins.
- **Reality as Baseline** — Mock tests validate flow; real environments validate function. Semantic-sensitive points (security judgment, format constraints, error translation, tool selection) must be tested against real LLMs when possible.
- **State as Responsibility** — Who creates a state, who persists it, who reads it, and who cleans it up must be documented and enforced in both architecture and code.

## Shared State

All skills read from and write to `skill/artifacts/STATE.md`. Artifacts are stored in `skill/artifacts/`.

## Usage Flow

1. Invoke `sdlc-requirement-analysis` with your product idea.
2. After approving the PRD, invoke `sdlc-architecture-design`.
3. After approving the architecture, optionally invoke `sdlc-architecture-validation` for technical consistency checks.
4. (Recommended) Invoke `sdlc-design-review` for adversarial inspection.
5. After reviewing the issue list, invoke `sdlc-project-scaffolding`.

## Artifact Index

| Artifact | Path | Produced By |
|----------|------|-------------|
| PRD | `skill/artifacts/PRD.md` | `sdlc-requirement-analysis` |
| Decision Log | `skill/artifacts/DECISION_LOG.md` | All skills (appended) |
| Interface Contract | `skill/artifacts/INTERFACE_CONTRACT.md` | `sdlc-architecture-design` |
| Architecture Design | `skill/artifacts/ARCHITECTURE.md` | `sdlc-architecture-design` |
| Architecture XML | `skill/artifacts/architecture.xml` | `sdlc-architecture-design` |
| Validation Report | `skill/artifacts/VALIDATION_REPORT.md` | `sdlc-architecture-validation` |
| Design Review | `skill/artifacts/DESIGN_REVIEW.md` | `sdlc-design-review` |
| Health Check Script | `skill/artifacts/health-check.sh` | `sdlc-architecture-validation` |
| Scaffolding | `skill/artifacts/PROJECT_SCAFFOLD/` | `sdlc-project-scaffolding` |
