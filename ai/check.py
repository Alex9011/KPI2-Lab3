#!/usr/bin/env python3
"""Audit the UC-05 Gherkin, Mermaid diagrams, official SVGs and project links."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sequence"
OUT = ROOT / "render"
SCENARIOS = ROOT / "scenarios.md"
errors = []
files = sorted(SRC.glob("S-*.mmd"))
scenario_text = SCENARIOS.read_text(encoding="utf-8") if SCENARIOS.exists() else ""
scenario_sections = re.findall(r"(?ms)^\*\*S-(\d\d)\.[^\r\n]*\r?\n\r?\n```gherkin\r?\n(.*?)\r?\n```", scenario_text)
expected_ids = [f"{i:02}" for i in range(1, 9)]
if len(files) != 8:
    errors.append(f"Expected exactly 8 Mermaid sources, found {len(files)}")
if [sid for sid, _ in scenario_sections] != expected_ids:
    errors.append(f"Expected exactly 8 Gherkin scenarios S-01..S-08, found {[sid for sid, _ in scenario_sections]}")
if "ff8507be7712da2ec72a0a29539cd40193b02a25" not in scenario_text:
    errors.append("Gherkin source commit from Lab 2 is not identified in scenarios.md")

required_source = {
    "S-01": ["critical", "lockCopy(C1)", "findOpenLoan(C1)", "insertLoan(", "LoanCreated", "201"],
    "S-02": ["findOpenLoan(C1)", "findHistoricalLoans(C1)", "L1.id != L0.id", "insertLoan(", "LoanCreated"],
    "S-03": ["break", "findOpenLoan(C1)", "CopyAlreadyLoaned", "rollbackTx()"],
    "S-04": ["break dueAt <= borrowedAt", "InvalidDueDate", "422"],
    "S-05": ["break Member", "MemberNotFound", "404", "Читача не знайдено"],
    "S-06": ["break Copy", "CopyNotFound", "404", "Примірник не знайдено"],
    "S-07": ["par ", "lockCopy(C1)", "findOpenLoan(C1)", "CopyAlreadyLoaned", "LoanCreated"],
    "S-08": ["alt ", "403", "Недостатньо прав"],
}
allowed_participants = {
    "B": "Бібліотекар", "B1": "Бібліотекар B1", "B2": "Бібліотекар B2",
    "U": "Користувач", "UI": "Форма видачі", "C": "LoanController",
    "A": "AccessGuard", "S": "LoanService", "D": "LibraryDB",
    "API1": "LoanController B1", "API2": "LoanController B2",
    "S1": "LoanService B1", "S2": "LoanService B2", "DB": "LibraryDB",
}

for index, path in enumerate(files, 1):
    sid = f"S-{index:02}"
    src = path.read_text(encoding="utf-8")
    if not path.name.startswith(sid + "-"):
        errors.append(f"Unexpected scenario ordering in {path.name}")
    if not src.lstrip().startswith("sequenceDiagram"):
        errors.append(f"Missing sequenceDiagram in {path.name}")
    for term in required_source[sid]:
        if term not in src:
            errors.append(f"{path.name}: missing required behavior {term!r}")
    if "-->>" not in src:
        errors.append(f"{path.name}: no return messages")
    if "Copy.available" in src:
        errors.append(f"{path.name}: forbidden Copy.available field")

    participants = dict(re.findall(r"(?m)^\s*(?:actor|participant)\s+(\w+)\s+as\s+(.+?)\s*$", src))
    for alias, label in participants.items():
        if allowed_participants.get(alias) != label:
            errors.append(f"{path.name}: unknown or non-ER participant {alias} as {label}")

    activation = {alias: 0 for alias in participants}
    fragments = []
    for line_no, raw in enumerate(src.splitlines(), 1):
        line = raw.strip()
        activation_match = re.fullmatch(r"(activate|deactivate)\s+(\w+)", line)
        if activation_match:
            operation, alias = activation_match.groups()
            if alias not in activation:
                errors.append(f"{path.name}:{line_no}: activation for undeclared participant {alias}")
            elif operation == "activate":
                activation[alias] += 1
            elif activation[alias] == 0:
                errors.append(f"{path.name}:{line_no}: unmatched deactivate {alias}")
            else:
                activation[alias] -= 1
            continue

        fragment_match = re.match(r"(alt|opt|break|loop|par|critical)\b(.*)", line)
        if fragment_match:
            kind, label = fragment_match.groups()
            if not label.strip():
                errors.append(f"{path.name}:{line_no}: empty {kind} condition")
            fragments.append([kind, 0])
            continue
        if re.match(r"(?:else|and|option)\b", line):
            branch = line.split(None, 1)[0]
            if not fragments:
                errors.append(f"{path.name}:{line_no}: {branch} outside a combined fragment")
            elif branch == "else" and fragments[-1][0] != "alt":
                errors.append(f"{path.name}:{line_no}: else outside alt")
            elif branch == "and" and fragments[-1][0] != "par":
                errors.append(f"{path.name}:{line_no}: and outside par")
            elif branch == "option" and fragments[-1][0] != "critical":
                errors.append(f"{path.name}:{line_no}: option outside critical")
            elif branch == "option":
                fragments[-1][1] += 1
            continue
        if line == "end":
            if not fragments:
                errors.append(f"{path.name}:{line_no}: unmatched end")
            else:
                kind, options = fragments.pop()
                if kind == "critical" and options == 0:
                    errors.append(f"{path.name}:{line_no}: critical has no option")
    if fragments:
        errors.append(f"{path.name}: unclosed combined fragments {fragments}")
    if any(activation.values()):
        errors.append(f"{path.name}: activation bars remain open: {activation}")

    if sid in {"S-03", "S-04", "S-05", "S-06"} and "insertLoan(" in src:
        errors.append(f"{sid}: failure path must not create a Loan")
    if sid == "S-03" and ("LoanCreated" in src or "201" in src):
        errors.append("S-03: an already-issued Copy cannot have a success response")
    if sid == "S-04":
        for date in ("2026-11-01T10:00:00Z", "2026-10-31T10:00:00Z"):
            if date not in scenario_text:
                errors.append(f"S-04: Gherkin example missing: {date}")
    if sid == "S-05" and "findCopy(" in src:
        errors.append("S-05: Copy lookup must not occur after MemberNotFound")
    if sid == "S-01" and any(token in src for token in ("InvalidDueDate", "422")):
        errors.append("S-01: invalid due-date flow belongs in S-04")
    if sid == "S-07":
        for token, count in (("lockCopy(C1)", 2), ("findOpenLoan(C1)", 2), ("insertLoan(", 1), ("LoanCreated", 1), ("CopyAlreadyLoaned", 1)):
            if src.count(token) != count:
                errors.append(f"S-07: expected {count} occurrence(s) of {token}, got {src.count(token)}")
    if sid == "S-08" and re.search(r"(?:S|D)\s*->>", src):
        errors.append("S-08: unauthorized flow must not reach LoanService or LibraryDB")

    svg = OUT / f"{path.stem}.svg"
    if not svg.is_file() or svg.stat().st_size < 1000:
        errors.append(f"Missing or empty SVG: {svg.name}")
    else:
        try:
            root = ET.parse(svg).getroot()
            if not root.tag.endswith("svg"):
                errors.append(f"Render is not an SVG root element: {svg.name}")
        except ET.ParseError as exc:
            errors.append(f"Invalid SVG XML {svg.name}: {exc}")
        if svg.stat().st_mtime_ns < path.stat().st_mtime_ns:
            errors.append(f"Stale SVG predates its Mermaid source: {svg.name}")
        if "Рендер із Mermaid sequenceDiagram" in svg.read_text(encoding="utf-8"):
            errors.append(f"Legacy custom-renderer SVG remains: {svg.name}")
    print(f"{sid}: source and SVG present")

if len(list(OUT.glob("S-*.svg"))) != 8:
    errors.append(f"Expected exactly 8 SVG files, found {len(list(OUT.glob('S-*.svg')))}")
if list(OUT.glob("S-*.png")):
    errors.append("Stale PNG renders remain; this project uses SVG only")

# Cross-check source scenario outcomes and response data against the verified local Gherkin.
for sid, code in scenario_sections:
    path = next((p for p in files if p.name.startswith(f"S-{sid}-")), None)
    if not path:
        continue
    src = path.read_text(encoding="utf-8")
    if sid == "01" and ("рівно одна нова Loan" not in code or "LoanCreated" not in src):
        errors.append("S-01 source and Gherkin success outcome do not align")
    if sid == "02" and ("відмінним від L0" not in code or "L1.id != L0.id" not in src):
        errors.append("S-02 must preserve L0 and create a distinct L1")
    if sid == "03" and ("Примірник уже видано" not in code or "CopyAlreadyLoaned" not in src):
        errors.append("S-03 source and Gherkin conflict outcome do not align")
    if sid == "04" and ("Строк має бути пізніше часу видачі" not in code or "dueAt <= borrowedAt" not in src):
        errors.append("S-04 source and Gherkin invalid-date outcome do not align")
    if sid == "05" and ("Читача не знайдено" not in code or "MemberNotFound" not in src):
        errors.append("S-05 source and Gherkin missing-member outcome do not align")
    if sid == "06" and ("Примірник не знайдено" not in code or "CopyNotFound" not in src):
        errors.append("S-06 source and Gherkin missing-copy outcome do not align")
    if sid == "07" and ("рівно одна відкрита видача" not in code or src.count("LoanCreated") != 1 or src.count("CopyAlreadyLoaned") != 1):
        errors.append("S-07 must show exactly one success and one conflict")
    if sid == "08" and ("Недостатньо прав" not in code or "403" not in src):
        errors.append("S-08 source and Gherkin authorization outcome do not align")

# Run Mermaid CLI against every current source. Set MMDC_JS for a local Node entry point,
# or install the pinned official CLI so mmdc is on PATH.
node = shutil.which("node")
cli_js = os.environ.get("MMDC_JS")
mmdc = shutil.which("mmdc")
if cli_js and node:
    cli_prefix = [node, cli_js]
elif mmdc:
    cli_prefix = [mmdc]
else:
    cli_prefix = []
if not cli_prefix:
    errors.append("Official Mermaid CLI not found. Install @mermaid-js/mermaid-cli@12.2.0 or set MMDC_JS.")
else:
    puppeteer_config = os.environ.get("PUPPETEER_CONFIG")
    with tempfile.TemporaryDirectory(prefix="uc05-mermaid-check-") as temp:
        for path in files:
            output = Path(temp) / f"{path.stem}.svg"
            command = cli_prefix + ["-i", str(path), "-o", str(output)]
            if puppeteer_config:
                command += ["-p", puppeteer_config]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"Mermaid CLI could not check {path.name}: {exc}")
                continue
            if result.returncode:
                errors.append(f"Mermaid CLI rejected {path.name}: {result.stderr.strip() or result.stdout.strip()}")
            elif not output.is_file() or output.stat().st_size < 1000:
                errors.append(f"Mermaid CLI produced no valid output for {path.name}")
            else:
                print(f"{path.name}: Mermaid CLI PASS")

# Required documents and obsolete artifacts.
required_docs = [ROOT / "README.md", ROOT / "spec.md", ROOT / "scenarios.md", ROOT / "DEFENSE.md", ROOT / "adr" / "0001-loan-consistency.md", ROOT / "ai" / "audit.md", ROOT / "ai" / "prompt.md", ROOT / "ai" / "task.md", ROOT / "ai" / "STUDENT_REVIEW.md"]
for doc in required_docs:
    if not doc.is_file():
        errors.append(f"Required project document is missing: {doc.relative_to(ROOT)}")
if (ROOT / "ai" / "render.py").exists() or (ROOT / "ai" / "render-check.json").exists():
    errors.append("Obsolete custom-renderer files remain")

# Check relative Markdown links and unresolved template markers.
markdown_files = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts]
for doc in markdown_files:
    body = doc.read_text(encoding="utf-8")
    if doc != ROOT / "ai" / "prompt.md" and ("[SHA]" in body or "TODO" in body):
        errors.append(f"Unresolved template marker in {doc.relative_to(ROOT)}")
    for target in re.findall(r"\]\(([^)]+)\)", body):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        local = target.split("#", 1)[0]
        if local and not (doc.parent / local).resolve().exists():
            errors.append(f"Broken local link in {doc.relative_to(ROOT)}: {target}")

# Validate links in the HTML diagram index as well.
index_html = OUT / "index.html"
if index_html.is_file():
    html = index_html.read_text(encoding="utf-8")
    for target in re.findall(r"(?:href|src)=\"([^\"]+)\"", html):
        if target.startswith(("http://", "https://", "data:", "#")):
            continue
        if not (OUT / target.split("#", 1)[0]).resolve().exists():
            errors.append(f"Broken local link in render/index.html: {target}")
else:
    errors.append("render/index.html is missing")

if errors:
    print("\nFAIL:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print("PASS: 8 scenarios = 8 sources = 8 fresh SVGs; control fragments, activation bars, returns, Gherkin outcomes, ER participants, local links and Mermaid CLI syntax verified.")