"""
Step 3: LLM Semantic Review
Analyzes semantic deviations (dataflow, rules, prompt-XML mismatches) using an LLM.
"""

import json
import os
from pathlib import Path
from typing import Optional

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".env", override=True)
except ImportError:
    pass


class LLMClient:
    """Minimal inline LLM client to avoid circular imports."""

    def __init__(self, model_name: str, api_key: str, provider: str = "openai", base_url: Optional[str] = None, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.provider = provider
        self.base_url = base_url
        self.kwargs = kwargs

    def _get_client(self):
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key, base_url=self.base_url)
        raise NotImplementedError(f"Provider {self.provider} not supported in llm_review.py")

    def call(self, prompt: str) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are an expert architecture reviewer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()


def _build_review_prompt(
    contract_snapshot: dict,
    rule_findings: list[dict],
    failed_cases: list[dict],
    trace_issues: list[dict],
) -> str:
    # Build compact XML summary: layer -> list of component names
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    xml_lines = []
    for layer_name, layer_data in xml_contracts.items():
        comps = [c["name"] for c in layer_data.get("components", [])]
        xml_lines.append(f"{layer_name}: {', '.join(comps)}")
    xml_summary = "\n".join(xml_lines)

    # Build compact rule summary: group by rule, list layer:component
    rule_lines = []
    for rf in rule_findings:
        rule_lines.append(f"{rf['rule']} {rf['layer']}.{rf['component']}: {rf['message'][:50]}")
    rules_summary = "\n".join(rule_lines[:20])  # cap at 20 items

    # Build compact failure summary
    failure_lines = []
    for fc in failed_cases:
        reason = fc.get("reason", "")[:50]
        failure_lines.append(f"{fc['test_id']}: {reason}")
    failures_summary = "\n".join(failure_lines[:10])  # cap at 10 items

    # Build compact trace summary
    trace_lines = []
    for ti in trace_issues:
        trace_lines.append(f"{ti.get('layer', 'N/A')}.{ti.get('component', 'N/A')}: {str(ti.get('issue', ''))[:50]}")
    traces_summary = "\n".join(trace_lines[:10])  # cap at 10 items

    return f"""你是一位 VClaw 架构审查专家。请基于以下输入，分析 XML 架构文档与 Mock 测试结果之间的语义级偏差。

【XML 组件清单】
{xml_summary}

【RuleEngine 已发现的结构性问题（前30条）】
{rules_summary}

【测试失败的用例（前15条）】
{failures_summary}

【Trace Issues（前15条）】
{traces_summary}

请输出严格的 JSON 格式，不要添加任何其他内容：
{{"semantic_findings":[
  {{"id":"LLM-01","layer":"L3","component":"ErrorTranslator","issue_type":"missing_rules|dataflow_mismatch|prompt_semantic_gap|trace_anomaly","description":"详细描述","recommendation":"修复建议","affected_test_cases":["TC-14"],"patch_target":"xml|prompt","tags":[]}}
]}}

审查重点：
1. Trace 异常解释：失败用例的 component_trace 时序是否合理？
2. 数据流偏差：XML 描述的数据流与实际 trace 是否一致？
3. 规则缺失：测试失败是否因为 XML 缺少某条规则？
4. Prompt-XML 语义不一致：Prompt 中的安全策略、路径规则是否与 XML 矛盾？
"""


def run_llm_review(
    contract_snapshot: dict,
    rule_findings: list[dict],
    failed_cases: list[dict],
    trace_issues: list[dict],
    output_findings_path: Path,
    output_patch_path: Path,
    llm_config: Optional[dict] = None,
) -> tuple:
    output_findings_path.parent.mkdir(parents=True, exist_ok=True)

    # Priority: LLM_PROXY_* (proxy config) > OPENAI_* (default) > fallback
    defaults = {
        "provider": os.getenv("TEST_LLM_PROVIDER", "openai"),
        "model": os.getenv("LLM_PROXY_MODEL") or os.getenv("TEST_LLM_MODEL", "gpt-4o-mini"),
        "api_key": os.getenv("LLM_PROXY_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("LLM_PROXY_BASE_URL") or os.getenv("API_BASE_URL"),
    }
    if llm_config:
        defaults.update(llm_config)
    config = defaults

    if not config.get("api_key"):
        # Graceful fallback: write empty review and mark as skipped
        review_data = {
            "semantic_findings": [],
            "meta": {"status": "skipped", "reason": "LLM API key not available"},
        }
        output_findings_path.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")
        output_patch_path.write_text("# LLM review skipped: API key not available\n", encoding="utf-8")
        return output_findings_path, output_patch_path

    prompt = _build_review_prompt(contract_snapshot, rule_findings, failed_cases, trace_issues)
    client = LLMClient(
        model_name=config["model"],
        api_key=config["api_key"],
        provider=config.get("provider", "openai"),
        base_url=config.get("base_url"),
    )

    try:
        raw = client.call(prompt)
        # Extract JSON
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            review_data = json.loads(raw[start:end+1])
        else:
            review_data = {"semantic_findings": [], "meta": {"status": "error", "reason": "No JSON found in LLM response"}}
    except Exception as e:
        review_data = {"semantic_findings": [], "meta": {"status": "error", "reason": str(e)}}

    output_findings_path.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate suggestion patch text
    patches = []
    for finding in review_data.get("semantic_findings", []):
        target = finding.get("patch_target", "xml")
        comp = finding.get("component", "Unknown")
        patches.append(f"# LLM suggestion for {comp} (target={target})")
        patches.append(f"# {finding.get('description', '')}")
        patches.append(f"# Recommendation: {finding.get('recommendation', '')}")
        if target == "prompt":
            patches.append("# [PROMPT_FIX]")
            patches.append("# Apply to: tests/mock/layer_prompts.py")
        patches.append("")
    patch_text = "\n".join(patches) if patches else "# No LLM suggestions generated\n"
    output_patch_path.write_text(patch_text, encoding="utf-8")

    return output_findings_path, output_patch_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run LLM semantic review")
    parser.add_argument("--contract-snapshot", type=Path, required=True)
    parser.add_argument("--rule-findings", type=Path, required=True)
    parser.add_argument("--mock-analysis", type=Path, required=True)
    parser.add_argument("--output-findings", type=Path, required=True)
    parser.add_argument("--output-patch", type=Path, required=True)
    args = parser.parse_args()

    contract_snapshot = json.loads(args.contract_snapshot.read_text(encoding="utf-8"))
    rule_findings = json.loads(args.rule_findings.read_text(encoding="utf-8"))
    mock_analysis = json.loads(args.mock_analysis.read_text(encoding="utf-8"))

    run_llm_review(
        contract_snapshot=contract_snapshot,
        rule_findings=rule_findings,
        failed_cases=mock_analysis.get("failed_cases", []),
        trace_issues=mock_analysis.get("trace_issues", []),
        output_findings_path=args.output_findings,
        output_patch_path=args.output_patch,
    )
    print(f"LLM review: {args.output_findings}")
    print(f"LLM patch: {args.output_patch}")


if __name__ == "__main__":
    main()
