# VClaw Mock E2E 测试框架

使用六个大模型分别模拟 VClaw 系统的 L1-L6 层，进行端到端测试。

## 核心文件

| 文件 | 说明 |
|------|------|
| `e2e_framework.py` | 核心框架，包含 `EndToEndRunner` 和 `LLMClient` |
| `layer_prompts.py` | L1-L6 六层 LLM 提示词定义 |
| `layer_protocol.py` | 层间数据传输协议（Pydantic 模型） |
| `test_cases.py` | 32 个端到端测试用例 |
| `run_e2e_tests.py` | 测试运行器（支持按套件/分类/指定用例运行） |
| `config.py` | API 密钥配置（OpenAI/Anthropic/Moonshot） |
| `requirements.txt` | 依赖列表 |
| `__init__.py` | 模块导出 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥（编辑 config.py）
OPENAI_API_KEY = "sk-your-key"

# 运行 P0 必过测试套件
python run_e2e_tests.py --suite p0

# 运行指定用例
python run_e2e_tests.py --cases TC-01 TC-04

# 列出所有用例
python run_e2e_tests.py --list
```

## 架构

```
L1 (用户接入层)    → 标准化输入
L2 (控制网关层)    → 限流、会话、工具权限筛选
L3 (逻辑编排层)    → 安全判断、ReAct 循环、工具决策
L4 (记忆与知识层)  → 历史检索、相关记忆
L5 (能力抽象层)    → 工具执行、参数验证
L6 (环境执行层)    → 沙盒代码执行
```

### Mock 理想环境规则

为了提升自动化测试的覆盖率和稳定性，L3 层的系统提示词包含以下特殊规则：
- 假设所有工具在理想环境下均可用；
- LLM 不得以"缺少工具"为由拒绝正常请求；
- 正常请求应选择合适工具或直接返回模拟成功结果；
- 只有在敏感内容、恶意操作或明显高危操作场景才允许拒绝。

### 语义结果校验

测试结果不仅检查技术流程是否跑通（`completed`），还会调用一个轻量级 LLM（默认 `gpt-5.4-mini`）对 `final_response` 和 `expected_result` 进行语义对比。只有两者同时满足才算通过。

## 使用示例

```python
from e2e_framework import EndToEndRunner, TestCaseGenerator

llm_configs = {
    "L1": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-xxx"},
    "L2": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-xxx"},
    "L3": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-xxx"},
    "L4": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-xxx"},
    "L5": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-xxx"},
    "L6": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-xxx"},
}

runner = EndToEndRunner(llm_configs)
test_case = TestCaseGenerator.telegram_message("计算 Fibonacci(10)")
result = runner.run(test_case)
print(result.final_response)
```
