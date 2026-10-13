# L6 Runtime Environment Tests

This directory contains unit tests for the L6 Runtime & Environment layer components.

## 测试文件列表

| 测试文件 | 用途 | 依赖 | 状态 |
|----------|------|------|------|
| `test_security.py` | SecurityEnforcer 安全校验测试 | `pytest` | ✅ 已通过 |
| `test_config.py` | SandboxConfig 配置测试 | `pytest` | ✅ 已通过 |
| `test_code_executor.py` | CodeExecutor 语言调度门面测试 | `pytest`, `unittest.mock` | ✅ 已通过 |
| `test_docker_controller.py` | DockerController API 封装测试 | `pytest`, `unittest.mock` | ✅ 已通过 |
| `test_docker_sandbox.py` | DockerSandbox 生命周期测试 | `pytest`, `unittest.mock` | ✅ 已通过 |
| `test_execution_logger.py` | ExecutionLogger 日志测试 | `pytest` | ✅ 已通过 |
| `test_l6.py` | RuntimeEnvironment 集成测试 | `pytest`, `unittest.mock` | ✅ 已通过 |
| `test_sandbox_manager.py` | SandboxManager 核心协调组件测试 | `pytest`, `unittest.mock` | ✅ 已通过 |

## 依赖清单

| 测试文件 | 依赖包 | 安装命令 |
|----------|--------|----------|
| `test_security.py` | `pytest` | `pip install pytest` |
| `test_config.py` | `pytest` | `pip install pytest` |
| `test_code_executor.py` | `pytest` | `pip install pytest` |
| `test_docker_controller.py` | `pytest` | `pip install pytest` |
| `test_docker_sandbox.py` | `pytest` | `pip install pytest` |
| `test_execution_logger.py` | `pytest` | `pip install pytest` |
| `test_l6.py` | `pytest` | `pip install pytest` |
| `test_sandbox_manager.py` | `pytest` | `pip install pytest` |

## 运行方法

运行所有 L6 测试：

```bash
pytest src/l6/tests/ -v
```

运行单个测试文件：

```bash
pytest src/l6/tests/test_security.py -v
pytest src/l6/tests/test_config.py -v
```

运行单个测试类：

```bash
pytest src/l6/tests/test_security.py::TestSecurityEnforcerLanguage -v
pytest src/l6/tests/test_security.py::TestSecurityEnforcerCode -v
pytest src/l6/tests/test_security.py::TestSecurityEnforcerResources -v
```

运行单个测试用例：

```bash
pytest src/l6/tests/test_security.py::TestSecurityEnforcerLanguage::test_valid_python -v
```

## 注意事项

- `test_docker_controller.py` 和 `test_docker_sandbox.py` 使用 `unittest.mock` 模拟 Docker API，不需要真实 Docker 环境。
- `test_l6.py` 使用 `unittest.mock` 模拟 DockerSandbox，不需要真实 Docker 环境。
- SecurityEnforcer 是纯静态分析组件，零外部依赖。
- ResourceLimiter 被 SecurityEnforcer 引用以读取硬上限（HARD_LIMITS）。
