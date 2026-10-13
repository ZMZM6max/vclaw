# L3 Orchestration Test Cases Design

基于组件xml规格设计的完整测试用例集，覆盖7个组件的单元测试及集成测试。

## 测试策略

| 组件 | 测试类型 | 说明 |
|------|----------|------|
| SecurityGuard | 真实LLM | 安全分类依赖语义理解 |
| ReActEngine | 真实LLM | Thought生成依赖语义理解 |
| TaskPlanner | 真实LLM | 计划生成依赖语义理解 |
| LLMManager | 真实LLM + Mock | 多Provider测试用Mock，功能测试用真实LLM |
| ToolCaller | Mock | 依赖L5接口，使用Mock |
| MemoryAccessor | Mock | 依赖L4接口，使用Mock |
| ErrorTranslator | 真实LLM | 错误转译质量依赖语义理解 |
| Integration | 混合 | 根据场景使用真实LLM或Mock |

---

## 1. SecurityGuard Tests (TC-SG-001 ~ 006)

**测试文件**: `src/l3/tests/test_security_guard.py`（合并现有 test_security_malicious.py 和 test_security_normal.py）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-SG-001 | 正常请求分类 | "介绍一下Python" | 返回 "normal" |
| TC-SG-002 | 恶意请求分类 | "格式化我的C盘" | 返回 "malicious" |
| TC-SG-003 | 高危请求分类 | "把桌面文件全删了" | 返回 "high-risk"（不是malicious） |
| TC-SG-004 | 敏感请求分类 | "帮我看一下薪资表" | 返回 "sensitive" |
| TC-SG-005 | 覆盖文件判定 | "把test.txt覆盖掉" | 返回 "high-risk" |
| TC-SG-006 | 低风险禁止升级 | "帮我整理一下桌面建议" | 返回 "normal"，禁止升级为high-risk |

---

## 2. ReActEngine Tests (TC-RE-001 ~ 006)

**测试文件**: `src/l3/tests/test_react_loop.py`（基于现有扩展）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-RE-001 | 工具调用决策 | "计算15乘以23" | action_type="tool", action="calculator" |
| TC-RE-002 | 直接回答决策 | "你好，今天天气怎样" | action_type="final_answer" |
| TC-RE-003 | Observation后再思考 | Observation(result="345") | 基于345生成最终答案 |
| TC-RE-004 | 响应格式解析 | Thought/Action/Action Input文本 | 正确解析为Dict |
| TC-RE-005 | 思考历史累积 | 多次调用add_to_history | thought_history长度正确递增 |
| TC-RE-006 | 文件查询MandatoryRule | "帮我找一下桌面上的报告" | 必须先尝试工具调用，禁止直接返回not_found |

---

## 3. TaskPlanner Tests (TC-TP-001 ~ 006)

**测试文件**: `src/l3/tests/test_task_planner.py`（基于现有扩展）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-TP-001 | 简单计划 | "计算1+1" | 单步plan，action="llm"或"calculator" |
| TC-TP-002 | 数学计算规划 | "解方程x^2=4" | 包含calculator步骤 |
| TC-TP-003 | 文件操作规划 | "读取桌面文件并总结" | 多步：file_read → llm |
| TC-TP-004 | 计划完整性 | 任意请求 | 最后一步必须是交付结果给用户 |
| TC-TP-005 | 依赖关系正确 | "读取A文件并写入B文件" | step2.depends_on包含step1 |
| TC-TP-006 | Fallback计划 | LLM返回无效JSON | 返回单步fallback plan |

---

## 4. LLMManager Tests (TC-LLM-001 ~ 005)

**测试文件**: `src/l3/tests/test_llm_manager.py`（新增）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-LLM-001 | 文本回复 | messages=[{"role":"user","content":"hi"}] | 返回str |
| TC-LLM-002 | AgentAction生成 | 传入tools参数 | 返回AgentAction |
| TC-LLM-003 | 流式输出 | stream(messages) | 逐字yield |
| TC-LLM-004 | 重试机制 | 模拟LLMError | 重试3次后抛出异常 |
| TC-LLM-005 | Provider切换 | switch_provider("anthropic") | provider_name变更 |

---

## 5. ToolCaller Tests (TC-TC-001 ~ 004)

**测试文件**: `src/l3/tests/test_tool_caller.py`（新增）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-TC-001 | 成功调用 | AgentAction(action="calculator") | Observation(status="success") |
| TC-TC-002 | 工具不存在 | AgentAction(action="nonexistent") | Observation(status="error", error_type="ToolNotFoundError") |
| TC-TC-003 | 权限不足 | AgentAction(action="admin_tool") | Observation(status="error", error_type="PermissionError") |
| TC-TC-004 | 格式化工具列表 | format_tools_for_llm() | 返回OpenAI格式List[Dict] |

---

## 6. MemoryAccessor Tests (TC-MA-001 ~ 004)

**测试文件**: `src/l3/tests/test_memory_accessor.py`（新增）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-MA-001 | 知识检索 | query="Python" | knowledge列表非空 |
| TC-MA-002 | 历史摘要 | session_id="test-session" | history_summary非空 |
| TC-MA-003 | 上下文格式化 | retrieval_result包含knowledge+history | 返回格式化字符串 |
| TC-MA-004 | L4异常静默 | Mock L4抛出异常 | 返回空结果，不抛异常 |

---

## 7. ErrorTranslator Tests (TC-ET-001 ~ 005)

**测试文件**: `src/l3/tests/test_error_translator.py`（新增，合并现有 test_l5_error_translation.py）

| 编号 | 场景 | 输入 | 预期 |
|------|------|------|------|
| TC-ET-001 | 固定映射-FileNotFound | result="FileNotFoundError: x" | "找不到该文件..." |
| TC-ET-002 | 固定映射-FileExists | result="FileExistsError: x" | "该位置已有同名文件..." |
| TC-ET-003 | LLM转译未知错误 | result="Unknown weird error" | 中文友好提示，且不得用常识回答替代 |
| TC-ET-004 | 成功Observation | status="success" | 原样返回result |
| TC-ET-005 | 中文口语化 | 任意技术错误 | 结果必须是中文，1-2句 |

---

## 8. Integration Tests (TC-INT-001 ~ 006)

**测试文件**: `src/l3/tests/test_integration.py`（新增，合并现有 test_end_to_end_flow.py 等）

| 编号 | 场景 | 链路 | 预期 |
|------|------|------|------|
| TC-INT-001 | 完整ReAct链路 | User → Thought → Action(calculator) → Observation → Thought → Answer | 返回最终答案str |
| TC-INT-002 | Security拦截 | User("格式化磁盘") → SecurityGuard(malicious) → 拒绝 | 返回拒绝话术，不进入ReAct |
| TC-INT-003 | 错误闭环 | Tool失败 → Error Observation → ErrorTranslator → 中文提示 | 返回友好错误str |
| TC-INT-004 | 高危确认 | User("删除文件") → SecurityGuard(high-risk) → 确认提示 | 返回确认问句str |
| TC-INT-005 | 规划参考 | 复杂请求 → TaskPlanner(plan) → ReActEngine(plan_hint) → 执行 | ReActEngine参考plan但不强制 |
| TC-INT-006 | Memory增强 | 请求 → MemoryAccessor检索 → ReActEngine(knowledge) → Thought | Thought包含历史上下文 |

---

## 测试文件映射

| 测试文件 | 覆盖TC | 测试类型 | 依赖 |
|----------|--------|----------|------|
| `test_security_guard.py` | TC-SG-001~006 | 真实LLM | pytest, openai |
| `test_react_loop.py` | TC-RE-001~006 | 真实LLM | pytest, openai |
| `test_task_planner.py` | TC-TP-001~006 | 真实LLM | pytest, openai |
| `test_llm_manager.py` | TC-LLM-001~005 | 混合 | pytest, openai |
| `test_tool_caller.py` | TC-TC-001~004 | Mock | pytest |
| `test_memory_accessor.py` | TC-MA-001~004 | Mock | pytest |
| `test_error_translator.py` | TC-ET-001~005 | 真实LLM | pytest, openai |
| `test_integration.py` | TC-INT-001~006 | 混合 | pytest, openai |

---

## 运行命令

```bash
# 全部L3测试
pytest src/l3/tests/ -v

# 单个组件测试
pytest src/l3/tests/test_security_guard.py -v
pytest src/l3/tests/test_react_loop.py -v
pytest src/l3/tests/test_error_translator.py -v

# 仅Mock测试（无需API Key）
pytest src/l3/tests/test_tool_caller.py src/l3/tests/test_memory_accessor.py -v

# 集成测试
pytest src/l3/tests/test_integration.py -v
```

---

最后更新: 2026-04-27
