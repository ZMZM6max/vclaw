"""
Step 2: Deterministic Rule Engine (R1-R7)
Produces rule_findings.json and auto_patch.patch.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def _xml_file_for_layer(xml_contracts: dict, layer: str) -> str:
    for key, val in xml_contracts.items():
        if key.startswith(layer):
            return val.get("file", f"docs/03_specs/{key}.xml")
    return f"docs/03_specs/{layer}_Unknown.xml"


# ---------------------------------------------------------------------------
# R1: Component in trace but missing in XML
# ---------------------------------------------------------------------------
def R1_missing_in_xml(contract_snapshot: dict, mock_analysis: dict) -> List[Dict[str, Any]]:
    findings = []
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    aggregates = mock_analysis.get("component_aggregates", {})
    # Build per-layer component sets
    layer_components = {}
    for key, val in xml_contracts.items():
        layer = key.split("_")[0] if "_" in key else key
        layer_components.setdefault(layer, set())
        for comp in val.get("components", []):
            layer_components[layer].add(comp["name"])

    for trace_key in aggregates:
        if ":" not in trace_key:
            continue
        layer, comp = trace_key.split(":", 1)
        if comp not in layer_components.get(layer, set()):
            findings.append({
                "rule": "R1",
                "severity": "high",
                "layer": layer,
                "component": comp,
                "message": f"Component '{comp}' appears in trace but is missing in XML.",
                "file": _xml_file_for_layer(xml_contracts, layer),
            })
    return findings


# ---------------------------------------------------------------------------
# R2: Component in XML but never touched in any test
# ---------------------------------------------------------------------------
def R2_unused_in_xml(contract_snapshot: dict, mock_analysis: dict) -> List[Dict[str, Any]]:
    findings = []
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    aggregates = mock_analysis.get("component_aggregates", {})
    code_contracts = contract_snapshot.get("code_contracts", {})

    trace_components = set()
    for key in aggregates:
        if ":" in key:
            trace_components.add(key.split(":", 1)[1])

    for key, val in xml_contracts.items():
        layer = key.split("_")[0] if "_" in key else key
        dataflows = val.get("dataflows", [])
        interfaces = val.get("interfaces", [])
        code_layer = code_contracts.get("code", {}).get(layer, {})
        code_names = set(code_layer.get("classes", []) + code_layer.get("methods", []))

        for comp in val.get("components", []):
            name = comp["name"]
            if name in trace_components:
                continue
            # Conservative check: does it have any references?
            has_references = False
            for df in dataflows:
                if df.get("from") == name or df.get("to") == name:
                    has_references = True
                    break
                # Check step_text for component name references
                step_text = df.get("step_text", "")
                if step_text and name in step_text:
                    has_references = True
                    break
            for iface in interfaces:
                if name in iface.get("methods", []):
                    has_references = True
                    break
            for cn in code_names:
                if name in cn:
                    has_references = True
                    break

            if has_references:
                findings.append({
                    "rule": "R2",
                    "severity": "low",
                    "layer": layer,
                    "component": name,
                    "message": f"Component '{name}' is defined in XML but never touched in tests. It has references, so marked as Underutilized.",
                    "action": "observe",
                    "file": val.get("file", _xml_file_for_layer(xml_contracts, layer)),
                })
            else:
                findings.append({
                    "rule": "R2",
                    "severity": "medium",
                    "layer": layer,
                    "component": name,
                    "message": f"Component '{name}' is defined in XML, never touched in tests, and has no references. Consider removal.",
                    "action": "remove",
                    "file": val.get("file", _xml_file_for_layer(xml_contracts, layer)),
                })
    return findings


# ---------------------------------------------------------------------------
# R3: XML component status inconsistent with code contract snapshot
# ---------------------------------------------------------------------------
def R3_status_mismatch(contract_snapshot: dict) -> List[Dict[str, Any]]:
    findings = []
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    code_contracts = contract_snapshot.get("code_contracts", {})
    code_layers = code_contracts.get("code", {})

    for key, val in xml_contracts.items():
        layer = key.split("_")[0] if "_" in key else key
        code_classes = set(code_layers.get(layer, {}).get("classes", []))
        for comp in val.get("components", []):
            name = comp["name"]
            # Simple heuristic: if class exists in code, it should be implemented=true
            implemented_in_code = name in code_classes
            # We can't reliably read XML attributes from our extracted dict,
            # so this rule emits a low-severity observation for now.
            if not implemented_in_code:
                findings.append({
                    "rule": "R3",
                    "severity": "low",
                    "layer": layer,
                    "component": name,
                    "message": f"Component '{name}' not found in code contract snapshot; verify XML status.",
                    "file": val.get("file", _xml_file_for_layer(xml_contracts, layer)),
                })
    return findings


# ---------------------------------------------------------------------------
# R4: Prompt mentions component missing in XML
# ---------------------------------------------------------------------------
def R4_prompt_missing_in_xml(contract_snapshot: dict) -> List[Dict[str, Any]]:
    findings = []
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    prompt_contracts = contract_snapshot.get("mock_prompt_contracts", {})
    xml_components = set()
    for val in xml_contracts.values():
        for comp in val.get("components", []):
            xml_components.add(comp["name"])

    for layer, pdata in prompt_contracts.items():
        for comp in pdata.get("mentioned_components", []):
            if comp not in xml_components:
                findings.append({
                    "rule": "R4",
                    "severity": "medium",
                    "layer": layer,
                    "component": comp,
                    "message": f"Prompt mentions '{comp}' but it is missing in XML.",
                    "action": "prompt_fix_or_add_to_xml",
                    "tag": "[PROMPT_FIX]",
                })
    return findings


# ---------------------------------------------------------------------------
# R5: Prompt vs XML interface/rule inconsistency (placeholder heuristic)
# ---------------------------------------------------------------------------
def R5_prompt_xml_inconsistency(contract_snapshot: dict) -> List[Dict[str, Any]]:
    # Detailed semantic comparison is deferred to LLM review.
    return []


# ---------------------------------------------------------------------------
# R6: Cross-layer dependency mismatch
# ---------------------------------------------------------------------------
def R6_dependency_mismatch(contract_snapshot: dict) -> List[Dict[str, Any]]:
    # Minimal implementation: no-op unless explicit <dependencies> nodes exist.
    return []


# ---------------------------------------------------------------------------
# R7: Critical component never active
# ---------------------------------------------------------------------------
def R7_critical_never_active(
    contract_snapshot: dict,
    mock_analysis: dict,
    trace_issues: List[dict],
) -> List[Dict[str, Any]]:
    findings = []
    xml_contracts = contract_snapshot.get("xml_contracts", {})
    # Determine which components were ever active
    active_components = set()
    for issue in trace_issues:
        if issue.get("status") == "active":
            active_components.add(f"{issue.get('layer')}:{issue.get('component')}")

    for key, val in xml_contracts.items():
        layer = key.split("_")[0] if "_" in key else key
        for comp in val.get("components", []):
            name = comp["name"]
            trace_key = f"{layer}:{name}"
            # Heuristic: treat any component whose name sounds critical as critical
            is_critical = name.lower() in {
                "reactengine", "securityguard", "toolcaller",
                "toolregistry", "sandboxmanager", "securityenforcer",
            }
            if is_critical and trace_key not in active_components:
                # But it might have been skipped; if it appears in aggregates at all, it's covered
                aggregates = mock_analysis.get("component_aggregates", {})
                if trace_key in aggregates:
                    findings.append({
                        "rule": "R7",
                        "severity": "medium",
                        "layer": layer,
                        "component": name,
                        "message": f"Critical component '{name}' appears in traces but never as 'active'. Consider adding test coverage.",
                        "action": "add_tests",
                        "file": val.get("file", _xml_file_for_layer(xml_contracts, layer)),
                    })
    return findings


# ---------------------------------------------------------------------------
# Patch generation
# ---------------------------------------------------------------------------
def _generate_patches(findings: List[dict]) -> str:
    patches = []
    for f in findings:
        if f.get("action") == "remove":
            file_path = f.get("file", "")
            comp = f["component"]
            # We generate a simplistic patch header; real patches are best-effort.
            patches.append(f"--- a/{file_path}\n+++ b/{file_path}\n")
            patches.append(f"# R2: Remove unused component {comp} (deterministic rule)\n")
            patches.append(f"# TODO: Manual removal required for <Component name=\"{comp}\">...</Component>\n")
        elif f.get("rule") == "R1":
            file_path = f.get("file", "")
            comp = f["component"]
            patches.append(f"--- a/{file_path}\n+++ b/{file_path}\n")
            patches.append(f"# R1: Add missing component {comp} (deterministic rule)\n")
            patches.append(f"# TODO: Add <Component name=\"{comp}\">...</Component>\n")
    return "\n".join(patches)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
def run_rule_engine(
    contract_snapshot_path: Path,
    mock_analysis_path: Path,
    output_findings_path: Path,
    output_patch_path: Path,
):
    contract_snapshot = json.loads(contract_snapshot_path.read_text(encoding="utf-8"))
    mock_analysis = json.loads(mock_analysis_path.read_text(encoding="utf-8"))
    trace_issues = mock_analysis.get("trace_issues", [])

    findings = []
    findings.extend(R1_missing_in_xml(contract_snapshot, mock_analysis))
    findings.extend(R2_unused_in_xml(contract_snapshot, mock_analysis))
    findings.extend(R3_status_mismatch(contract_snapshot))
    findings.extend(R4_prompt_missing_in_xml(contract_snapshot))
    findings.extend(R5_prompt_xml_inconsistency(contract_snapshot))
    findings.extend(R6_dependency_mismatch(contract_snapshot))
    findings.extend(R7_critical_never_active(contract_snapshot, mock_analysis, trace_issues))

    output_findings_path.parent.mkdir(parents=True, exist_ok=True)
    output_findings_path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    patch_text = _generate_patches(findings)
    output_patch_path.write_text(patch_text, encoding="utf-8")

    return output_findings_path, output_patch_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run deterministic rule engine")
    parser.add_argument("--contract-snapshot", type=Path, required=True)
    parser.add_argument("--mock-analysis", type=Path, required=True)
    parser.add_argument("--output-findings", type=Path, required=True)
    parser.add_argument("--output-patch", type=Path, required=True)
    args = parser.parse_args()
    run_rule_engine(args.contract_snapshot, args.mock_analysis, args.output_findings, args.output_patch)
    print(f"Rule findings: {args.output_findings}")
    print(f"Auto patch: {args.output_patch}")


if __name__ == "__main__":
    main()
