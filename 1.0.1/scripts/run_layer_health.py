"""VClaw Layer Health 诊断器.

按阶段顺序跑测试，上游失败自动 skip 下游，产出 Markdown + JSON 双格式报告.

Usage:
    python scripts/run_layer_health.py                # 全跑
    python scripts/run_layer_health.py --skip e2e     # 跳过 E2E（节约 token）
    python scripts/run_layer_health.py --from stage2  # 从阶段 2 开始
    python scripts/run_layer_health.py --json-only    # 只输出 JSON
    python scripts/run_layer_health.py --layer l5     # 只跑 L5 相关
"""
import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Force UTF-8 encoding for stdout/stderr on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ========== 阶段定义 ==========

STAGES = [
    {
        "name": "stage1",
        "label": "单层单测",
        "command": ["pytest", "src/", "-m", "not contract and not integration_real and not e2e_real and not telegram_manual", "-v", "--tb=line", "--ignore=src/l5/tests/test_bash_analyzer.py", "--ignore=src/l5/tests/test_path_mapper.py", "--ignore=src/l5/tests/test_permissions.py", "--ignore=src/l5/tests/test_task_manager.py"],
        "layers": ["l1", "l2", "l3", "l4", "l5", "l6"],
    },
    {
        "name": "stage2",
        "label": "相邻层契约",
        "command": ["pytest", "src/", "tests/", "-m", "contract", "-v", "--tb=line", "--ignore=src/l5/tests/test_bash_analyzer.py", "--ignore=src/l5/tests/test_path_mapper.py", "--ignore=src/l5/tests/test_permissions.py", "--ignore=src/l5/tests/test_task_manager.py", "--ignore=tests/mock/"],
        "pairs": ["L1→L2", "L2→L3", "L3→L4", "L5→L6"],
    },
    {
        "name": "stage3",
        "label": "真实闭环",
        "command": ["pytest", "tests/integration/test_real_loop.py", "-v", "--tb=line"],
        "depends_on": "stage2",
    },
    {
        "name": "stage4",
        "label": "L1→L6 端到端",
        "command": ["pytest", "tests/integration/test_e2e_real.py", "-v", "--tb=line"],
        "depends_on": "stage3",
    },
    {
        "name": "stage5",
        "label": "Telegram 验收",
        "command": None,  # 手动执行
        "depends_on": "stage4",
    },
]


def run_pytest(cmd: List[str]) -> Tuple[int, str, str]:
    """运行 pytest 命令，返回 (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


def parse_pytest_output(stdout: str) -> Dict:
    """解析 pytest stdout，提取通过/失败/skip 数量."""
    summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}

    # 查找最后一行 summary
    for line in reversed(stdout.splitlines()):
        if "passed" in line or "failed" in line or "skipped" in line or "error" in line:
            # 示例: "3 passed, 1 failed, 2 skipped in 12.34s"
            import re
            for key, pattern in [
                ("passed", r"(\d+) passed"),
                ("failed", r"(\d+) failed"),
                ("skipped", r"(\d+) skipped"),
                ("errors", r"(\d+) error"),
            ]:
                match = re.search(pattern, line)
                if match:
                    summary[key] = int(match.group(1))
            summary["total"] = summary["passed"] + summary["failed"] + summary["skipped"] + summary["errors"]
            break

    return summary


def diagnose_failure(stderr: str, stdout: str) -> str:
    """根据输出诊断失败原因，返回用户友好的提示."""
    combined = stderr + stdout

    if "docker.errors.DockerException" in combined or ("ConnectionRefusedError" in combined and "docker" in combined.lower()):
        return "Docker daemon 未启动，请启动 Docker Desktop"
    if "ImageNotFound" in combined or "No such image" in combined:
        return "Docker 镜像未拉取，运行: docker pull python:3.11-alpine"
    if "401" in combined and "OPENAI" in combined.upper():
        return "OPENAI_API_KEY 无效或缺失，请检查 .env 文件"
    if "ConnectionError" in combined and "qingyuntop" in combined:
        return "青云端 API 不可达，请检查网络或 OPENAI_BASE_URL"
    if "PermissionError" in combined and "chroma" in combined.lower():
        return "ChromaDB 目录权限不足，请检查 src/l4/data/ 目录"
    if "MaxIterationsExceeded" in combined:
        return "ReAct 死循环，请检查 L3 提示词或提高 max_iterations"
    if "RateLimitError" in combined or "429" in combined:
        return "API 限流（429），请稍后再试或降低并发"

    return "未知错误，请查看详细输出"


def generate_report(results: List[Dict], json_only: bool) -> str:
    """生成报告."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if json_only:
        return json.dumps({
            "timestamp": timestamp,
            "results": results,
        }, ensure_ascii=False, indent=2)

    lines = [
        "=== VClaw Layer Health Report ===",
        f"生成时间: {timestamp}",
        "",
    ]

    for r in results:
        stage_label = r["stage_label"]
        status = r["status"]
        summary = r.get("summary", {})

        if status == "skipped_upstream":
            lines.append(f"[{stage_label}]  SKIP 跳过 (上游失败)")
        elif status == "manual":
            lines.append(f"[{stage_label}]  MANUAL 请手动执行")
        elif status == "passed":
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            lines.append(f"[{stage_label}]  PASS {passed}/{total} 通过")
        elif status == "failed":
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            lines.append(f"[{stage_label}]  FAIL {passed}/{total} 通过 ({failed} 失败, {skipped} skip)")

    # 失败摘要
    failures = [r for r in results if r["status"] == "failed"]
    if failures:
        lines.extend(["", "=== 失败摘要 ==="])
        for r in failures:
            diagnosis = r.get("diagnosis", "未知错误")
            lines.append(f"FAIL {r['stage_label']}: {diagnosis}")

    # 修复建议
    if failures:
        lines.extend(["", "=== 修复后只需重跑: ==="])
        first_failed = failures[0]["stage_name"]
        lines.append(f"python scripts/run_layer_health.py --from {first_failed}")

    lines.append("")
    return "\n".join(lines)


def save_json_report(results: List[Dict]) -> Path:
    """保存 JSON 报告到 tests/results/."""
    results_dir = PROJECT_ROOT / "tests" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    path = results_dir / f"layer_health_{timestamp}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    return path


def main():
    parser = argparse.ArgumentParser(description="VClaw Layer Health 诊断器")
    parser.add_argument("--skip", choices=["e2e"], help="跳过 E2E 阶段（节约 token）")
    parser.add_argument("--from", dest="from_stage", help="从指定阶段开始（stage1~stage4）")
    parser.add_argument("--json-only", action="store_true", help="只输出 JSON")
    parser.add_argument("--layer", help="只跑指定层相关（l1~l6）")
    args = parser.parse_args()

    # 阶段过滤
    stages_to_run = STAGES[:]
    if args.from_stage:
        start_idx = next((i for i, s in enumerate(stages_to_run) if s["name"] == args.from_stage), 0)
        stages_to_run = stages_to_run[start_idx:]
    if args.skip == "e2e":
        stages_to_run = [s for s in stages_to_run if s["name"] != "stage4"]
    if args.layer:
        # 只保留 stage1（单层）和该层相关的契约
        stages_to_run = [s for s in stages_to_run if s["name"] in ("stage1", "stage2")]

    results = []

    for stage in stages_to_run:
        result = {
            "stage_name": stage["name"],
            "stage_label": stage["label"],
            "status": "pending",
        }

        # 检查上游依赖（仅当当前阶段声明了 depends_on 时才检查）
        depends_on = stage.get("depends_on")
        if depends_on and any(
            r["stage_name"] == depends_on and r["status"] in ("failed", "skipped_upstream")
            for r in results
        ):
            result["status"] = "skipped_upstream"
            results.append(result)
            continue

        # stage5 是手动执行
        if stage["name"] == "stage5":
            result["status"] = "manual"
            result["diagnosis"] = "请手动执行 docs/02_guides/telegram-acceptance-checklist.md 中的 8 条用例"
            results.append(result)
            continue

        # 运行 pytest
        print(f"\n>>> 正在跑: {stage['label']}...", file=sys.stderr)
        returncode, stdout, stderr = run_pytest(stage["command"])

        summary = parse_pytest_output(stdout)
        result["summary"] = summary

        if returncode == 0 or (summary["failed"] == 0 and summary["errors"] == 0):
            result["status"] = "passed"
        else:
            result["status"] = "failed"
            result["diagnosis"] = diagnose_failure(stderr, stdout)

        # 保存详细输出（调试用）
        result["stdout_tail"] = stdout[-2000:] if len(stdout) > 2000 else stdout
        result["stderr_tail"] = stderr[-1000:] if len(stderr) > 1000 else stderr

        results.append(result)

    # 生成报告
    report = generate_report(results, args.json_only)
    print(report)

    # 保存 JSON
    if not args.json_only:
        json_path = save_json_report(results)
        print(f"\nJSON 报告已保存: {json_path}")

    # 返回码：有失败则返回 1
    if any(r["status"] == "failed" for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
