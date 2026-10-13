"""
Step 1: Contract Preparation
Reads XML docs, mock prompts, and the static code-contract snapshot,
then produces a unified contract_snapshot.json.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


def _extract_components(root: ET.Element) -> list:
    components = []
    for comp in root.findall(".//Component"):
        name = comp.get("name", "").strip()
        if not name:
            continue
        desc_elem = comp.find("Description")
        methods_elems = comp.findall(".//Method")
        components.append({
            "name": name,
            "description": desc_elem.text.strip() if desc_elem is not None and desc_elem.text else "",
            "methods": [m.text.strip() for m in methods_elems if m.text],
        })
    return components


def _extract_interfaces(root: ET.Element) -> list:
    interfaces = []
    for iface in root.findall(".//Interface"):
        name = iface.get("name", "").strip()
        if not name:
            continue
        methods = [m.text.strip() for m in iface.findall("Method") if m.text]
        interfaces.append({"name": name, "methods": methods})
    return interfaces


def _extract_dataflows(root: ET.Element) -> list:
    flows = []
    for df in root.findall(".//DataFlow"):
        # Extract explicit from/to attributes (e.g. <DataFlow from="X" to="Y">)
        src = df.get("from", "").strip()
        dst = df.get("to", "").strip()
        desc_elem = df.find("Description")
        description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
        if src or dst:
            flows.append({
                "from": src,
                "to": dst,
                "description": description,
            })
        # Also extract Step text references (e.g. <Step>ComponentName does something</Step>)
        for step in df.findall("Step"):
            step_text = step.text.strip() if step.text else ""
            if step_text:
                flows.append({
                    "from": "",
                    "to": "",
                    "step_text": step_text,
                })
    return flows


def extract_xml_contracts(xml_dir: Path) -> dict:
    contracts = {}
    for xml_file in sorted(xml_dir.glob("L*.xml")):
        layer_key = xml_file.stem
        tree = ET.parse(xml_file)
        root = tree.getroot()
        contracts[layer_key] = {
            "file": str(xml_file),
            "components": _extract_components(root),
            "interfaces": _extract_interfaces(root),
            "dataflows": _extract_dataflows(root),
        }
    return contracts


def extract_mock_prompt_contracts(prompt_path: Path) -> dict:
    """Extract component names from layer component trace requirements.

    Only extracts components listed in the numbered component trace lists
    (e.g., '1. ProtocolAdapter - 协议适配') to avoid false positives from
    error names, data models, and XML tag names that appear elsewhere in
    the prompts.
    """
    text = prompt_path.read_text(encoding="utf-8")
    contracts = {}
    for layer_num in range(1, 7):
        layer = f"L{layer_num}"
        trace_var = f"{layer}_COMPONENT_TRACE_REQUIREMENT"
        pattern = rf"{trace_var}\s*=\s*\"\"\"(.*?)\"\"\""
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            pattern_single = rf"{trace_var}\s*=\s*'(.*?)'"
            match = re.search(pattern_single, text, re.DOTALL)
        trace_text = match.group(1) if match else ""
        # Extract component names from numbered list items like:
        #   "1. ProtocolAdapter - 协议适配"
        #   "5. ErrorTranslator - 错误转译（仅当...）"
        components = sorted(set(re.findall(r"^\d+\.\s+([A-Za-z]+)", trace_text, re.MULTILINE)))
        contracts[layer] = {
            "mentioned_components": components,
        }
    return contracts


def load_code_contracts(contract_path: Path) -> dict:
    return json.loads(contract_path.read_text(encoding="utf-8"))


def build_contract_snapshot(
    xml_dir: Path,
    prompt_path: Path,
    contract_path: Path,
    output_path: Path,
) -> dict:
    snapshot = {
        "generated_at": datetime.now().isoformat(),
        "xml_contracts": extract_xml_contracts(xml_dir),
        "mock_prompt_contracts": extract_mock_prompt_contracts(prompt_path),
        "code_contracts": load_code_contracts(contract_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Prepare contract snapshot")
    parser.add_argument("--xml-dir", type=Path, default=Path("docs/03_specs"))
    parser.add_argument("--prompt", type=Path, default=Path("tests/mock/layer_prompts.py"))
    parser.add_argument("--contract", type=Path, default=Path(".claude/planning/contract_extraction.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_contract_snapshot(args.xml_dir, args.prompt, args.contract, args.output)
    print(f"Contract snapshot written to {args.output}")


if __name__ == "__main__":
    main()
