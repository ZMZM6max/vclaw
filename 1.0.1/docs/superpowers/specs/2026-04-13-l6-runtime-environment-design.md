# L6 Runtime Environment 设计文档

> **设计日期**: 2026-04-13  
> **设计范围**: L6 环境执行层完整实现  
> **设计目标**: 基于 L6_RuntimeEnvironment.xml 规范，构建安全的代码执行沙盒系统

---

## 1. 设计概述

### 1.1 目标

构建 L6 Runtime Environment 层，提供：
- 安全的代码执行沙盒（Docker 容器隔离）
- 资源限制管理（CPU、内存、时间、磁盘）
- 代码安全检查和策略执行
- 支持 Python、JavaScript、Bash 语言

### 1.2 架构原则

- **单向依赖**: L6 是最底层，只被 L5 调用，不依赖其他层
- **无状态设计**: 每次执行都是独立的沙盒环境
- **安全第一**: 禁止网络、禁止宿主机文件系统访问、超时强制终止
- **组件化**: 职责分离，便于测试和扩展

### 1.3 参考文档

- `docs/L6_RuntimeEnvironment.xml` - L6 详细规范
- `docs/Architecture_Overview.xml` - 系统架构总览
- `src/core/interfaces.py` - RuntimeInterface 定义
- `src/core/exceptions.py` - 异常定义

---

## 2. 组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RuntimeEnvironment                        │
│                    (主入口/门面类)                            │
│                    实现 RuntimeInterface                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────────────────┐     │
│  │ DockerSandbox   │    │ SecurityEnforcer            │     │
│  │ 沙盒生命周期管理 │    │ 代码安全检查和策略执行       │     │
│  │                 │    │                             │     │
│  │ • create()      │    │ • check_code()              │     │
│  │ • execute()     │    │ • validate_language()       │     │
│  │ • destroy()     │    │ • check_resource_limits()   │     │
│  └────────┬────────┘    └─────────────────────────────┘     │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────────────┐                    │
│  │ DockerController                    │                    │
│  │ Docker API 底层封装                 │                    │
│  │                                     │                    │
│  │ • create_container()                │                    │
│  │ • exec_in_container()               │                    │
│  │ • remove_container()                │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 组件职责

| 组件 | 职责 | 文件 |
|------|------|------|
| `RuntimeEnvironment` | 主入口，实现 RuntimeInterface | `l6_runtime.py` |
| `DockerSandbox` | 沙盒生命周期管理（创建/执行/销毁） | `docker_sandbox.py` |
| `DockerController` | Docker API 底层调用封装 | `docker_controller.py` |
| `SecurityEnforcer` | 代码安全检查、资源限制验证 | `security_enforcer.py` |
| `SandboxConfig` | 沙盒配置数据类 | `config.py` |

---

## 3. 数据流设计

```
L5 调用 run_code(language, code, timeout, config)
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  RuntimeEnvironment.run_code()                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 安全预检查 (SecurityEnforcer)                            │
│     ├─ 代码长度限制 (100KB)                                  │
│     ├─ 禁止模式检查 (os.system, subprocess, eval, exec)      │
│     └─ 语言支持验证                                          │
│                                                              │
│  2. 创建沙盒 (DockerSandbox.create())                        │
│     ├─ 生成 environment_id (UUID)                           │
│     ├─ 创建临时目录 /tmp/sandbox/{id}/                       │
│     └─ DockerController 创建容器                             │
│        ├─ 镜像: python:3.11-alpine / node:18-alpine         │
│        ├─ 资源限制: CPU 1核, 内存 512MB                      │
│        ├─ 网络模式: none (禁用)                              │
│        └─ rootfs: 只读                                       │
│                                                              │
│  3. 准备执行                                                 │
│     ├─ 写入代码到 /tmp/sandbox/{id}/script.{ext}            │
│     └─ 构建执行命令                                          │
│                                                              │
│  4. 执行代码 (DockerSandbox.execute())                       │
│     ├─ DockerController.exec_in_container()                 │
│     ├─ 捕获 stdout/stderr                                   │
│     └─ 监控执行时间                                          │
│                                                              │
│  5. 强制清理 (finally 块)                                    │
│     ├─ DockerController.remove_container()                  │
│     └─ 删除临时目录                                          │
│                                                              │
│  6. 返回 ExecutionResult                                     │
│     ├─ exit_code, stdout, stderr                            │
│     ├─ execution_time                                       │
│     └─ resource_usage                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
返回 ExecutionResult 给 L5
```

---

## 4. 接口定义

### 4.1 RuntimeEnvironment

```python
class RuntimeEnvironment(RuntimeInterface):
    """L6 实现 - 运行时环境管理"""
    
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self.sandbox = DockerSandbox(self.config)
        self.security = SecurityEnforcer()
    
    def run_code(
        self, 
        language: str, 
        code: str, 
        timeout: int = 30,
        environment_config: Optional[Dict] = None
    ) -> ExecutionResult:
        """在沙盒中执行代码"""
        pass
```

### 4.2 DockerSandbox

```python
class DockerSandbox:
    """Docker 沙盒管理器"""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.controller = DockerController()
        self.base_dir = Path("/tmp/sandbox")
    
    def create(self, environment_id: str) -> str:
        """创建沙盒环境，返回 environment_id"""
        pass
    
    def execute(
        self, 
        environment_id: str, 
        language: str, 
        code: str,
        timeout: int
    ) -> ExecutionResult:
        """在沙盒中执行代码"""
        pass
    
    def destroy(self, environment_id: str) -> bool:
        """销毁沙盒环境"""
        pass
```

### 4.3 DockerController

```python
class DockerController:
    """Docker API 控制器"""
    
    def __init__(self):
        self.client = None  # docker.DockerClient
    
    def create_container(
        self,
        image: str,
        command: List[str],
        volumes: Dict[str, Dict],
        mem_limit: str,
        cpu_quota: int,
        network_mode: str
    ) -> str:
        """创建容器，返回 container_id"""
        pass
    
    def exec_in_container(
        self,
        container_id: str,
        command: List[str],
        timeout: int
    ) -> Tuple[int, str, str]:
        """在容器内执行命令，返回 (exit_code, stdout, stderr)"""
        pass
    
    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """移除容器"""
        pass
```

### 4.4 SecurityEnforcer

```python
class SecurityEnforcer:
    """安全策略执行器"""
    
    FORBIDDEN_PATTERNS = [
        "os.system", "subprocess", "__import__",
        "eval(", "exec(", "compile("
    ]
    
    SUPPORTED_LANGUAGES = {"python", "javascript", "bash"}
    
    def check_code(self, code: str) -> None:
        """检查代码安全性，违规则抛出 SecurityViolationError"""
        pass
    
    def validate_language(self, language: str) -> None:
        """验证语言支持，不支持则抛出 UnsupportedLanguageError"""
        pass
    
    def validate_config(self, config: Dict) -> SandboxConfig:
        """验证配置，返回标准化的 SandboxConfig"""
        pass
```

### 4.5 SandboxConfig

```python
@dataclass
class SandboxConfig:
    """沙盒配置"""
    memory_limit: int = 512        # MB
    cpu_limit: float = 1.0         # cores
    timeout: int = 30              # seconds
    enable_network: bool = False   # 默认禁用
    disk_limit: int = 100          # MB
    allowed_imports: Optional[List[str]] = None
```

---

## 5. 异常处理

使用 `src/core/exceptions.py` 中定义的异常：

| 异常 | 错误码 | 触发条件 |
|------|--------|----------|
| `UnsupportedLanguageError` | 400 | 语言不在支持列表 |
| `SecurityViolationError` | 403 | 代码包含禁止模式 |
| `ResourceExceededError` | 413 | 内存/CPU/磁盘超限 |
| `ExecutionTimeoutError` | 408 | 执行超时 |
| `SandboxCreationError` | 503 | Docker 创建失败 |

---

## 6. 文件结构

```
src/l6/
├── __init__.py                 # 包导出
├── l6_runtime.py              # RuntimeEnvironment 主类
├── docker_sandbox.py          # DockerSandbox 实现
├── docker_controller.py       # DockerController 实现
├── security_enforcer.py       # SecurityEnforcer 实现
├── config.py                  # SandboxConfig 配置
└── tests/
    ├── __init__.py
    ├── test_l6.py            # RuntimeEnvironment 集成测试
    ├── test_docker_sandbox.py # DockerSandbox 单元测试
    ├── test_docker_controller.py # DockerController 单元测试
    └── test_security.py      # SecurityEnforcer 单元测试
```

---

## 7. 测试策略

### 7.1 单元测试

- **test_security.py**: 安全规则检查（禁止模式、语言验证）
- **test_docker_controller.py**: Docker API 调用（Mock Docker client）
- **test_docker_sandbox.py**: 沙盒生命周期（创建/执行/销毁）

### 7.2 集成测试

- **test_l6.py**: 完整执行流程（需要 Docker 环境）

### 7.3 测试用例示例

```python
def test_python_execution_success():
    """成功执行 Python 代码"""
    runtime = RuntimeEnvironment()
    result = runtime.run_code("python", "print('Hello')")
    assert result.exit_code == 0
    assert "Hello" in result.stdout

def test_security_violation_blocked():
    """危险代码被阻止"""
    runtime = RuntimeEnvironment()
    with pytest.raises(SecurityViolationError):
        runtime.run_code("python", "import os; os.system('rm -rf /')")

def test_timeout_enforced():
    """超时强制终止"""
    runtime = RuntimeEnvironment()
    with pytest.raises(ExecutionTimeoutError):
        runtime.run_code("python", "while True: pass", timeout=1)
```

---

## 8. Docker 镜像策略

### 8.1 基础镜像

- **Python**: `python:3.11-alpine` (精简，约 55MB)
- **Node.js**: `node:18-alpine` (精简，约 40MB)
- **Bash**: `alpine:latest` (极简，约 5MB)

### 8.2 容器配置

```python
container_config = {
    "image": "python:3.11-alpine",
    "command": ["python", "/sandbox/script.py"],
    "volumes": {
        "/tmp/sandbox/{id}": {"bind": "/sandbox", "mode": "ro"}
    },
    "mem_limit": "512m",
    "cpu_quota": 100000,  # 1核
    "network_mode": "none",
    "read_only": True
}
```

---

## 9. 安全策略

### 9.1 代码层面安全

1. **禁止模式检查**: 正则表达式匹配危险函数调用
2. **代码长度限制**: 最大 100KB
3. **语言白名单**: 只允许 Python/JavaScript/Bash

### 9.2 容器层面安全

1. **无网络访问**: `network_mode="none"`
2. **只读文件系统**: `read_only=True`
3. **资源限制**: cgroup 限制 CPU/内存
4. **临时目录隔离**: 每次执行独立目录

### 9.3 执行层面安全

1. **超时强制终止**: subprocess timeout + Docker 容器销毁
2. **输出截断**: stdout/stderr 最大 10000 字符
3. **即时清理**: finally 块确保容器和目录被清理

---

## 10. 依赖清单

```
# requirements.txt (新增)
docker>=6.0.0          # Docker Python SDK
```

---

## 11. 后续扩展点

1. **ProcessSandbox**: Docker 不可用时回退到进程隔离
2. **RestrictedPython**: Python 代码使用 RestrictedPython 解释器
3. **网络白名单**: 允许访问特定域名（如 PyPI）
4. **持久化存储**: 允许沙盒目录在多次执行间保持

---

**设计完成日期**: 2026-04-13  
**设计版本**: v1.0  
**下一步**: 创建详细实施计划
