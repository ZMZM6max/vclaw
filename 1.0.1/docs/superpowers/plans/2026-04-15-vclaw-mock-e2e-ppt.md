# VClaw Mock E2E PPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an 11-page technical presentation (`.claude/0415_vclaw_mock_e2e.pptx`) showcasing the VClaw Mock E2E testing framework using pptxgenjs.

**Architecture:** A single Node.js script using `pptxgenjs` to programmatically generate all 11 slides with shapes, text, tables, and charts based on the approved design spec. No template — created from scratch.

**Tech Stack:** Node.js, pptxgenjs, LibreOffice (for PDF conversion QA), Poppler (for image QA)

---

### Task 1: Write the PPT generation script

**Files:**
- Create: `.claude/generate_ppt.js`
- Output: `.claude/0415_vclaw_mock_e2e.pptx`

- [ ] **Step 1.1: Initialize the presentation with color palette and fonts**

```javascript
const pptxgen = require("pptxgenjs");
let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'VClaw Team';
pres.title = 'VClaw Mock E2E 测试框架';

// Color constants
const COLORS = {
  primary: "065A82",     // deep sea blue
  secondary: "1C7293",   // teal
  accent: "02C39A",      // bright cyan
  bg: "F8F9FA",          // light gray-white
  text: "212529",        // dark text
  white: "FFFFFF"
};
```

- [ ] **Step 1.2: Create Slide 1 — Cover**

Dark background (`065A82`). Left side: title + subtitle. Right side: 6-layer stacked rectangles (L1-L6) with layer names.

- [ ] **Step 1.3: Create Slide 2 — Testing Pain Points**

Light background. Three pain-point cards with icons (shapes). Bottom: conclusion callout box.

- [ ] **Step 1.4: Create Slide 3 — Core Solution**

"6 LLMs simulate 6 layers" as the central concept. Large "6" callout. Three key advantage bullet points on the right.

- [ ] **Step 1.5: Create Slide 4 — Framework Architecture Overview**

Three module boxes connected by arrows. Modules: `e2e_framework.py`, `layer_protocol.py`, `test_cases.py / run_e2e_tests.py`.

- [ ] **Step 1.6: Create Slide 5 — Six-Layer Simulation Architecture**

A clean table showing L1-L6: simulation responsibility and core output type.

- [ ] **Step 1.7: Create Slide 6 — Inter-Layer Data Protocol**

Data flow diagram using arrows and Pydantic model labels. Key flows: L1→L2 (`StandardEvent`), L2→L3 (`SessionContext`), L3→L5 (`AgentAction`), L5→L3 (`Observation`), L6→L5 (`ExecutionResult`).

- [ ] **Step 1.8: Create Slide 7 — Test Case Design**

"32 test cases, 8 scenarios" as a big stat. 8 scenario tags in a 2x4 grid with colored badges.

- [ ] **Step 1.9: Create Slide 8 — Test Runner Capabilities**

CLI command examples on the left. Output directory tree on the right.

- [ ] **Step 1.10: Create Slide 9 — Complete Journey (TC-01)**

Timeline / process flow showing 6 steps from user request to final response. Use numbered circles and connecting arrows.

- [ ] **Step 1.11: Create Slide 10 — Real LLM E2E Testing**

Comparison table: Mock E2E vs Real LLM E2E. Key features of `RealLLMTestExecutor` as bullet points.

- [ ] **Step 1.12: Create Slide 11 — Summary & Outlook**

Dark background. Three sections: Achieved (checkmarks), Value (highlight), Next Steps (arrows).

- [ ] **Step 1.13: Write the file and run the script**

Run: `node .claude/generate_ppt.js`
Expected: `.claude/0415_vclaw_mock_e2e.pptx` is created.

---

### Task 2: QA the PPT

**Files:**
- Input: `.claude/0415_vclaw_mock_e2e.pptx`
- Tools: `python -m markitdown`, `python scripts/thumbnail.py`, LibreOffice, Poppler

- [ ] **Step 2.1: Content QA with markitdown**

Run: `python -m markitdown .claude/0415_vclaw_mock_e2e.pptx`
Check: All 11 slides have expected titles and content. No placeholder text.

- [ ] **Step 2.2: Convert to images for visual QA**

Run:
```bash
python scripts/office/soffice.py --headless --convert-to pdf .claude/0415_vclaw_mock_e2e.pptx
pdftoppm -jpeg -r 150 .claude/0415_vclaw_mock_e2e.pdf .claude/slide
```

- [ ] **Step 2.3: Visual inspection via subagent**

Dispatch subagent to inspect all 11 slide images for overlapping elements, text overflow, low contrast, and spacing issues.

- [ ] **Step 2.4: Fix any issues found and re-verify**

Edit `.claude/generate_ppt.js`, re-run, and re-check affected slides until clean.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-15-vclaw-mock-e2e-ppt.md`.**

Two execution options:
1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
