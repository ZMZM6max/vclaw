"""VClaw 前置环境检查.

运行测试前检查所有依赖是否就绪.
"""
import os
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def check_env(keys: list) -> list:
    """检查环境变量."""
    missing = []
    for key in keys:
        if not os.getenv(key):
            missing.append(key)
    return missing


def check_docker() -> tuple:
    """检查 Docker daemon."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Docker daemon 运行中"
        return False, f"Docker daemon 未响应: {result.stderr.strip()[:100]}"
    except FileNotFoundError:
        return False, "docker 命令未找到"
    except Exception as e:
        return False, str(e)


def check_docker_image(image: str) -> tuple:
    """检查 Docker 镜像."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip():
            return True, f"镜像 {image} 已存在"
        return False, f"镜像 {image} 未拉取，运行: docker pull {image}"
    except Exception as e:
        return False, str(e)


def check_api_reachable(url: str) -> tuple:
    """简单检查 API 地址是否可达."""
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "vclaw-preflight/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, f"API 可达 (HTTP {resp.status})"
    except Exception as e:
        return False, str(e)


def check_writable_dir(path: Path) -> tuple:
    """检查目录是否可写."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".preflight_test"
        test_file.write_text("test")
        test_file.unlink()
        return True, f"目录 {path} 可写"
    except Exception as e:
        return False, str(e)


def main():
    print("=== VClaw Preflight Check ===\n")
    all_ok = True

    # 1. 环境变量
    print("[1/5] 检查环境变量...")
    env_keys = ["OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN"]
    missing = check_env(env_keys)
    if missing:
        print(f"  [FAIL] 缺失: {', '.join(missing)}")
        all_ok = False
    else:
        print(f"  [PASS] 全部配置")

    # 2. Docker
    print("\n[2/5] 检查 Docker...")
    ok, msg = check_docker()
    print(f"  {'[PASS]' if ok else '[FAIL]'} {msg}")
    if not ok:
        all_ok = False

    # 3. Docker 镜像
    print("\n[3/5] 检查 Docker 镜像...")
    ok, msg = check_docker_image("python:3.11-alpine")
    print(f"  {'[PASS]' if ok else '[FAIL]'} {msg}")
    if not ok:
        all_ok = False

    # 4. API 可达性
    print("\n[4/5] 检查 API 可达性...")
    api_url = os.getenv("OPENAI_BASE_URL", "https://api.qingyuntop.top/v1")
    # 去掉 /v1 后缀做简单 ping
    base_url = api_url.rsplit("/", 1)[0]
    ok, msg = check_api_reachable(base_url)
    print(f"  {'[PASS]' if ok else '[WARN]'} {msg}")
    # API 不可达不阻断（可能是网络暂时问题）

    # 5. 目录权限
    print("\n[5/5] 检查目录权限...")
    dirs = [
        Path("src/l4/data/chroma_db"),
        Path("src/l4/data/conversations"),
        Path("tests/results"),
    ]
    for d in dirs:
        ok, msg = check_writable_dir(d)
        print(f"  {'[PASS]' if ok else '[FAIL]'} {msg}")
        if not ok:
            all_ok = False

    print("\n" + "=" * 40)
    if all_ok:
        print("[PASS] 全部检查通过，可以开始测试!")
        return 0
    else:
        print("[FAIL] 部分检查未通过，请修复后重试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
