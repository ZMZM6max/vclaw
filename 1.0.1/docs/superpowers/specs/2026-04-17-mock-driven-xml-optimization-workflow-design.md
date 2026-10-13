# Mock-Driven XML Optimization Workflow Design

> **生成日期**: 2026-04-17  
> **目标**: 建立一套可复用、半自动化的工作流，利用 Mock E2E 测试结果持续发现 VClaw XML 架构文档中的偏差，并以 diff patch + 报告的形式输出，供人工审查后应用。

---

## 1. 设计目标与范围

### 1.1 目标

- **不自动修改 XML**：工作流只生成补丁和报告，所有修改必须经过人工审查。
- **全覆盖偏差类型**：组件级、接口级、数据流/规则级、测试覆盖率级。
- **可复用与自动化**：每次运行 Mock 测试后可自动触发，增量更新分析结果。
- **人机结合**：确定性规则引擎处理结构性偏差，LLM 处理语义/数据流偏差。

### 1.2 范围

| 覆盖项 | 说明 |
|--------|------|
| XML 文档 | `docs/03_specs/L3_Orchestration.xml`、`L5_ToolsCapabilities.xml`、`L6_RuntimeEnvironment.xml` 等 |
| Mock Prompt | `tests/mock/layer_prompts.py` |
| 测试数据 | `tests/mock/results/<run_id>/test_report.json`、`mock_analysis.json` |
| 代码契约快照 | `.claude/planning/contract_extraction.json`（静态快照，不重新解析源码） |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Mock-Driven XML Optimization Workflow            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 0: Mock E2E 测试运行                                                │
│   run_e2e_tests.py --suite all → test_report.json + component_trace     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Contract增量准备                                                 │
│   - 读取 XML 文档，提取组件、接口、数据流定义                            │
│   - 读取 layer_prompts.py，提取 Prompt 中提及的组件                      │
│   - 读取 contract_extraction.json（代码契约静态快照）                    │
│   - 输出: contract_snapshot.json                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: RuleEngine（确定性规则）                                         │
│   R1-R7 检测结构性/覆盖性偏差                                            │
│   - 输出: rule_findings.json                                            │
│   - 输出: auto_patch.patch（可直接 git apply --check 的规则补丁）        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: LLM Semantic Review（语义审查）                                  │
│   - 输入: contract_snapshot + rule_findings + 测试失败用例 trace         │
│   - LLM 分析数据流、时序、规则缺失、Prompt-XML 语义不一致                │
│   - 输出: llm_review.json + llm_suggestions.patch                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: ReportMerger（报告合并）                                         │
│   - 合并 rule_findings + llm_review                                    │
│   - 生成 xml_optimization_report.md（含 6 大章节）                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step 1: 增量契约准备（Contract Preparation）

### 3.1 输入

| 输入源 | 文件路径 | 说明 |
|--------|----------|------|
| XML 架构文档 | `docs/03_specs/*.xml` | 当前版本的 XML 设计文档 |
| Mock Prompt | `tests/mock/layer_prompts.py` | 模拟 LLM 的系统提示词 |
| 代码契约快照 | `.claude/planning/contract_extraction.json` | 静态代码契约，不重新解析源码 |

### 3.2 输出

**`contract_snapshot.json`** 结构：

```json
{
  "generated_at": "2026-04-17T10:00:00Z",
  "xml_contracts": {
    "L3_Orchestration": {
      "components": [{"name": "ReActEngine", "status": "implemented", ...}],
      "interfaces": [...],
      "dataflows": [...]
    },
    "L5_ToolsCapabilities": { ... },
    "L6_RuntimeEnvironment": { ... }
  },
  "mock_prompt_contracts": {
    "L1": {"mentioned_components": ["ProtocolAdapter", "DataValidator"]},
    "L2": {"mentioned_components": ["RateLimiter", "SessionManager"]},
    "L3": {"mentioned_components": ["ReActEngine", "TaskPlanner", ...]},
    "L5": {"mentioned_components": ["ToolRegistry", "BashAnalyzer", ...]},
    "L6": {"mentioned_components": ["RuntimeEnvironment", "SecurityEnforcer"]}
  },
  "code_contracts": {
    // 直接加载 contract_extraction.json 的内容
  }
}
```

### 3.3 实现说明

- **XML 解析**：使用 `xml.etree.ElementTree` 提取 `<component>`、`<interface>`、`<dataflow>` 节点。
- **Prompt 解析**：使用正则提取 `layer_prompts.py` 中各 Layer 系统提示词，再提取其中大写的 CamelCase 单词作为 "mentioned_components"。
- **代码契约**：直接加载 `.claude/planning/contract_extraction.json`，**不读取 `src/` 源码**。

---

## 4. Step 2: RuleEngine（确定性规则 R1-R7）

RuleEngine 基于 `contract_snapshot.json` 和 `mock_analysis.json` 中的 `component_trace` 数据运行 7 条规则。

### 4.1 R1: XML 中缺失但在 Trace 中出现的组件

**条件**：某组件在 `component_trace` 中出现过（active/skipped/error），但在对应 Layer 的 XML 中无定义。  
**动作**：在 XML 中新增 `<component>` 占位定义，标记 `implemented="false"`，并在报告中标注为 "Missing in XML"。

### 4.2 R2: XML 中有定义但所有 32 个测试均未触发的组件

**条件**：
1. 组件在 XML 中有定义；
2. 该组件在全部 32 个测试的 `component_trace` 中**从未出现**（包括 active/skipped/error）。  

**保守判定**：即使条件 1、2 满足，还需由分析器判断该组件是否对系统**没有任何作用**（即：移除它不会降低系统能力）。判断标准如下（需同时满足）：
- XML 中该组件**没有定义任何接口**（`<interface>` 节点为空或不存在）；
- XML 中该组件**未被任何数据流引用**（无 `<dataflow>` 指向或来自它）；
- XML 中该组件**未被其他组件显式依赖**；
- `contract_extraction.json` 中**没有任何代码引用**该组件的类/函数签名。

如果上述任意一条不满足，则**不建议删除**，只报告 "Underutilized"。  

**动作**：仅在 "确实无系统价值" 时生成删除 patch，否则仅记录为低优先级观察项。

### 4.3 R3: XML 与代码契约快照不一致的组件状态

**条件**：XML 中组件的 `implemented` 或 `implementation_phase` 与 `contract_extraction.json` 中的记录不一致。  
**动作**：生成 patch，将 XML 中的状态修正为与代码契约快照一致。

### 4.4 R4: Prompt 中提及但 XML 中无定义的组件

**条件**：`layer_prompts.py` 某 Layer 的 Prompt 中提到了一个组件，但该组件在对应 Layer 的 XML 中无定义。  

**保守判定**：需分析该组件是否对目前系统**没有任何好处**。如果它只是尚未实现但未来有价值，则标记为 `[PROMPT_FIX]`（建议修改 Prompt 而非 XML）。  

**动作**：
- 若组件应属于该 Layer 设计 → 在 XML 中新增组件定义。
- 若组件不应在 Prompt 中出现 → 标记 `[PROMPT_FIX]`，生成 `layer_prompts.py` 的 patch。

### 4.5 R5: Prompt 与 XML 的接口/规则描述不一致

**条件**：Prompt 中对某组件行为的描述与 XML 中的接口签名、规则编号、或风险等级不一致。  
**动作**：标记 `[PROMPT_FIX]` 或 XML patch，视偏差来源而定。

### 4.6 R6: 跨层依赖与 XML 声明不一致

**条件**：`contract_extraction.json` 中记录的跨层依赖关系与 XML `<dependencies>` 节点不一致。  
**动作**：生成 XML patch 修正依赖声明。

### 4.7 R7: 覆盖率异常（关键组件从未 active）

**条件**：某组件在 XML 中被标记为 `critical="true"` 或属于核心流程，但在全部 32 个测试的 `component_trace` 中**从未处于 `active` 状态**。  
**动作**：报告为 "Coverage Gap - Critical Component Never Active"，建议补充测试用例，**不删除组件**。

### 4.8 RuleEngine 输出

- **`rule_findings.json`**：每条规则触发的详细记录（含 severity、confidence、source_rule）。
- **`auto_patch.patch`**：所有确定性补丁的合并 diff，可用 `git apply --check` 验证。

---

## 5. Step 3: LLM Semantic Review

### 5.1 输入

- `contract_snapshot.json`
- `rule_findings.json`
- 测试失败用例的 `component_trace` 和 LLM 对话历史（从 `mock_analysis.json` 提取）
- 用户自定义问题模板（可选）

### 5.2 LLM 分析任务

LLM 负责以下语义层审查：

1. **Trace 异常解释**：为什么某测试失败了？`component_trace` 的时序是否合理？
2. **数据流偏差**：XML 中描述的数据流与实际 trace 中的调用顺序是否一致？
3. **规则缺失**：测试失败是否因为 XML 中缺少某条规则的定义（如 ErrorTranslator 的转译规则）？
4. **Prompt-XML 语义不一致**：Prompt 中的安全策略、路径处理规则是否与 XML 设计文档矛盾？

### 5.3 输出

- **`llm_review.json`**：结构化审查结果。

```json
{
  "semantic_findings": [
    {
      "id": "LLM-01",
      "layer": "L3",
      "component": "ErrorTranslator",
      "issue_type": "missing_rules",
      "description": "XML 中未定义 ErrorTranslator 组件，也未定义 502/API 错误转译规则。",
      "recommendation": "在 L3_Orchestration.xml 中新增 ErrorTranslator 组件，并补充 error_translation_rules 节点。",
      "affected_test_cases": ["TC-14", "TC-25"],
      "patch_target": "xml"
    },
    {
      "id": "LLM-02",
      "layer": "L3",
      "component": "ReActEngine",
      "issue_type": "prompt_semantic_gap",
      "description": "ReActEngine 在空文件读取、模糊文件名匹配等场景下输出不符合预期。",
      "recommendation": "在 layer_prompts.py 的 L3 Prompt 中补充空文件处理和模糊匹配的输出示例。",
      "affected_test_cases": ["TC-10", "TC-23"],
      "patch_target": "prompt"
    }
  ]
}
```

- **`llm_suggestions.patch`**：由 LLM 生成的建议性 patch（与 `auto_patch.patch` 分离，便于区分确定性修改与建议性修改）。

### 5.4 `[PROMPT_FIX]` 标记规范

当 LLM 发现偏差来源于 Prompt 而非 XML 时，必须在 `llm_review.json` 中设置：

```json
{
  "patch_target": "prompt",
  "tags": ["[PROMPT_FIX]"]
}
```

---

## 6. Step 4: ReportMerger（报告合并）

### 6.1 输出文件

**`xml_optimization_report.md`** 必须包含以下 6 个章节：

1. **执行摘要**：本次分析的时间范围、测试数量、规则触发数、LLM 发现数。
2. **组件级偏差**：R1、R2、R3、R7 的结果 + LLM 组件相关发现。
3. **接口级偏差**：R5、R6 的结果 + LLM 接口相关发现。
4. **数据流/规则级偏差**：数据流时序不一致、规则缺失、ErrorTranslator 等设计缺口。
5. **测试覆盖率级偏差**：R7 结果、关键组件未激活列表、建议补充的测试用例。
6. **建议补丁清单**：列出 `auto_patch.patch` 和 `llm_suggestions.patch` 中的每个变更，标注来源（Rule/LLM）和审查建议。

### 6.2 报告位置

- 默认保存到 `tests/mock/results/<run_id>/xml_optimization_report.md`
- 同时复制一份到 `.claude/planning/mock_xml_optimization_latest.md` 作为最新快照

---

## 7. Step 5: 自动触发机制

### 7.1 集成点

在 `tests/mock/run_e2e_tests.py` 中增加 `--analyze` 选项：

```bash
# 运行全部测试并自动触发分析
python tests/mock/run_e2e_tests.py --suite all --analyze

# 仅运行测试，不触发分析（默认行为不变）
python tests/mock/run_e2e_tests.py --suite all
```

### 7.2 触发流程

当 `--analyze` 传入时，测试完成后自动：

1. 调用 `scripts/prepare_contracts.py` 生成 `contract_snapshot.json`
2. 调用 `scripts/rule_engine.py` 生成 `rule_findings.json` + `auto_patch.patch`
3. 调用 `scripts/llm_review.py` 生成 `llm_review.json` + `llm_suggestions.patch`
4. 调用 `scripts/merge_report.py` 生成 `xml_optimization_report.md`
5. 在终端输出报告路径和关键统计摘要

### 7.3 增量更新策略

- 每次运行使用 `run_id = 当前日期时间`（如 `2026-04-17-1030`）。
- 新结果保存在 `tests/mock/results/<run_id>/`。
- 保留历史结果，便于对比趋势。

---

## 8. Step 6: 边界与异常处理

### 8.1 XML 解析失败

- 若某 XML 文件格式错误，RuleEngine 跳过该文件并在报告中记录 `PARSE_ERROR`。
- 不影响其他 XML 文件的分析。

### 8.2 contract_extraction.json 缺失或过期

- 若文件不存在，脚本报错并提示用户："请先生成代码契约快照，或更新 contract_extraction.json"。
- **不自动回退到读取源码**，以遵守设计约束。

### 8.3 LLM API 不可用

- 若 LLM Review 步骤因 API 限制/无网络失败，RuleEngine 的结果和 `auto_patch.patch` 仍然保留。
- 报告中 LLM 章节标注为 "LLM review skipped due to API unavailability"。

### 8.4 Patch 无法应用

- 所有 patch 生成后必须通过 `git apply --check` 验证。
- 若验证失败，标记为 `PATCH_CONFLICT` 并在报告中提示人工审查。

### 8.5 零发现

- 若 RuleEngine 和 LLM 均未发现偏差，报告明确输出 "No deviations detected in this run"。

---

## 9. 文件与目录规划

### 9.1 新增脚本

| 脚本 | 路径 | 职责 |
|------|------|------|
| `prepare_contracts.py` | `tests/mock/scripts/prepare_contracts.py` | Step 1: 生成 contract_snapshot.json |
| `rule_engine.py` | `tests/mock/scripts/rule_engine.py` | Step 2: 运行 R1-R7 |
| `llm_review.py` | `tests/mock/scripts/llm_review.py` | Step 3: LLM 语义审查 |
| `merge_report.py` | `tests/mock/scripts/merge_report.py` | Step 4: 合并报告 |

### 9.2 输出目录

```
tests/mock/results/
├── <run_id>/
│   ├── test_report.json
│   ├── mock_analysis.json
│   ├── contract_snapshot.json
│   ├── rule_findings.json
│   ├── auto_patch.patch
│   ├── llm_review.json
│   ├── llm_suggestions.patch
│   └── xml_optimization_report.md
└── final_regression/          (保留用于对比的基准结果)
```

### 9.3 需修改的现有文件

- `tests/mock/run_e2e_tests.py`：增加 `--analyze` 参数和自动触发逻辑。

---

## 10. 下一步工作

本设计文档获批后，将按以下顺序实施：

1. 创建 `tests/mock/scripts/` 目录和 4 个脚本文件。
2. 实现 `prepare_contracts.py`（XML + Prompt + 快照加载）。
3. 实现 `rule_engine.py`（R1-R7）。
4. 实现 `llm_review.py`（LLM 语义审查 Pipeline）。
5. 实现 `merge_report.py`（报告生成）。
6. 修改 `run_e2e_tests.py` 集成 `--analyze`。
7. 用现有的 `final_regression` 数据做一次完整流程验证。
