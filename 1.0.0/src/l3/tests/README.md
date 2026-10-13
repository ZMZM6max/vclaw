# L3 Orchestration Tests

L3 逻辑编排层测试文档 - 每个功能独立一个文件，全部使用真实LLM

## 测试文件列表

| 测试文件 | 用途 | 测试编号 | 依赖 |
|----------|------|----------|------|
| `test_l3.py` | L3 核心功能集成测试 | TC-L3-001~012 | pytest, openai |
| `test_simple_chat.py` | 简单对话回复测试 | TC-L3-001 | pytest, openai |
| `test_security_malicious.py` | 安全判断 - 拒绝恶意请求 | TC-L3-011 | pytest, openai |
| `test_security_normal.py` | 安全判断 - 允许正常请求 | TC-L3-012 | pytest, openai |
| `test_l5_error_translation.py` | L5错误转译测试 | TC-L3-007 | pytest, openai |
| `test_file_path_handling.py` | 文件路径处理测试 | - | pytest, openai |
| `test_task_planner.py` | 任务规划器测试 | TC-L3-005 | pytest, openai |
| `test_react_loop.py` | **ReAct循环测试** | - | pytest, openai |
| `test_tool_invocation.py` | **工具调用流程测试** | TC-L3-013~018 | pytest, openai |
| `test_observation_flow.py` | **Observation返回流程测试** | TC-L3-019~023 | pytest, openai |

## 依赖清单

```bash
pip install pytest openai python-dotenv
```

## 配置 .env 文件

在项目根目录创建 `.env` 文件：

```bash
# 第三方API平台（青云端）
API_BASE_URL=https://api.qingyuntop.top/v1
OPENAI_API_KEY=sk-...
TEST_LLM_PROVIDER=openai
TEST_LLM_MODEL=gpt-5.4-mini  # 或其他可用模型
```

## 运行方法

### 运行单个测试文件

```bash
# 简单对话测试
pytest src/l3/tests/test_simple_chat.py -v

# 安全判断 - 恶意请求
pytest src/l3/tests/test_security_malicious.py -v

# 安全判断 - 正常请求
pytest src/l3/tests/test_security_normal.py -v

# L5错误转译
pytest src/l3/tests/test_l5_error_translation.py -v

# 路径处理
pytest src/l3/tests/test_file_path_handling.py -v

# 任务规划
pytest src/l3/tests/test_task_planner.py -v

# ReAct循环测试
pytest src/l3/tests/test_react_loop.py -v

# 工具调用流程测试
pytest src/l3/tests/test_tool_invocation.py -v

# Observation返回流程测试
pytest src/l3/tests/test_observation_flow.py -v
```

### 运行特定测试用例

```bash
# 运行单个测试方法
pytest src/l3/tests/test_simple_chat.py::TestSimpleChatResponse::test_simple_chat_response -v

# 运行安全判断测试中的特定用例
pytest src/l3/tests/test_security_malicious.py::TestSecurityMalicious::test_refuse_format_disk -v
```

### 运行所有 L3 测试

```bash
# 运行 src/l3/tests/ 目录下所有测试
pytest src/l3/tests/ -v

# 或运行特定标记的测试
pytest src/l3/tests/ -v -m "security"      # 安全相关测试
pytest src/l3/tests/ -v -m "error_handling" # 错误处理测试
pytest src/l3/tests/ -v -m "path_handling"  # 路径处理测试
pytest src/l3/tests/ -v -m "planning"       # 任务规划测试
```

## 测试用例详情

### test_simple_chat.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_simple_chat_response` | TC-L3-001 | 简单英文对话回复 |
| `test_simple_chat_in_chinese` | - | 中文简单对话回复 |

### test_security_malicious.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_refuse_format_disk` | TC-L3-011 | 拒绝格式化硬盘请求 |
| `test_refuse_delete_system_files` | - | 拒绝删除系统文件 |
| `test_refuse_create_virus` | - | 拒绝创建病毒 |

### test_security_normal.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_allow_python_introduction` | TC-L3-012 | 允许Python介绍 |
| `test_allow_calculator` | - | 允许数学计算 |
| `test_allow_file_creation` | - | 允许文件创建（非恶意） |

### test_l5_error_translation.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_file_not_found_error` | TC-L3-007 | 文件不存在错误转译 |
| `test_permission_error` | - | 权限错误转译 |
| `test_timeout_error` | - | 超时错误转译 |

### test_file_path_handling.py

| 测试方法 | 描述 |
|----------|------|
| `test_desktop_file_creation` | 桌面文件创建路径处理 |
| `test_download_folder_access` | 下载文件夹路径处理 |
| `test_path_conversion_chinese` | 中文路径转换 |

### test_task_planner.py

| 测试方法 | 描述 |
|----------|------|
| `test_create_simple_plan` | 创建简单任务计划 |
| `test_create_math_plan` | 数学计算任务规划 |
| `test_create_file_operation_plan` | 文件操作任务规划 |

### test_react_loop.py

| 测试方法 | 描述 |
|----------|------|
| `test_react_generate_thought` | 验证ReAct Thought生成 |
| `test_react_with_observation` | 验证Observation后的闭环再思考 |
| `test_orchestration_run_first_iteration` | 验证Orchestration.run()第一轮执行 |
| `test_react_iteration_count` | 验证迭代计数机制 |
| `test_react_history_accumulation` | 验证思考历史累积 |

### test_tool_invocation.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_l5_provides_tools` | TC-L3-013 | L5提供可用工具列表 |
| `test_tools_passed_to_react_engine` | TC-L3-014 | 工具列表传递给ReActEngine |
| `test_llm_selects_calculator_tool` | TC-L3-015 | LLM选择计算器工具 |
| `test_llm_selects_python_repl` | TC-L3-016 | LLM选择Python REPL工具 |
| `test_tool_execution_observation_loop` | TC-L3-017 | 工具执行后的Observation闭环 |
| `test_tools_in_prompt_description` | TC-L3-018 | 工具描述在Prompt中正确显示 |

### test_observation_flow.py

| 测试方法 | 测试编号 | 描述 |
|----------|----------|------|
| `test_l5_returns_observation` | TC-L3-019 | L5执行工具后返回Observation对象 |
| `test_l3_receives_observation` | TC-L3-020 | L3正确接收并处理Observation |
| `test_error_observation_handling` | TC-L3-021 | L3正确处理错误Observation |
| `test_observation_in_react_history` | TC-L3-022 | Observation被记录在ReAct历史中 |
| `test_complete_react_loop_with_observation` | TC-L3-023 | 完整ReAct闭环：Action→Observation→Thought→Answer |

## ReAct循环说明

L3层实现了真正的 **ReAct (Reasoning + Acting)** 循环：

```
Thought → Action → Observation → Thought → ... → Final Answer
```

### ReActEngine组件

```python
class ReActEngine:
    - generate_thought(): 基于当前状态生成思考
    - add_to_history(): 记录思考历史
    - reset(): 重置ReAct状态
```

### 循环流程

1. **第一轮** - 用户输入：
   - 生成初始 Thought
   - 决定 Action（工具调用或直接回答）
   - 如果需要工具 → 返回 `AgentAction` 给L5执行

2. **第二轮及以后** - Observation返回：
   - 记录 Observation 到思考历史
   - 基于 Observation 再生成新的 Thought
   - 决定下一步 Action
   - 循环直到得到最终答案

### 终止条件

- 得到最终答案（action_type = "final_answer"）
- 达到最大迭代次数（MAX_ITERATIONS = 5）

## 测试标记

| 标记 | 说明 |
|------|------|
| `@pytest.mark.slow` | 慢速测试（调用真实API） |
| `@pytest.mark.integration` | 集成测试 |
| `@pytest.mark.security` | 安全相关测试 |
| `@pytest.mark.error_handling` | 错误处理测试 |
| `@pytest.mark.path_handling` | 路径处理测试 |
| `@pytest.mark.planning` | 任务规划测试 |

## 注意事项

1. **全部使用真实LLM**: 所有测试均调用真实LLM API，不再使用Mock
2. **真实LLM依赖**: 所有测试需要配置 `OPENAI_API_KEY`
3. **第三方API平台**: 默认使用青云端 `https://api.qingyuntop.top/v1`
4. **无API Key时**: 测试会自动跳过，显示 `s`
5. **API成本**: 使用第三方平台可降低成本
6. **网络要求**: 需要互联网连接访问LLM API

---
## 移除Mock说明

**已移除的Mock组件**:
- ✅ 删除了 `MockProvider` 类
- ✅ 修改 `LLMManager` 默认 provider 从 `MOCK` 改为 `OPENAI`
- ✅ 删除了 `test_l3_debug.py` (使用 unittest.mock)
- ✅ 更新 `TaskPlanner` 默认使用真实LLM

**影响**:
- 测试现在需要有效的 API Key 才能运行
- 不再支持无API Key下的Mock测试模式

---
最后更新: 2026-04-13
