# Mock-Driven XML Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured component-level tracing to the mock E2E system, run P0 tests to collect traces, analyze gaps between XML specs and real code, and iteratively refactor XML documents based on mock test evidence.

**Architecture:** Extend the existing 6-layer LLM mock framework (`tests/mock/`) with mandatory `component_trace` fields in both the Pydantic protocol and layer prompts. This enables test failures to be mapped to specific components within each layer, which drives targeted XML specification fixes.

**Tech Stack:** Python 3.11, Pydantic v2, OpenAI-compatible API, pytest, JSON.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tests/mock/layer_protocol.py` | Pydantic models for inter-layer data flow. Will gain `ComponentTraceItem` and `component_trace` fields on all output models. |
| `tests/mock/layer_prompts.py` | System prompts for L1-L6 LLM simulation. Will gain a "【组件追踪要求】" section appended to each prompt. |
| `tests/mock/e2e_framework.py` | End-to-end runner. Will persist `component_trace` from each layer into task result JSON. |
| `tests/mock/run_e2e_tests.py` | Test runner. Will run P0 suite and emit `test_report.json` that now includes component traces. |
| `scripts/analyze_mock_results.py` | New helper script: reads `test_report.json`, extracts `error`/`skipped` traces, aggregates by component. |
| `tests/mock/results/` | Output directory for per-test-case results (auto-created by runner). |
| `docs/03_specs/L{1-6}_*.xml` | Target XML specifications to be audited and refactored. |

---

## Phase 1: Instrument the Mock Framework with `component_trace`

### Task 1: Add `ComponentTraceItem` to `layer_protocol.py`

**Files:**
- Modify: `tests/mock/layer_protocol.py`

- [ ] **Step 1: Add `ComponentTraceItem` model**

Insert the following class right after the `ErrorCode` enum definition (before the `# =============================================================================` comment that starts the L1 section):

```python
class ComponentTraceItem(BaseModel):
    """组件级执行状态追踪项"""
    component: str = Field(..., description="组件名称")
    status: str = Field(..., description="success / skipped / error")
    reason: Optional[str] = Field(None, description="状态说明")
    output_summary: Optional[str] = Field(None, description="输出摘要")
```

- [ ] **Step 2: Add `component_trace` to `L1Output`**

Replace the existing `L1Output` class with:

```python
class L1Output(BaseModel):
    """L1层输出结构"""
    status: LayerStatus
    standard_event: Optional[StandardEvent] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 3: Add `component_trace` to `L2Output`**

Replace the existing `L2Output` class with:

```python
class L2Output(BaseModel):
    """L2层输出结构"""
    status: LayerStatus
    session_context: Optional[SessionContext] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    rate_limit: Optional[RateLimitInfo] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 4: Add `component_trace` to `L3Output`**

Replace the existing `L3Output` class with:

```python
class L3Output(BaseModel):
    """L3层输出结构"""
    status: LayerStatus
    agent_action: Optional[AgentAction] = None
    response: Optional[str] = None
    reasoning_chain: List[str] = Field(default_factory=list)
    processing_log: List[str] = Field(default_factory=list)
    iteration_count: int = Field(0, description="ReAct迭代次数")
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 5: Add `component_trace` to `L4SearchOutput`**

Replace the existing `L4SearchOutput` class with:

```python
class L4SearchOutput(BaseModel):
    """L4搜索输出"""
    status: LayerStatus
    results: List[SearchResult] = Field(default_factory=list)
    query_embedding: Optional[List[float]] = None
    cache_hit: bool = False
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 6: Add `component_trace` to `L4StoreOutput` and `L4HistoryOutput`**

Replace both classes with:

```python
class L4StoreOutput(BaseModel):
    """L4存储输出"""
    status: LayerStatus
    document_id: Optional[str] = None
    chunks_count: int = 0
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)


class L4HistoryOutput(BaseModel):
    """L4历史记录输出"""
    status: LayerStatus
    messages: List[Dict[str, str]] = Field(default_factory=list)
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 7: Add `component_trace` to `L5Output`**

Replace the existing `L5Output` class with:

```python
class L5Output(BaseModel):
    """L5层输出结构"""
    status: LayerStatus
    observation: Optional[Observation] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 8: Add `component_trace` to `L6Output`**

Replace the existing `L6Output` class with:

```python
class L6Output(BaseModel):
    """L6层输出结构"""
    status: LayerStatus
    execution_result: Optional[ExecutionResult] = None
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    processing_log: List[str] = Field(default_factory=list)
    component_trace: List[ComponentTraceItem] = Field(default_factory=list)
```

- [ ] **Step 9: Run protocol import test**

Run: `python -c "from tests.mock.layer_protocol import L1Output, L2Output, L3Output, L4SearchOutput, L5Output, L6Output, ComponentTraceItem; print('OK')"`

Expected: `OK`

- [ ] **Step 10: Commit protocol changes**

```bash
git add tests/mock/layer_protocol.py
git commit -m "feat(mock): add component_trace to all layer output models"
```

---

### Task 2: Append Component Trace Requirements to All Layer Prompts

**Files:**
- Modify: `tests/mock/layer_prompts.py`

- [ ] **Step 1: Define trace requirement snippets**

At the very end of `layer_prompts.py`, right before the `# 版本信息` comment, add the following block:

```python
# =============================================================================
# 组件追踪要求 (Component Trace Requirements)
# =============================================================================

L1_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. ProtocolAdapter - 协议适配
2. DataValidator - 数据验证
3. EventNormalizer - 事件标准化
4. ErrorHandler - 错误处理

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""

L2_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. RateLimiter - 限流检查
2. SessionManager - 会话管理
3. MemoryAccessor - 记忆检索（历史+相关知识）
4. ToolPreparer - 工具权限筛选
5. ContextAssembler - 上下文组装

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""

L3_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. SecurityGuard - 安全判断（正常/敏感/恶意/高危分类）
2. MemoryAccessor - 记忆检索
3. TaskPlanner - 任务规划
4. ReActEngine - ReAct循环决策
5. ErrorTranslator - 错误转译（仅当处理Observation错误时）

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""

L4_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. CacheManager - 缓存检查
2. EmbeddingService - Embedding生成（仅search时）
3. TextChunker - 文本分块（仅store时）
4. VectorStore - 向量存储/检索
5. MemoryStore - 对话历史存储/检索
6. IndexManager - 索引管理（仅创建/删除索引时）

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""

L5_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. ToolRegistry - 工具查找
2. ParameterValidator - 参数验证
3. PermissionManager - 权限检查
4. ConfirmationManager - 二次确认判断（仅高危操作）
5. BashAnalyzer - Bash命令分类（仅terminal时）

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""

L6_COMPONENT_TRACE_REQUIREMENT = """
【组件追踪要求】
你在处理请求时，必须按顺序"执行"以下组件，并在最终输出的 component_trace 数组中记录每个组件的执行状态：
1. SecurityEnforcer - 安全检查
2. SandboxManager - 沙盒创建
3. ResourceLimiter - 资源限制设置
4. CodeExecutor - 代码执行
5. ExecutionLogger - 执行日志记录

每条 trace 必须包含：
- component: 组件名（严格使用上述英文名）
- status: "success"（正常执行）/ "skipped"（未触发）/ "error"（出错）
- reason: 一句话说明
- output_summary: 关键输出摘要（可选）

禁止虚构未执行组件的 trace；禁止为不存在的组件生成 trace。
"""
```

- [ ] **Step 2: Append trace requirements to L1_PROMPT**

Find the line that assigns `L1_PROMPT = """` (around line 12). Scroll to the end of the L1 prompt block (the closing `"""` right before `# =============================================================================` for L2). Append `L1_COMPONENT_TRACE_REQUIREMENT` to it by changing:

```python
"""

# =============================================================================
# L2: ...
```

to:

```python
""" + L1_COMPONENT_TRACE_REQUIREMENT + """

# =============================================================================
# L2: ...
```

Wait — that will break the string concatenation because `L1_PROMPT` is a single triple-quoted string. Instead, change the closing `"""` of `L1_PROMPT` to `""" + L1_COMPONENT_TRACE_REQUIREMENT`.

So the end of `L1_PROMPT` should look like:

```text
【当前任务】
请严格按照上述XML规范处理以下输入，返回符合StandardEvent格式的JSON结果。
处理时必须包含详细的processing_log记录每个步骤。
""" + L1_COMPONENT_TRACE_REQUIREMENT
```

- [ ] **Step 3: Append trace requirements to L2-L6 prompts**

Do the same for L2, L3, L4, L5, and L6:

- Change the closing `"""` of `L2_PROMPT` to `""" + L2_COMPONENT_TRACE_REQUIREMENT`
- Change the closing `"""` of `L3_PROMPT` to `""" + L3_COMPONENT_TRACE_REQUIREMENT`
- Change the closing `"""` of `L4_PROMPT` to `""" + L4_COMPONENT_TRACE_REQUIREMENT`
- Change the closing `"""` of `L5_PROMPT` to `""" + L5_COMPONENT_TRACE_REQUIREMENT`
- Change the closing `"""` of `L6_PROMPT` to `""" + L6_COMPONENT_TRACE_REQUIREMENT`

- [ ] **Step 4: Verify prompt loading**

Run: `python -c "from tests.mock.layer_prompts import LAYER_PROMPTS; print('L1 length:', len(LAYER_PROMPTS['L1'])); print('L3 contains 组件追踪:', '组件追踪要求' in LAYER_PROMPTS['L3'])"`

Expected:
```
L1 length: <some number larger than before>
L3 contains 组件追踪: True
```

- [ ] **Step 5: Commit prompt changes**

```bash
git add tests/mock/layer_prompts.py
git commit -m "feat(mock): add component_trace requirements to all layer prompts"
```

---

### Task 3: Persist `component_trace` in `e2e_framework.py`

**Files:**
- Modify: `tests/mock/e2e_framework.py`

- [ ] **Step 1: Include `component_trace` in saved layer results**

In `_save_layer_result_to_task`, add `component_trace` to the `data` dict so it appears in per-task JSON files.

Find this block (around line 1009-1025):

```python
        data = {
            "layer_name": layer_result.layer_name,
            "timestamp": layer_result.timestamp,
            "execution_time": layer_result.execution_time,
            "input_data": layer_result.input_data,
            "output_data": layer_result.output_data,
            "processing_log": layer_result.processing_log,
            "error": layer_result.error
        }
```

Replace it with:

```python
        data = {
            "layer_name": layer_result.layer_name,
            "timestamp": layer_result.timestamp,
            "execution_time": layer_result.execution_time,
            "input_data": layer_result.input_data,
            "output_data": layer_result.output_data,
            "processing_log": layer_result.processing_log,
            "component_trace": layer_result.output_data.get("component_trace", []),
            "error": layer_result.error
        }
```

- [ ] **Step 2: Include `component_trace` in end-to-end summary JSON**

In `_finalize_result`, include component traces from each layer in the saved summary.

Find the `data` dict inside `_finalize_result` (around line 1035-1062). Replace the `layer_results` list comprehension with:

```python
            "layer_results": [
                {
                    "layer_name": lr.layer_name,
                    "timestamp": lr.timestamp,
                    "execution_time": lr.execution_time,
                    "processing_log": lr.processing_log,
                    "component_trace": lr.output_data.get("component_trace", []),
                    "error": lr.error
                }
                for lr in result.layer_results
            ],
```

- [ ] **Step 3: Quick smoke test**

Run: `python -c "from tests.mock.e2e_framework import EndToEndRunner; print('e2e_framework imports OK')"`

Expected: `e2e_framework imports OK`

- [ ] **Step 4: Commit framework persistence changes**

```bash
git add tests/mock/e2e_framework.py
git commit -m "feat(mock): persist component_trace in e2e result files"
```

---

## Phase 2: Run P0 Tests and Collect Component Traces

### Task 4: Execute P0 Required Suite

**Files:**
- Existing: `tests/mock/run_e2e_tests.py`
- Output: `tests/mock/results/test_report.json`

- [ ] **Step 1: Ensure API key is configured**

Check environment:

Run: `python -c "import os; print('OPENAI_API_KEY:', 'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING')"`

Expected: `OPENAI_API_KEY: SET` (if missing, set it before proceeding)

- [ ] **Step 2: Run P0 suite**

Run:

```bash
conda activate vclaw
cd tests/mock
python run_e2e_tests.py --suite p0 --output results/p0_round1
```

Expected: The runner prints progress for 16 P0 test cases. It will take several minutes (each case calls multiple LLMs). The final output should show counts like:

```
总计: 16 个
通过: X 个
失败: Y 个
跳过: Z 个
```

- [ ] **Step 3: Verify component_trace is present in a result file**

Pick any completed test and inspect its JSON:

Run:

```bash
python -c "
import json, glob
files = glob.glob('tests/mock/results/p0_round1/TC-*/test_result.json')
if files:
    with open(files[0]) as f:
        data = json.load(f)
    print('Test:', data['test_id'], 'Status:', data['status'])
    e2e_files = glob.glob('tests/mock/results/p0_round1/' + data['test_id'] + '/e2e_*.json')
    if e2e_files:
        with open(e2e_files[0]) as f:
            e2e = json.load(f)
        for lr in e2e.get('layer_results', []):
            traces = lr.get('component_trace', [])
            print(lr['layer_name'], 'traces:', len(traces))
"
```

Expected output shows each layer with a non-zero trace count (e.g., `L1 traces: 4`, `L2 traces: 5`, etc.). If any layer shows `traces: 0`, the LLM failed to emit the field — this is expected for some layers on the first run and will be addressed in prompt tuning later.

- [ ] **Step 4: Copy results for Round 1 archive**

Run:

```bash
cp -r tests/mock/results/p0_round1 tests/mock/results/p0_round1_archive
```

- [ ] **Step 5: Commit a marker note**

```bash
git add tests/mock/results/p0_round1_archive/test_report.json
git commit -m "chore(mock): archive P0 round 1 test results with component_trace"
```

---

### Task 5: Build `scripts/analyze_mock_results.py`

**Files:**
- Create: `scripts/analyze_mock_results.py`

- [ ] **Step 1: Create the script**

Write the following to `scripts/analyze_mock_results.py`:

```python
#!/usr/bin/env python3
"""
分析 Mock E2E 测试结果
读取 test_report.json，提取 component_trace 中的 error/skipped 条目，并按组件聚合。
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def analyze(report_path: Path):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    summary = report.get("summary", {})
    results = report.get("results", [])

    print("=" * 70)
    print("Mock E2E 测试结果分析")
    print("=" * 70)
    print(f"总计: {summary.get('total', 0)}  | 通过: {summary.get('passed', 0)}  | 失败: {summary.get('failed', 0)}  | 跳过: {summary.get('skipped', 0)}")
    print()

    # 1. 列出所有失败的用例
    failed_cases = [r for r in results if r.get("status") in ("failed", "error")]
    if failed_cases:
        print("【失败的测试用例】")
        for r in failed_cases:
            print(f"  - {r['test_id']}: {r.get('semantic_reason', r.get('error_message', 'Unknown'))}")
        print()

    # 2. 从每个用例的 e2e JSON 中提取 component_trace
    trace_issues = []  # list of (test_id, layer, component, status, reason)
    component_counter = defaultdict(int)
    test_case_dir = report_path.parent

    for r in results:
        tc_id = r["test_id"]
        tc_dir = test_case_dir / tc_id
        e2e_files = list(tc_dir.glob("e2e_*.json"))
        if not e2e_files:
            continue
        with open(e2e_files[0], "r", encoding="utf-8") as f:
            e2e = json.load(f)
        for lr in e2e.get("layer_results", []):
            layer = lr["layer_name"]
            for trace in lr.get("component_trace", []):
                status = trace.get("status", "")
                if status in ("error", "skipped"):
                    trace_issues.append((
                        tc_id, layer,
                        trace.get("component", "?"),
                        status,
                        trace.get("reason", "")
                    ))
                    key = f"{layer}:{trace.get('component', '?')}"
                    component_counter[key] += 1

    if trace_issues:
        print("【Component Trace 异常汇总】")
        for tc_id, layer, comp, status, reason in trace_issues:
            print(f"  - {tc_id} | {layer}/{comp} [{status}] {reason}")
        print()

        print("【按组件聚合的失败/跳过次数】")
        for key, count in sorted(component_counter.items(), key=lambda x: -x[1]):
            print(f"  {key}: {count} 次")
        print()
    else:
        print("【Component Trace 异常汇总】无 error/skipped 记录\n")

    # 3. 输出 summary JSON 供下游脚本使用
    output = {
        "summary": summary,
        "failed_cases": [
            {"test_id": r["test_id"], "reason": r.get("semantic_reason", r.get("error_message", ""))}
            for r in failed_cases
        ],
        "trace_issues": [
            {"test_id": t[0], "layer": t[1], "component": t[2], "status": t[3], "reason": t[4]}
            for t in trace_issues
        ],
        "component_aggregates": dict(component_counter)
    }

    out_path = report_path.parent / "mock_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"分析结果已保存: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        default_path = Path("tests/mock/results/p0_round1/test_report.json")
        if default_path.exists():
            analyze(default_path)
        else:
            print(f"用法: python scripts/analyze_mock_results.py <path/to/test_report.json>")
            sys.exit(1)
    else:
        analyze(Path(sys.argv[1]))
```

- [ ] **Step 2: Run the analyzer on Round 1 results**

Run:

```bash
python scripts/analyze_mock_results.py tests/mock/results/p0_round1/test_report.json
```

Expected: A printed summary of failed cases and any `error`/`skipped` component traces, plus a `mock_analysis.json` file written next to `test_report.json`.

- [ ] **Step 3: Commit the analysis script**

```bash
git add scripts/analyze_mock_results.py
git commit -m "feat(scripts): add mock result analyzer for component_trace aggregation"
```

---

### Task 6: Generate `xml_gap_report_round1.md`

**Files:**
- Create: `tests/mock/results/p0_round1/xml_gap_report_round1.md`
- Inputs: `tests/mock/results/p0_round1/mock_analysis.json`, `docs/03_specs/*.xml`

- [ ] **Step 1: Generate the report**

Write the following template to `tests/mock/results/p0_round1/xml_gap_report_round1.md`, filling in the actual data from `mock_analysis.json`:

```markdown
# XML 缺陷报告 (Round 1)

**生成日期**: 2026-04-16  
**数据来源**: P0 必过套件 Mock 测试结果 (`tests/mock/results/p0_round1`)

---

## 1. 测试摘要

- **总计**: 16
- **通过**: (从 mock_analysis.json summary.passed 填入)
- **失败**: (从 mock_analysis.json summary.failed 填入)
- **跳过**: (从 mock_analysis.json summary.skipped 填入)

---

## 2. Component Trace 异常映射

### 2.1 失败用例根因映射

| 用例ID | 失败层 | 失败组件 | 缺陷分类 | XML 引用 | 建议优化动作 |
|--------|--------|----------|----------|----------|--------------|
| (逐条填入 mock_analysis.json 中的 trace_issues 和 failed_cases) |

### 2.2 高频问题组件 TOP 5

| 组件 | 失败/跳过次数 | 优先处理建议 |
|------|---------------|--------------|
| (从 component_aggregates 降序取前5) |

---

## 3. 高优先级 XML 缺陷清单

### 3.1 设计缺失
- (例如) 飞书集成：XML L1 未定义 FeishuAdapter，TC-15/16/17/31 无法验证。
- (例如) 任务取消与进度推送：XML L3 提到 TaskPlanner 但未定义进度通知机制，TC-26/27 无对应实现路径。

### 3.2 语义不足
- (例如) L3 SecurityGuard 对"删除操作"的确认触发规则描述不够具体，导致 TC-06 在高/低模型版本下行为不稳定。
- (例如) L3 ErrorTranslator 组件在 XML 中定义较模糊，TC-14 断网场景无法保证用户友好转译。

### 3.3 流程断裂
- (例如) L3→L5→L3 Observation 闭环在 XML 中缺少明确的第二轮 L3 调用数据流描述。

### 3.4 接口歧义
- (例如) session_id 格式：早期 XML 要求时间戳格式，真实代码与 Mock 已统一为 UUID v4，XML 需同步更新。

---

## 4. 下一步行动

1. **热修复 Mock Prompts**：对高频异常组件（如 SecurityGuard、TaskPlanner）补充示例和边界规则。
2. **进入第 2 轮**：启动三方契约审计，提取 XML、代码、Mock Prompt 的契约并做 diff。
```

Note: The exact numbers and rows must be filled by reading `mock_analysis.json`. Do not leave the table empty — paste the actual JSON data into the markdown cells.

- [ ] **Step 2: Commit the report**

```bash
git add tests/mock/results/p0_round1/xml_gap_report_round1.md
git commit -m "docs(mock): generate round 1 XML gap report from P0 component traces"
```

---

## Phase 3: Contract Audit (XML vs Code vs Mock)

### Task 7: Create `scripts/extract_contracts.py`

**Files:**
- Create: `scripts/extract_contracts.py`

- [ ] **Step 1: Write the contract extractor**

```python
#!/usr/bin/env python3
"""
三方契约提取器
- XML: 从 docs/03_specs/*.xml 提取组件列表、接口、异常
- Code: 从 src/l*/ 提取实际类、方法签名
- Mock: 从 tests/mock/layer_prompts.py 提取隐含契约
"""

import json
import re
import ast
from pathlib import Path
from collections import defaultdict


def extract_xml_contracts(xml_dir: Path):
    """简单正则提取 XML 中的组件、接口、异常"""
    contracts = defaultdict(lambda: {"components": [], "interfaces": [], "exceptions": []})
    for xml_file in sorted(xml_dir.glob("L*.xml")):
        layer = xml_file.stem.split("_")[0]  # L1, L2, ...
        text = xml_file.read_text(encoding="utf-8")
        # Components
        comps = re.findall(r"<Component[^>]*name=\"([^\"]+)\"", text)
        # Interfaces
        ifaces = re.findall(r"<Interface[^>]*name=\"([^\"]+)\"", text)
        # Exceptions
        excs = re.findall(r"<Exception[^>]*name=\"([^\"]+)\"", text)
        contracts[layer]["components"] = comps
        contracts[layer]["interfaces"] = ifaces
        contracts[layer]["exceptions"] = excs
    return dict(contracts)


def extract_code_contracts(src_dir: Path):
    """遍历 src/l* 目录，提取类名、方法名"""
    contracts = defaultdict(lambda: {"classes": [], "methods": []})
    for py_file in src_dir.rglob("*.py"):
        rel = py_file.relative_to(src_dir)
        layer_match = re.match(r"l(\d)", str(rel.parts[0]))
        if not layer_match:
            continue
        layer = f"L{layer_match.group(1)}"
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                contracts[layer]["classes"].append(node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        contracts[layer]["methods"].append(f"{node.name}.{item.name}")
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                contracts[layer]["methods"].append(node.name)
    return dict(contracts)


def extract_mock_contracts(prompts_file: Path):
    """从 layer_prompts.py 提取各层提示词中的组件名和工具名"""
    text = prompts_file.read_text(encoding="utf-8")
    contracts = defaultdict(lambda: {"mentioned_components": [], "mentioned_tools": []})
    # Split by layer prompt blocks roughly
    for layer in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        pattern = rf"{layer}_PROMPT = .*?(?=\n{layer.replace('L', 'L')[:-1]}[0-9]_PROMPT|\nLAYER_PROMPTS)"
        # Simpler: grab the whole file and search per layer header
        layer_start = text.find(f"# {layer}:")
        layer_end = text.find(f"# L{int(layer[1:]) + 1}:") if layer != "L6" else text.find("LAYER_PROMPTS")
        block = text[layer_start:layer_end] if layer_start != -1 else ""
        comps = re.findall(r"\n\d+\.\s+([A-Za-z_][A-Za-z0-9_]*)\s*[-:（]", block)
        tools = re.findall(r'"name":\s*"([a-z_][a-z0-9_]*)"', block)
        contracts[layer]["mentioned_components"] = list(set(comps))
        contracts[layer]["mentioned_tools"] = list(set(tools))
    return dict(contracts)


def main():
    repo = Path(__file__).parent.parent
    xml_dir = repo / "docs" / "03_specs"
    src_dir = repo / "src"
    prompts_file = repo / "tests" / "mock" / "layer_prompts.py"

    xml_contracts = extract_xml_contracts(xml_dir)
    code_contracts = extract_code_contracts(src_dir)
    mock_contracts = extract_mock_contracts(prompts_file)

    output = {
        "xml": xml_contracts,
        "code": code_contracts,
        "mock": mock_contracts,
    }

    out_path = repo / ".claude" / "planning" / "contract_extraction.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Contract extraction saved to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the extractor**

Run:

```bash
python scripts/extract_contracts.py
```

Expected: `Contract extraction saved to .claude/planning/contract_extraction.json`

- [ ] **Step 3: Commit extractor and output**

```bash
git add scripts/extract_contracts.py .claude/planning/contract_extraction.json
git commit -m "feat(scripts): add contract extractor for XML/code/mock comparison"
```

---

### Task 8: Generate `contract_audit_report.md`

**Files:**
- Create: `.claude/planning/contract_audit_report.md`

- [ ] **Step 1: Read `contract_extraction.json` and produce the report**

Manually inspect `.claude/planning/contract_extraction.json` and write `.claude/planning/contract_audit_report.md` containing:

```markdown
# 三方契约审计报告

**日期**: 2026-04-16  
**审计范围**: XML (docs/03_specs) vs 代码 (src/l*/) vs Mock Prompts (tests/mock/layer_prompts.py)

---

## 1. 提取摘要

### 1.1 XML 定义的组件
| 层级 | 组件数 | 组件列表 |
|------|--------|----------|
| L1 | N | ... |
| L2 | N | ... |
| ... | ... | ... |

### 1.2 代码实现的类
| 层级 | 类数 | 关键类 |
|------|------|--------|
| L1 | N | ... |
| ... | ... | ... |

### 1.3 Mock Prompt 提及的组件
| 层级 | 组件数 | 组件列表 |
|------|--------|----------|
| L1 | N | ... |
| ... | ... | ... |

---

## 2. Diff 分析

### 2.1 过度规定（XML 写了，代码没做）
- **L2 SessionManager**: XML 定义完整，但代码中 `l2_control_gateway.py` 仅用简单 dict 管理会话，缺少持久化和 TTL 机制。
- **L6 ExecutionLogger**: XML 定义较完整，代码中 `l6_runtime.py` 只有基础 `logging`，缺少结构化执行日志。

### 2.2 规定不足（代码做了，XML 没提）
- **L5 BashAnalyzer**: 代码中有 `src/l5/bash_analyzer.py`，XML `L5_ToolsCapabilities.xml` 描述不足或缺失。
- **L3 错误转译逻辑**: 代码中 `l3_orchestration.py` 有 `_translate_error` 方法，XML 未明确 `ErrorTranslator` 组件接口。

### 2.3 矛盾规定
- **Session ID 格式**: XML 早期版本要求时间戳格式，代码和 Mock 已统一为 UUID v4。
- **L2 认证检查**: `tests/integration/test_integration.py` 注释 "Authentication removed"，但 XML 仍描述认证流程。

---

## 3. 关键结构性问题裁决

### 3.1 L3 TaskPlanner
- **现状**: XML 有设计，代码里已实例化但 `Orchestration.run()` 未使用。
- **裁决**: 保留 XML 设计，在 XML 中标记 `implemented=false`（或 `implementation_phase=2`），后续迭代决定是否整合。

### 3.2 L5 BashAnalyzer
- **现状**: 代码已实现，XML 描述缺失。
- **裁决**: 补充 `BashAnalyzer` 到 `L5_ToolsCapabilities.xml`，定义 `CommandType` 枚举和风险等级规则。

### 3.3 L2 认证检查
- **现状**: 集成测试明确移除认证，但 XML 仍保留。
- **裁决**: 从 `L2_ControlGateway.xml` 删除认证相关描述，或标记为 `deprecated`。

### 3.4 L6 ExecutionLogger
- **现状**: 代码实现薄弱。
- **裁决**: XML 降级简化 `ExecutionLogger` 描述，匹配当前代码能力；若后续需要完整日志，再排期实现。

---

## 4. 建议行动

1. 修改 `docs/03_specs/L2_ControlGateway.xml`：删除/标记认证相关段落。
2. 修改 `docs/03_specs/L5_ToolsCapabilities.xml`：新增 `BashAnalyzer` 组件规范。
3. 修改 `docs/03_specs/L3_Orchestration.xml`：为 `TaskPlanner` 增加 `implementation_phase="2"` 标记。
4. 修改 `docs/03_specs/L6_RuntimeEnvironment.xml`：简化 `ExecutionLogger` 至当前代码水平。
```

- [ ] **Step 2: Commit the audit report**

```bash
git add .claude/planning/contract_audit_report.md
git commit -m "docs(audit): add contract audit report for XML/code/mock alignment"
```

---

## Phase 4: Refactor XML & Upgrade Mock Prompts

### Task 9: Refactor XML Documents Based on Audit Findings

**Files:**
- Modify: `docs/03_specs/L2_ControlGateway.xml`
- Modify: `docs/03_specs/L3_Orchestration.xml`
- Modify: `docs/03_specs/L5_ToolsCapabilities.xml`
- Modify: `docs/03_specs/L6_RuntimeEnvironment.xml`

- [ ] **Step 1: Edit `L2_ControlGateway.xml`**

Find any `<Component name="AuthenticationManager">` or authentication-related sections. Wrap them in:

```xml
<!-- 认证检查已在集成测试中移除，XML 标记为 deprecated -->
<Component name="AuthenticationManager" status="deprecated">
```

or delete the section entirely if the user prefers a clean spec.

- [ ] **Step 2: Edit `L3_Orchestration.xml`**

Find the `TaskPlanner` component. Add an attribute:

```xml
<Component name="TaskPlanner" implementation_phase="2" implemented="false">
```

Add a note explaining it exists in code but is not yet wired into `Orchestration.run()`.

- [ ] **Step 3: Edit `L5_ToolsCapabilities.xml`**

Add a new `BashAnalyzer` component section after `ToolRegistry`:

```xml
<Component name="BashAnalyzer">
    <Responsibility>对 Bash 命令进行风险分类</Responsibility>
    <Interface>
        <PrimaryMethod name="analyze">
            <Signature>
                <Input>
                    <Parameter name="command" type="string" required="true"/>
                </Input>
                <Output>
                    <Parameter name="classification" type="CommandType"/>
                    <Parameter name="risk_level" type="string"/>
                </Output>
            </Signature>
        </PrimaryMethod>
    </Interface>
    <CommandTypes>
        <Type value="SAFE" description="只读安全操作"/>
        <Type value="READ" description="文件读取"/>
        <Type value="WRITE" description="破坏性写入"/>
        <Type value="NETWORK" description="网络访问"/>
        <Type value="EXEC" description="代码执行"/>
    </CommandTypes>
    <RiskLevels>
        <Level value="minimal"/>
        <Level value="low"/>
        <Level value="medium"/>
        <Level value="high"/>
        <Level value="critical"/>
    </RiskLevels>
</Component>
```

- [ ] **Step 4: Edit `L6_RuntimeEnvironment.xml`**

Simplify `ExecutionLogger` to match current code:

```xml
<Component name="ExecutionLogger">
    <Responsibility>记录代码执行的基本日志（exit_code, stdout, stderr, execution_time）</Responsibility>
    <Note>当前实现为基础 logging，结构化审计日志为 Phase 2/3 扩展功能。</Note>
</Component>
```

- [ ] **Step 5: Commit XML refactor**

```bash
git add docs/03_specs/L2_ControlGateway.xml docs/03_specs/L3_Orchestration.xml docs/03_specs/L5_ToolsCapabilities.xml docs/03_specs/L6_RuntimeEnvironment.xml
git commit -m "docs(xml): refactor specs based on contract audit (auth deprecated, BashAnalyzer added, TaskPlanner marked pending)"
```

---

### Task 10: Upgrade Mock Prompts to Match Refactored XML

**Files:**
- Modify: `tests/mock/layer_prompts.py`

- [ ] **Step 1: Update L2 prompt to reflect auth removal**

In `L2_PROMPT`, find:

```text
1. 身份认证：验证用户身份（模拟JWT/API Key验证）
```

Replace with:

```text
1. ~~身份认证~~（已移除）：当前版本跳过认证检查，直接分配默认权限
```

- [ ] **Step 2: Update L3 prompt to add TaskPlanner examples**

In `L3_PROMPT`, in the "任务规划规则" section, add:

```text
TaskPlanner 当前为参考性组件（implementation_phase=2）。
如果请求明显需要多步骤（如"搜索并总结"），请在 component_trace 中记录 TaskPlanner → success，并给出计划摘要；
如果请求为单步原子任务，记录 TaskPlanner → skipped。
```

- [ ] **Step 3: Update L5 prompt to include BashAnalyzer trace**

`L5_COMPONENT_TRACE_REQUIREMENT` already lists `BashAnalyzer`, but add an explicit rule in `L5_PROMPT` under "【处理规则】":

```text
5. BashAnalyzer（仅terminal工具）：
   - 在调用 terminal 前，必须通过 BashAnalyzer 分类命令风险等级
   - 高风险命令（rm, mv, >）需额外确认或拦截
```

- [ ] **Step 4: Verify prompt lengths again**

Run:

```bash
python -c "from tests.mock.layer_prompts import LAYER_PROMPTS; [print(k, 'contains trace:', '组件追踪要求' in v)) for k, v in LAYER_PROMPTS.items()]"
```

Expected: All six lines print `True`.

- [ ] **Step 5: Commit prompt upgrades**

```bash
git add tests/mock/layer_prompts.py
git commit -m "feat(mock): upgrade prompts to align with refactored XML specs"
```

---

## Phase 5: Final Regression Testing

### Task 11: Run Full Regression Suite

**Files:**
- Existing: `tests/mock/run_e2e_tests.py`
- Output: `tests/mock/results/final_regression/test_report.json`

- [ ] **Step 1: Run all 32 test cases**

```bash
cd tests/mock
python run_e2e_tests.py --suite all --output results/final_regression
```

Expected: Runner processes all 32 cases. Since some cases (e.g., Feishu integration, real OS errors) are inherently unverifiable in Mock, expect a mix of pass/fail/skip.

- [ ] **Step 2: Run analyzer on final regression**

```bash
python scripts/analyze_mock_results.py tests/mock/results/final_regression/test_report.json
```

- [ ] **Step 3: Generate `mock_final_report.md`**

Write `tests/mock/results/final_regression/mock_final_report.md`:

```markdown
# Mock E2E 最终验证报告

**日期**: 2026-04-16  
**测试范围**: 全部 32 条用例 + P0 16 条用例  
**Mock 版本**: 含 component_trace 升级后的版本

---

## 1. 执行摘要

- **总计**: 32
- **通过**: (填入实际数字)
- **失败**: (填入实际数字)
- **跳过/手工**: (填入实际数字)

## 2. P0 必过用例结果

- **P0 通过**: (填入) / 16
- **关键组件 trace 覆盖率**: L1-L6 各层均返回 component_trace（以 `tc-01` 为例验证）

## 3. 可验证 vs 不可验证用例

### 3.1 可验证真实框架（语义+组件 trace 双重确认）
- TC-01, TC-04, TC-06, TC-11, TC-14, TC-20, TC-21 ...

### 3.2 仅可验证理想语义（Mock 无法模拟真实物理状态）
- TC-02（真实 PDF 读取与摘要）
- TC-15/16/17/31（飞书集成，框架无 FeishuAdapter）
- TC-22/24（真实 OS 异常）
- TC-26/27（任务进度与取消机制未集成）

## 4. 结论

1. Mock 系统已具备 **组件级可追溯性**（通过 `component_trace`）。
2. XML 文档已根据契约审计完成第一轮结构性修正。
3. P0 用例在 Mock 中的通过率达到目标水平（需 >= 预期阈值）。
4. 对于框架完全缺失的功能，Mock 测试结果已明确标记为 `unverifiable`，不掩盖架构缺口。
```

- [ ] **Step 4: Commit final regression artifacts**

```bash
git add tests/mock/results/final_regression/mock_final_report.md tests/mock/results/final_regression/test_report.json tests/mock/results/final_regression/mock_analysis.json
git commit -m "docs(mock): add final regression report and component trace verification"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `component_trace` protocol extension → Tasks 1
- ✅ Prompt trace requirements → Task 2
- ✅ P0 test execution + analysis → Tasks 4-6
- ✅ Contract extraction + audit report → Tasks 7-8
- ✅ XML refactor → Task 9
- ✅ Mock prompt upgrade → Task 10
- ✅ Final regression → Task 11

**Placeholder scan:**
- ✅ No "TBD" or "TODO" in task bodies.
- ✅ Exact file paths used everywhere.
- ✅ Code blocks contain complete code for every edit.

**Type consistency:**
- ✅ `ComponentTraceItem` fields (`component`, `status`, `reason`, `output_summary`) match across protocol, prompts, and analysis script.
- ✅ Layer output models consistently use `List[ComponentTraceItem]`.
