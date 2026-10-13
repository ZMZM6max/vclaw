# VClaw Layer-by-Layer Build Design

> **Goal:** Reconcile all 6 layers with their XML specifications through interface-first alignment, then build each layer independently with TDD and component-level XML decomposition.

**Approach:** Critical-Gap-First (Option C)
- Phase 0: Lock core contracts (`core/models.py`, `core/interfaces.py`)
- Phase 1: Fix 6 critical architectural gaps that break inter-layer contracts
- Phase 2-7: Build each layer bottom-up with per-component XML decomposition
- Phase 8: Integration validation via mock E2E regression

**Tech Stack:** Python 3.11, Pydantic, pytest, Docker (L6)

---

## Phase 0: Lock Core Contracts

Before any layer is modified, we freeze the inter-layer data models and abstract interfaces to exactly match the XML specifications.

**Files to modify:**
- `src/core/models.py` — StandardEvent, SessionContext, AgentAction, Observation, ExecutionResult, etc.
- `src/core/interfaces.py` — MemoryInterface, ToolsInterface, RuntimeInterface
- `src/core/exceptions.py` — Layer-specific exception hierarchy

**Key decisions:**

| Decision | XML says | Code currently does | Locked to |
|----------|----------|---------------------|-----------|
| `RuntimeInterface` | Has `run_command(command, timeout)` | Only `run_code` | **Add `run_command`** |
| `MemoryInterface.delete` | `document_id: str` | `document_ids: List[str]` | **Keep `List[str]` (batch is intentional), update XML** |
| `ExecutionResult.resource_usage` | `memory_peak`, `cpu_time` | Empty `{}` | **Populate from Docker stats** |

**Output:** `docs/superpowers/specs/interfaces_lock.md` — a decision log of every interface choice made.

---

## Phase 1: Fix 6 Critical Architectural Gaps

These gaps break the inter-layer contract. Fixing them before building features prevents integration failures.

### Gap 1: L2 Does Not Call L3

**Problem:** `ControlGateway.process_event()` returns `L3Input` but never calls `L3.run()`. The XML data flow says L2 orchestrates the L3→L5→L6 loop and routes errors back to L1.

**Fix:**
- Add `L3Orchestrator` dependency injection to `ControlGateway`
- In `process_event()`, after assembling `L3Input`, call `l3.run(context)`
- Handle `AgentAction` (route to L5) or `str` (direct response)
- On error, wrap in `OrchestrationError` and route back through `L1.ErrorHandler`

**Files:** `src/l2/l2_control_gateway.py`

### Gap 2: L3 SecurityGuard Is Bypassed

**Problem:** `Orchestration.run()` instantiates `SecurityGuard` but never calls `classify()`. XML mandates any request passes SecurityGuard before ReActEngine, TaskPlanner, LLMManager, or ToolCaller.

**Fix:**
- At top of `run()`, call `security_guard.classify(user_input)`
- Route `dangerous` → `_handle_confirmation()`
- Route `rejected` → return canned response
- Route `normal` → proceed to ReActEngine

**Files:** `src/l3/l3_orchestration.py`

### Gap 3: L5 ToolExecutor Is a Stub

**Problem:** `ToolExecutor.call_tool()` returns a placeholder `Observation`. XML requires a 6-step execution chain: ToolRegistry → ParameterValidator → PermissionManager → ConfirmationManager → ToolExecutor → ResultFormatter, with `python_repl`/`terminal` delegating to L6.

**Fix:**
- Implement full 6-step chain in `ToolsCapabilities.execute()`
- For `python_repl`/`terminal` tools, inject `RuntimeInterface` and call `run_code()`
- Return properly formatted `Observation` via `ResultFormatter`

**Files:** `src/l5/l5_tools_capabilities.py`, `src/l5/tool_executor.py`

### Gap 4: Dual Tool System

**Problem:** `src/l5/` and `src/tools/` are two parallel tool systems with different names (`file_read` vs `file_reader`), return types (`Observation` vs `ToolResult`), and interfaces.

**Fix:**
- Migrate only the tools that match XML definitions (`file_read`, `file_write`, `search_web`, `python_repl`, `terminal`, `calculator`, `file_search`) into `src/l5/`
- Standardize return type to `Observation`
- Update `ToolRegistry` to register the migrated tools
- Extra tools from `src/tools/` (`file_edit`, `glob`, `grep`, `web_fetch`, `todo_write`) are not in the current XML spec — move to `src/l5/experimental/` or remove

**Files:** `src/l5/`, `src/tools/`

### Gap 5: L3 TaskPlanner Is Instantiated But Unused

**Problem:** `Orchestration` creates a `TaskPlanner` and stores `current_plan`, but `run()` never feeds the plan into `ReActEngine`.

**Fix:**
- Call `task_planner.create_plan(user_input)` before ReAct loop
- Pass `current_plan` into `ReActEngine.run()` as structured context
- ReActEngine uses plan steps to guide thought→action selection

**Files:** `src/l3/l3_orchestration.py`, `src/l3/react_engine.py`

### Gap 6: L6 ExecutionLogger Is Unused

**Problem:** `ExecutionLogger` class exists but `RuntimeEnvironment.run_code()` never calls `log()`. `resource_usage` is always empty `{}`.

**Fix:**
- After Docker execution, call `execution_logger.log(result)`
- Extract `memory_peak` and `cpu_time` from Docker container stats API
- Populate `ExecutionResult.resource_usage` dict

**Files:** `src/l6/l6_runtime.py`

---

## Phase 2-7: Layer-by-Layer Build (L4 → L6 → L5 → L3 → L2 → L1)

### Per-Layer Pattern

Every layer follows the same 5-step process:

```
1. Split XML → component-level specs
2. Implement/Reconcile → align code to specs
3. Unit tests → mock all dependencies
4. Layer integration test → internal wiring
5. Commit
```

### L4: Memory & Knowledge (Phase 2)

**XML split into:**
- `docs/03_specs/l4/VectorStore.xml` — ChromaDB, FAISS, Memory backends
- `docs/03_specs/l4/EmbeddingService.xml` — OpenAI, Sentence Transformers
- `docs/03_specs/l4/TextChunker.xml` — Recursive, Token, Markdown splitters
- `docs/03_specs/l4/MemoryStore.xml` — Conversation, Knowledge, Preference storage
- `docs/03_specs/l4/IndexManager.xml` — Create, update, delete, optimize indices
- `docs/03_specs/l4/CacheManager.xml` — LRU + TTL caching
- `docs/03_specs/l4/integration.xml` — Data flow and CallEdges

**Code state:** Most complete layer. Main work: align CacheManager defaults (1000→10000), add Pinecone stub (raises `NotImplementedError`), extract `KnowledgeMemory`/`UserPreferenceMemory` from unified `MemoryStore`.

**Tests:** `tests/unit/l4/`, `tests/integration/l4/`

### L6: Runtime Environment (Phase 3)

**XML split into:**
- `docs/03_specs/l6/SandboxManager.xml` — Create, manage, destroy sandboxes
- `docs/03_specs/l6/ResourceLimiter.xml` — CPU, memory, time, disk, network limits
- `docs/03_specs/l6/CodeExecutor.xml` — Execute code in sandbox
- `docs/03_specs/l6/DockerController.xml` — Docker lifecycle management
- `docs/03_specs/l6/SecurityEnforcer.xml` — Language whitelist, forbidden patterns
- `docs/03_specs/l6/ExecutionLogger.xml` — Execution logging and metrics
- `docs/03_specs/l6/integration.xml` — Data flow and CallEdges

**Code state:** Docker path is solid. Main work: wire ExecutionLogger, add `run_command`, populate `resource_usage`.

**Tests:** `tests/unit/l6/`, `tests/integration/l6/`

### L5: Tools & Capabilities (Phase 4)

**XML split into:**
- `docs/03_specs/l5/ToolRegistry.xml` — Register, unregister, list tools
- `docs/03_specs/l5/ParameterValidator.xml` — Type check, path safety, schema validation
- `docs/03_specs/l5/PermissionManager.xml` — Permission rules, wildcard matching
- `docs/03_specs/l5/ConfirmationManager.xml` — Pending ops, TTL, confirmation prompts
- `docs/03_specs/l5/ToolExecutor.xml` — Execute tool, delegate to L6
- `docs/03_specs/l5/ResultFormatter.xml` — Format results per template
- `docs/03_specs/l5/BashAnalyzer.xml` — Command classification, destructive detection
- `docs/03_specs/l5/integration.xml` — 6-step execution chain

**Code state:** Components exist but ToolExecutor is stubbed, dual tool system unmerged.

**Tests:** `tests/unit/l5/`, `tests/integration/l5/`

### L3: Orchestration (Phase 5)

**XML split into:**
- `docs/03_specs/l3/SecurityGuard.xml` — Classification, canned responses
- `docs/03_specs/l3/ReActEngine.xml` — Thought→Action→Observation loop
- `docs/03_specs/l3/TaskPlanner.xml` — Plan creation, step tracking
- `docs/03_specs/l3/LLMManager.xml` — Provider management, retry, streaming
- `docs/03_specs/l3/ToolCaller.xml` — Call L5 tools
- `docs/03_specs/l3/MemoryAccessor.xml` — Retrieve context from L4
- `docs/03_specs/l3/ErrorTranslator.xml` — Error type mapping, recovery suggestions
- `docs/03_specs/l3/integration.xml` — ReAct loop with MandatoryPreActionRules

**Code state:** Classes exist but SecurityGuard not wired, TaskPlanner unused, ToolCaller stubbed.

**Tests:** `tests/unit/l3/`, `tests/integration/l3/`

### L2: Control Gateway (Phase 6)

**XML split into:**
- `docs/03_specs/l2/SessionManager.xml` — Create, get, update, expire sessions
- `docs/03_specs/l2/RateLimiter.xml` — Token bucket, user/ip/global tiers
- `docs/03_specs/l2/ContextAssembler.xml` — Build SessionContext
- `docs/03_specs/l2/HistoryRetriever.xml` — Retrieve conversation history from L4
- `docs/03_specs/l2/ToolPreparer.xml` — Filter tools by user permissions
- `docs/03_specs/l2/integration.xml` — Full data flow including L3 invocation

**Code state:** Input assembly works, but SessionManager not standalone, L3 not called, error return path missing.

**Tests:** `tests/unit/l2/`, `tests/integration/l2/`

### L1: User Interaction (Phase 7)

**XML split into:**
- `docs/03_specs/l1/ProtocolAdapter.xml` — Telegram, WebSocket, Webhook adapters
- `docs/03_specs/l1/DataValidator.xml` — Field validation, injection detection
- `docs/03_specs/l1/EventNormalizer.xml` — Adapter selection, normalization
- `docs/03_specs/l1/ErrorHandler.xml` — Retry, backoff, error formatting for L3
- `docs/03_specs/l1/integration.xml` — Payload processing pipeline

**Code state:** Most mature layer. Main work: align ErrorHandler with XML responsibilities, remove SessionManager duplication.

**Tests:** `tests/unit/l1/`, `tests/integration/l1/`

---

## Phase 8: Integration Validation

After all layers are built, validate the full pipeline:

1. **Adjacent-layer integration tests**
   - L1→L2 payload handoff
   - L2→L3 loop with AgentAction routing
   - L3→L5 tool call delegation
   - L5→L6 code execution
   - L3→L4 memory access

2. **Mock E2E regression**
   - Run all 32 existing TCs against the new implementation
   - Compare results to `final_regression` baseline
   - Target: zero degradation in pass rate

3. **Rule engine check**
   - Run `rule_engine.py` against the final XML + code
   - Target: zero R1-R7 violations

---

## Test Strategy

**Unit tests:** Each component tested in isolation with mocked dependencies.

**Layer integration tests:** Components within a layer wired together, external layers mocked via `core/interfaces.py` ABCs.

**E2E tests:** Full pipeline with mock LLM (deterministic responses) to validate data flow.

**Test file naming convention:**
- `tests/unit/l{layer}/test_{component}.py`
- `tests/integration/l{layer}/test_l{layer}_flow.py`
- `tests/e2e/test_tc_{nn}.py`

---

## Commit Strategy

One commit per layer after Phase 1:
- `feat(l4): align with XML spec, split XML, add tests`
- `feat(l6): align with XML spec, split XML, add tests`
- `feat(l5): align with XML spec, unify tool system, add tests`
- `feat(l3): wire SecurityGuard, use TaskPlanner, implement ToolCaller, add tests`
- `feat(l2): add SessionManager, call L3, route errors, add tests`
- `feat(l1): align ErrorHandler, remove SessionManager duplication, add tests`

Phase 0-1 commits precede these as a group:
- `chore(core): lock interfaces to XML contract`
- `fix(l2): add L3 invocation loop`
- `fix(l3): wire SecurityGuard as mandatory pre-gate`
- `fix(l5): implement ToolExecutor 6-step chain, delegate to L6`
- `refactor(l5): merge src/tools/ into l5, unify names and return types`
- `fix(l3): feed TaskPlanner into ReActEngine`
- `fix(l6): wire ExecutionLogger, populate resource_usage`
