"""L5-L6 真实依赖契约测试

验证 L5 的 python_repl 工具能够通过真实的 L6 Docker 沙盒执行 Python 代码，
并返回正确的执行结果。

依赖:
    - Docker Desktop 必须正在运行
    - python:3.11-alpine 镜像必须可用

标记:
    @pytest.mark.contract - 契约测试标记
"""

import pytest


# =============================================================================
# 模块级 Fixture
# =============================================================================

@pytest.fixture(scope="module")
def l5_with_l6():
    """模块级 Fixture：创建注入真实 L6 的 L5 ToolsCapabilities 实例.

    检查 Docker 守护进程和 python:3.11-alpine 镜像的可用性，
    如果不满足条件则跳过整个模块的测试。

    Yields:
        ToolsCapabilities: 配置好真实 L6 Runtime 的 L5 工具实例
    """
    # Step 1: 检查 Docker 守护进程是否可连接
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception as e:
        pytest.skip(f"Docker 守护进程不可用: {e}")

    # Step 2: 检查 python:3.11-alpine 镜像是否存在
    try:
        client.images.get("python:3.11-alpine")
    except docker.errors.ImageNotFound:
        pytest.skip("Docker 镜像 python:3.11-alpine 未找到，请先执行: docker pull python:3.11-alpine")
    except Exception as e:
        pytest.skip(f"检查 Docker 镜像时出错: {e}")

    # Step 3: 初始化真实的 L5 + L6
    from src.l6.runtime_environment import RuntimeEnvironment
    from src.l5.l5_tools import ToolsCapabilities

    l6 = RuntimeEnvironment()
    l5 = ToolsCapabilities(runtime=l6)

    yield l5

    # 模块结束后无需显式清理，L6 的 sandbox manager 会自动销毁容器


# =============================================================================
# 契约测试
# =============================================================================

pytestmark = pytest.mark.contract


class TestL5L6Contract:
    """L5-L6 真实依赖契约测试类.

    验证 L5 的 python_repl 工具在真实 L6 Docker 沙盒中的执行能力，
    包括正常代码执行、复杂计算和语法错误处理。
    """

    def test_l5_python_repl_runs_in_docker(self, l5_with_l6):
        """测试 python_repl 工具在 Docker 沙盒中成功执行简单代码.

        测试步骤:
            1. 调用 L5 的 python_repl 工具执行 print(2+2)
            2. 验证返回 Observation 的状态、结果和执行时间

        验证点:
            - status == "success"
            - result 中包含 "4"
            - execution_time > 0（证明确实执行了代码）
        """
        obs = l5_with_l6.execute(
            "python_repl",
            {"code": "print(2+2)"},
            user_permissions=[],
        )

        assert obs.status == "success", (
            f"python_repl 执行失败: {obs.result}"
        )
        assert "4" in obs.result, (
            f"执行结果中未找到预期输出 '4': {obs.result}"
        )
        assert obs.execution_time > 0, (
            f"执行时间应大于 0，实际为: {obs.execution_time}"
        )

    def test_l5_python_repl_calculates_fibonacci(self, l5_with_l6):
        """测试 python_repl 工具能执行复杂计算（斐波那契数列）.

        测试步骤:
            1. 调用 python_repl 执行 fibonacci(10) 的 Python 代码
            2. 验证返回结果中包含 "55"

        验证点:
            - status == "success"
            - result 中包含 "55"
        """
        fibonacci_code = """
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

print(fibonacci(10))
"""
        obs = l5_with_l6.execute(
            "python_repl",
            {"code": fibonacci_code},
            user_permissions=[],
        )

        assert obs.status == "success", (
            f"斐波那契计算执行失败: {obs.result}"
        )
        assert "55" in obs.result, (
            f"斐波那契计算结果中未找到 '55': {obs.result}"
        )

    def test_l5_python_repl_syntax_error_returns_error(self, l5_with_l6):
        """测试 python_repl 工具对语法错误返回 error 状态.

        测试步骤:
            1. 调用 python_repl 执行包含语法错误的代码 print(2+)
            2. 验证返回 Observation 的 status 为 "error"

        验证点:
            - status == "error"
            - 结果中包含错误信息（如 SyntaxError 或 invalid syntax）
        """
        obs = l5_with_l6.execute(
            "python_repl",
            {"code": "print(2+"},
            user_permissions=[],
        )

        assert obs.status == "error", (
            f"语法错误代码应返回 error 状态，实际为: {obs.status}"
        )
