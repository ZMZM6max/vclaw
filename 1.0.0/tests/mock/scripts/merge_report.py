"""
Step 4: Report Merger
Combines rule findings and LLM review into a single markdown report.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def generate_report(
    rule_findings: List[dict],
    llm_review: dict,
    auto_patch_text: str,
    llm_patch_text: str,
    summary: dict,
    output_path: Path,
) -> Path:
    sections = []

    # 1. 执行摘要
    llm_findings = llm_review.get("semantic_findings", [])
    sections.append("# XML 优化报告\n")
    sections.append(f"**生成时间**: {datetime.now().isoformat()}  \n")
    sections.append("## 1. 执行摘要\n")
    sections.append(f"| 指标 | 数值 |\n|------|------|\n")
    sections.append(f"| 总计用例 | {summary.get('total', 0)} |\n")
    sections.append(f"| 通过 | {summary.get('passed', 0)} |\n")
    sections.append(f"| 失败 | {summary.get('failed', 0)} |\n")
    sections.append(f"| 跳过 | {summary.get('skipped', 0)} |\n")
    sections.append(f"| 规则发现 | {len(rule_findings)} |\n")
    sections.append(f"| LLM 发现 | {len(llm_findings)} |\n\n")

    # 2. 组件级偏差
    r1 = [f for f in rule_findings if f["rule"] == "R1"]
    r2 = [f for f in rule_findings if f["rule"] == "R2"]
    r3 = [f for f in rule_findings if f["rule"] == "R3"]
    r7 = [f for f in rule_findings if f["rule"] == "R7"]
    llm_comp = [f for f in llm_findings if f.get("issue_type") in ("missing_rules", "trace_anomaly")]

    sections.append("## 2. 组件级偏差\n")
    sections.append("### R1: XML 中缺失但在 Trace 中出现的组件\n")
    for f in r1:
        sections.append(f"- **{f['layer']}** `{f['component']}`: {f['message']}\n")
    sections.append("\n### R2/R3/R7: 组件状态与覆盖率偏差\n")
    for f in r2 + r3 + r7:
        sections.append(f"- **{f['layer']}** `{f['component']}` ({f['rule']}): {f['message']}\n")
    sections.append("\n### LLM 组件相关发现\n")
    for f in llm_comp:
        sections.append(f"- **{f['layer']}** `{f['component']}`: {f['description']}\n")

    # 3. 接口级偏差
    r5 = [f for f in rule_findings if f["rule"] == "R5"]
    r6 = [f for f in rule_findings if f["rule"] == "R6"]
    llm_iface = [f for f in llm_findings if f.get("issue_type") == "prompt_semantic_gap"]
    sections.append("\n## 3. 接口级偏差\n")
    for f in r5 + r6 + llm_iface:
        sections.append(f"- **{f.get('layer', 'N/A')}** `{f.get('component', 'N/A')}`: {f.get('message', f.get('description', ''))}\n")
    if not (r5 + r6 + llm_iface):
        sections.append("- 未发现接口级偏差。\n")

    # 4. 数据流/规则级偏差
    llm_dataflow = [f for f in llm_findings if f.get("issue_type") == "dataflow_mismatch"]
    sections.append("\n## 4. 数据流/规则级偏差\n")
    for f in llm_dataflow:
        sections.append(f"- **{f['layer']}** `{f['component']}`: {f['description']}\n")
    if not llm_dataflow:
        sections.append("- 未发现明显的数据流时序偏差。\n")

    # 5. 测试覆盖率级偏差
    sections.append("\n## 5. 测试覆盖率级偏差\n")
    for f in r7:
        sections.append(f"- **{f['layer']}** `{f['component']}`: {f['message']}\n")
    if not r7:
        sections.append("- 未发现覆盖率异常。\n")

    # 6. 建议补丁清单
    sections.append("\n## 6. 建议补丁清单\n")
    sections.append("### auto_patch.patch（规则引擎生成）\n")
    sections.append("```diff\n")
    sections.append(auto_patch_text[:3000] if auto_patch_text else "# 无规则补丁\n")
    sections.append("\n```\n")
    sections.append("\n### llm_suggestions.patch（LLM 语义审查生成）\n")
    sections.append("```diff\n")
    sections.append(llm_patch_text[:3000] if llm_patch_text else "# 无 LLM 建议补丁\n")
    sections.append("\n```\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(sections), encoding="utf-8")
    return output_path


def main():
    import json
    import argparse
    parser = argparse.ArgumentParser(description="Merge findings into report")
    parser.add_argument("--rule-findings", type=Path, required=True)
    parser.add_argument("--llm-review", type=Path, required=True)
    parser.add_argument("--auto-patch", type=Path, required=True)
    parser.add_argument("--llm-patch", type=Path, required=True)
    parser.add_argument("--test-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rule_findings = json.loads(args.rule_findings.read_text(encoding="utf-8"))
    llm_review = json.loads(args.llm_review.read_text(encoding="utf-8"))
    auto_patch_text = args.auto_patch.read_text(encoding="utf-8")
    llm_patch_text = args.llm_patch.read_text(encoding="utf-8")
    test_report = json.loads(args.test_report.read_text(encoding="utf-8"))

    generate_report(
        rule_findings=rule_findings,
        llm_review=llm_review,
        auto_patch_text=auto_patch_text,
        llm_patch_text=llm_patch_text,
        summary=test_report.get("summary", {}),
        output_path=args.output,
    )
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
