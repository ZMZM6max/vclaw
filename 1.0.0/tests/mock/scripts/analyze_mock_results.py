#!/usr/bin/env python3
"""
分析 Mock E2E 测试结果
读取 test_report.json，提取 component_trace 中的 error/skipped 条目，并按组件聚合。
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def analyze(report_path: Path):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    summary = report.get("summary", {})
    results = report.get("results", [])

    print("=" * 70)
    print("Mock E2E 测试结果分析")
    print("=" * 70)
    print(f"总计: {summary.get('total', 0)}  | 通过: {summary.get('passed', 0)}  | 失败: {summary.get('failed', 0)}  | 跳过: {summary.get('skipped', 0)}")
    print()

    # 1. 列出所有失败的用例
    failed_cases = [r for r in results if r.get("status") in ("failed", "error")]
    if failed_cases:
        print("【失败的测试用例】")
        for r in failed_cases:
            print(f"  - {r['test_id']}: {r.get('semantic_reason', r.get('error_message', 'Unknown'))}")
        print()

    # 2. 从每个用例的 e2e JSON 中提取 component_trace
    trace_issues = []  # list of (test_id, layer, component, status, reason)
    component_counter = defaultdict(lambda: defaultdict(int))  # key -> status -> count
    test_case_dir = report_path.parent

    for r in results:
        tc_id = r["test_id"]
        tc_dir = test_case_dir / tc_id
        e2e_files = list(tc_dir.rglob("e2e_*.json"))
        if not e2e_files:
            continue
        with open(e2e_files[0], "r", encoding="utf-8") as f:
            e2e = json.load(f)
        for lr in e2e.get("layer_results", []):
            layer = lr["layer_name"]
            for trace in lr.get("component_trace", []):
                status = trace.get("status", "")
                comp = trace.get("component", "?")
                key = f"{layer}:{comp}"
                component_counter[key][status] += 1
                # 收集 error / skipped 以及 active（供 R7 检测关键组件覆盖）
                if status in ("error", "skipped", "active"):
                    trace_issues.append((
                        tc_id, layer, comp,
                        status,
                        trace.get("reason", "")
                    ))

    if trace_issues:
        print("【Component Trace 异常/活跃汇总】")
        for tc_id, layer, comp, status, reason in trace_issues:
            print(f"  - {tc_id} | {layer}/{comp} [{status}] {reason}")
        print()
    else:
        print("【Component Trace 异常/活跃汇总】无记录\n")

    # 按组件聚合出现次数（所有状态）
    if component_counter:
        print("【按组件聚合的出现次数】")
        for key, status_counts in sorted(component_counter.items(), key=lambda x: -sum(x[1].values())):
            total = sum(status_counts.values())
            status_str = ", ".join(f"{s}={c}" for s, c in sorted(status_counts.items()))
            print(f"  {key}: {total} 次 ({status_str})")
        print()

    # 3. 输出 summary JSON 供下游脚本使用
    output = {
        "summary": summary,
        "failed_cases": [
            {"test_id": r["test_id"], "reason": r.get("semantic_reason", r.get("error_message", ""))}
            for r in failed_cases
        ],
        "trace_issues": [
            {"test_id": t[0], "layer": t[1], "component": t[2], "status": t[3], "reason": t[4]}
            for t in trace_issues
        ],
        "component_aggregates": {k: dict(v) for k, v in component_counter.items()}
    }

    out_path = report_path.parent / "mock_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"分析结果已保存: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        default_path = Path("tests/mock/results/p0_round1/test_report.json")
        if default_path.exists():
            analyze(default_path)
        else:
            print(f"用法: python scripts/analyze_mock_results.py <path/to/test_report.json>")
            sys.exit(1)
    else:
        analyze(Path(sys.argv[1]))
