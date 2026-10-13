# XML 优化报告
**生成时间**: 2026-04-20T19:50:45.880884  
## 1. 执行摘要
| 指标 | 数值 |
|------|------|
| 总计用例 | 32 |
| 通过 | 3 |
| 失败 | 19 |
| 跳过 | 10 |
| 规则发现 | 12 |
| LLM 发现 | 8 |

## 2. 组件级偏差
### R1: XML 中缺失但在 Trace 中出现的组件

### R2/R3/R7: 组件状态与覆盖率偏差
- **L4** `VectorStore` (R2): Component 'VectorStore' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `EmbeddingService` (R2): Component 'EmbeddingService' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `TextChunker` (R2): Component 'TextChunker' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `MemoryStore` (R2): Component 'MemoryStore' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `IndexManager` (R2): Component 'IndexManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L4** `CacheManager` (R2): Component 'CacheManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `SandboxManager` (R2): Component 'SandboxManager' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `ResourceLimiter` (R2): Component 'ResourceLimiter' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `CodeExecutor` (R2): Component 'CodeExecutor' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `DockerController` (R2): Component 'DockerController' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `SecurityEnforcer` (R2): Component 'SecurityEnforcer' is defined in XML but never touched in tests. It has references, so marked as Underutilized.
- **L6** `ExecutionLogger` (R2): Component 'ExecutionLogger' is defined in XML but never touched in tests. It has references, so marked as Underutilized.

### LLM 组件相关发现
- **L5** `ConfirmationManager`: TC-07 删除操作仅发出高危警告但未提供 '35个文件，包括照片和文档' 的统计信息，说明 ConfirmationManager 缺少调用 ToolExecutor 预扫描（dry-run）获取统计摘要的规则。
- **L3** `ReActEngine`: TC-03 中预期工具调用（文件检索）未触发，ReActEngine 直接降级为追问，说明 ReActEngine→ToolCaller 的触发阈值/工具选择策略在 XML 中未定义，导致过早放弃工具路径。
- **L4** `MemoryStore`: L4 所有组件（VectorStore/EmbeddingService/TextChunker/MemoryStore/IndexManager/CacheManager）在 XML 定义但从未被引用，L3.MemoryAccessor 与 L4 的绑定关系缺失，导致上下文检索链路断裂。
- **L6** `SandboxManager`: L6 全部组件为孤儿节点，L5.ToolExecutor 未声明将代码执行委托至 L6.SandboxManager/CodeExecutor，导致运行时安全链路不可追踪。

## 3. 接口级偏差
- **L3** `ErrorTranslator`: TC-14 中网络异常未被转化为自然语言错误提示，反而返回无关内容（红烧肉做法），说明 ErrorTranslator 未拦截工具调用失败事件，错误传播路径未在 XML 中明确定义其对 ToolCaller 异常的订阅关系。
- **L3** `SecurityGuard`: TC-09 拒绝代发微信的措辞与预期固定模板不一致，SecurityGuard 的拒绝回复模板未在 Prompt 中硬编码。
- **L5** `ResultFormatter`: TC-10 文件为空时回复语义一致但措辞偏离预期固定句式，ResultFormatter 缺少空结果的标准化模板。

## 4. 数据流/规则级偏差
- **L5** `BashAnalyzer`: TC-01 写入文件时路径为 documents/desktop 且内容被篡改，说明 BashAnalyzer/ParameterValidator 未对用户原文参数做保真校验，存在 LLM 幻觉覆盖原始输入。

## 5. 测试覆盖率级偏差
- 未发现覆盖率异常。

## 6. 建议补丁清单
### auto_patch.patch（规则引擎生成）
```diff
# 无规则补丁

```

### llm_suggestions.patch（LLM 语义审查生成）
```diff
# LLM suggestion for ErrorTranslator (target=xml)
# TC-14 中网络异常未被转化为自然语言错误提示，反而返回无关内容（红烧肉做法），说明 ErrorTranslator 未拦截工具调用失败事件，错误传播路径未在 XML 中明确定义其对 ToolCaller 异常的订阅关系。
# Recommendation: 在 XML 中为 L3.ErrorTranslator 增加对 ToolCaller/LLMManager 异常事件的显式输入契约，并在 Prompt 中强制要求工具失败时必须走 ErrorTranslator 生成用户可读提示。

# LLM suggestion for ConfirmationManager (target=xml)
# TC-07 删除操作仅发出高危警告但未提供 '35个文件，包括照片和文档' 的统计信息，说明 ConfirmationManager 缺少调用 ToolExecutor 预扫描（dry-run）获取统计摘要的规则。
# Recommendation: 在 XML 中为 ConfirmationManager 增加 pre_confirm_summary 步骤，要求在高危操作前调用目录统计工具，并在 Prompt 中规定确认消息模板需包含数量与类型统计。

# LLM suggestion for BashAnalyzer (target=xml)
# TC-01 写入文件时路径为 documents/desktop 且内容被篡改，说明 BashAnalyzer/ParameterValidator 未对用户原文参数做保真校验，存在 LLM 幻觉覆盖原始输入。
# Recommendation: 在 XML 中显式定义 ParameterValidator 从 L1.DataValidator 获取 raw_user_payload 并与 LLM 产出的参数做一致性比对的数据流。

# LLM suggestion for ReActEngine (target=prompt)
# TC-03 中预期工具调用（文件检索）未触发，ReActEngine 直接降级为追问，说明 ReActEngine→ToolCaller 的触发阈值/工具选择策略在 XML 中未定义，导致过早放弃工具路径。
# Recommendation: 在 XML 中补充 ReActEngine 的工具选择决策规则（最小尝试次数、ToolRegistry 匹配阈值），Prompt 中禁止在未调用检索工具前放弃。
# [PROMPT_FIX]
# Apply to: tests/mock/layer_prompts.py

# LLM suggestion for SecurityGuard (target=prompt)
# TC-09 拒绝代发微信的措辞与预期固定模板不一致，SecurityGuard 的拒绝回复模板未在 Prompt 中硬编码。
# Recommendation: 在 Prompt 中为 SecurityGuard 定义受限操作的固定拒绝话术，并在 XML 中标注 SecurityGuard 输出为模板化字符串而非 LLM 自由生成。
# [PROMPT_FIX]
# Apply to: tests/mock/layer_prompts.py

# LLM suggestion for MemoryStore (target=xml)
# L4 所有组件（VectorStore/EmbeddingService/TextChunker/MemoryStore/IndexManager/CacheManager）在 XML 定义但从未被引用，L3.MemoryAccessor 与 L4 的绑定关系缺失，导致上下文检索链路断裂。
# Recommendation: 在 XML 中补齐 L3.MemoryAccessor → L4.VectorStore/MemoryStore 的调用契约，激活整层 L4 的数据流。

# LLM suggestion for SandboxManager (target=xml)
# L6 全部组件为孤儿节点，L5.ToolExecutor 未声明将代码执行委托至 L6.SandboxManager/CodeExecutor，导致运行时安全链路不可追踪。
# Recommendation: 在 XML 中为 ToolExecutor 增加 runtime_delegate 属性指向 L6.SandboxManager，并定义 SecurityEnforcer 的准入规则。

# LLM suggestion for ResultFormatter (target=prompt)
# TC-10 文件为空时回复语义一致但措辞偏离预期固定句式，ResultFormatter 缺少空结果的标准化模板。
# Recommendation: 在 Prompt 中为 ResultFormatter 增加空结果固定回复模板。
# [PROMPT_FIX]
# Apply to: tests/mock/layer_prompts.py

```
