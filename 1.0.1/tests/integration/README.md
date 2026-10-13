# Integration Tests

本目录包含 VClaw 跨层集成测试，验证多个真实层之间的交互。

## 测试文件列表

| 测试文件 | 用途 | 依赖 | 状态 |
|----------|------|------|------|
| `test_l2_l3_loop.py` | Mock版本的L2-L3 ReAct循环测试（使用Mock L3/L5） | 无 | 稳定 |
| `test_real_loop.py` | 真实ReAct循环集成测试（L2-L3-L4-L5-L6全真实实例） | OPENAI_API_KEY、Docker（可选） | 真实LLM测试 |
| `test_e2e_real.py` | L1→L6 真实端到端测试（从原始Telegram payload到最终回答） | OPENAI_API_KEY、Docker（可选） | 真实LLM测试 |

## 依赖清单

| 测试文件 | 依赖包 | 安装命令 |
|----------|--------|----------|
| `test_l2_l3_loop.py` | pytest | `pip install pytest` |
| `test_real_loop.py` | pytest, openai, docker（可选） | `pip install pytest openai docker` |
| `test_e2e_real.py` | pytest, openai, docker（可选） | `pip install pytest openai docker` |

## 运行方法

### 运行所有集成测试

```bash
pytest tests/integration/ -v
```

### 运行Mock版本（无需外部依赖）

```bash
pytest tests/integration/test_l2_l3_loop.py -v
```

### 运行真实ReAct循环测试

需要设置 `OPENAI_API_KEY` 环境变量：

```bash
# Linux/macOS
export OPENAI_API_KEY="sk-..."
pytest tests/integration/test_real_loop.py -v

# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."
pytest tests/integration/test_real_loop.py -v
```

如果 L3 选择了 `python_repl` 工具且本地没有 Docker，对应测试将自动 skip。

### 运行端到端真实测试

```bash
# Linux/macOS
export OPENAI_API_KEY="sk-..."
pytest tests/integration/test_e2e_real.py -v

# Windows PowerShell
$env:OPENAI_API_KEY="sk-..."
pytest tests/integration/test_e2e_real.py -v
```

## 注意事项

1. **API Key**: `test_real_loop.py` 和 `test_e2e_real.py` 需要真实的 `OPENAI_API_KEY`。未设置时会自动 skip。
2. **Docker（可选）**: 若 L3 选择 `python_repl` 执行数学计算，需要本地 Docker 环境。若不可用，相关用例会 skip。
3. **费用**: 真实 LLM 测试会产生 API 调用费用，请谨慎运行。
4. **L4数据清理**: `test_real_loop.py` 和 `test_e2e_real.py` 使用模块级 fixture，测试结束后会自动清理 L4 中的测试数据。
5. **网络**: 真实测试需要能够访问 OpenAI API（或配置的第三方 API 平台）。
