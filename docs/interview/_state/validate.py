"""Validate documentation only; never import application modules or call services."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).resolve().parent
DOCS = STATE.parent
HEAD = re.compile(r"^### Q(\d{3})[：:]\s*(.*?)\s*$", re.M)
PARTS = ["1.标准答案", "2.面试口述版", "3.Adaptive-RAG实际实现", "4.面试官可能追问", "5.测试与证据"]
LINK = re.compile(r"\[[^\]\n]+\]\(([^\s)]+)\)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--output")
    parser.add_argument("--preservation", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((STATE / "questions.json").read_text(encoding="utf-8"))
    expected = {q["id"]: q for q in manifest["questions"] if q["batch"] <= args.batch}
    all_questions = {q["id"]: q for q in manifest["questions"]}
    errors, warnings, observed = [], [], {}
    link_count = source_count = code_count = 0
    source = ROOT / manifest["source_file"]
    if not source.exists():
        source = STATE / "question-source.md"  # Exact supplied source snapshot for cloned docs.
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["source_sha256"]:
        errors.append("Original question bank was modified")
    file_names = sorted({q["answer_file"] for q in manifest["questions"]})
    for name in file_names:
        path = DOCS / name
        if not path.exists():
            if any(q["answer_file"] == name for q in expected.values()):
                errors.append(f"Missing answer file: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        headings = list(HEAD.finditer(text))
        for i, match in enumerate(headings):
            number = int(match[1])
            if number in observed:
                errors.append(f"Duplicate Q{number:03d}")
            observed[number] = name
            q = all_questions.get(number)
            if q is None:
                errors.append(f"Invented Q{number:03d}")
                continue
            if name != q["answer_file"]:
                errors.append(f"Q{number:03d}: wrong destination")
            if match[2] != q["canonical_question"]:
                errors.append(f"Q{number:03d}: original title mismatch")
            if f'<a id="q{number:03d}"></a>' not in text[:match.start()]:
                errors.append(f"Q{number:03d}: missing explicit anchor")
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            block = text[match.end():end]
            parts = list(re.finditer(r"^####\s+(.+?)\s*$", block, re.M))
            actual = [re.sub(r"\s+", "", p[1]) for p in parts]
            if actual != PARTS:
                errors.append(f"Q{number:03d}: five-section structure {actual}")
                continue
            bodies = [block[p.end():parts[j + 1].start() if j + 1 < len(parts) else len(block)] for j, p in enumerate(parts)]
            followups = len(re.findall(r"追问[：:]", bodies[3]))
            if not 2 <= followups <= 4:
                errors.append(f"Q{number:03d}: {followups} followups, expected2..4")
            if "答" not in bodies[3]:
                errors.append(f"Q{number:03d}: followups lack reference answers")
            oral = re.sub(r"\s+", "", bodies[1])
            if len(oral) < 160:
                warnings.append(f"Q{number:03d}: oral answer short ({len(oral)} chars)")
            if not LINK.search(bodies[2]):
                errors.append(f"Q{number:03d}: no source link in project implementation")
            if not LINK.search(bodies[4]) and "未验证" not in bodies[4]:
                errors.append(f"Q{number:03d}: no evidence link or explicit unverified label")
        for target in LINK.findall(text):
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("//"):
                continue
            file_part, _, fragment = unquote(target).partition("#")
            destination = (path.parent / file_part).resolve() if file_part else path
            link_count += 1
            if not destination.is_file():
                errors.append(f"{name}: missing link {target}")
                continue
            if re.fullmatch(r"L\d+(?:-L\d+)?", fragment):
                source_count += 1
                count = len(destination.read_text(encoding="utf-8-sig").splitlines())
                numbers = [int(n) for n in re.findall(r"\d+", fragment)]
                if any(n < 1 or n > count for n in numbers):
                    errors.append(f"{name}: invalid source line {target}")
            elif re.fullmatch(r"q\d{3}", fragment) and destination.parent == DOCS:
                if f'<a id="{fragment}"></a>' not in destination.read_text(encoding="utf-8"):
                    errors.append(f"{name}: missing question anchor {target}")
        if text.count("```") % 2:
            errors.append(f"{name}: unbalanced fenced code blocks")
        for snippet in re.findall(r"```python\s*\n(.*?)\n```", text, re.S):
            code_count += 1
            try:
                ast.parse(snippet)
            except SyntaxError as exc:
                errors.append(f"{name}: Python example syntax at snippet line{exc.lineno}")
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    if missing:
        errors.append(f"Missing IDs: {missing}")
    if unexpected:
        errors.append(f"Later-batch IDs written before release: {unexpected}")
    preservation = None
    if args.preservation:
        baseline = json.loads((STATE / "preservation.json").read_text(encoding="utf-8"))
        changed = [name for name, digest in baseline["tracked_non_interview"].items() if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
        for name, digest in baseline["existing_interview"].items():
            normalized = name.replace("\\", "/")
            if normalized.endswith("/README.md"):
                original_readme = subprocess.check_output(
                    ["git", "show", f"{manifest['base_head']}:{normalized}"], cwd=ROOT
                ).decode("utf-8").replace("\r\n", "\n")
                current_readme = (ROOT / normalized).read_text(encoding="utf-8").replace("\r\n", "\n")
                without_entry = re.sub(
                    r"\n## 2026 年 360 题答案库\n\n[^\n]+\n", "", current_readme, count=1
                )
                if without_entry != original_readme:
                    changed.append(normalized)
                continue
            if not (ROOT / normalized).is_file() or hashlib.sha256((ROOT / normalized).read_bytes()).hexdigest() != digest:
                changed.append(normalized)
        stash = subprocess.check_output(["git", "stash", "list", "--format=%H"], cwd=ROOT, text=True).splitlines()
        preservation = {"changed_protected_paths": changed, "stash_unchanged": stash == baseline["stash"], "source_question_unchanged": hashlib.sha256(source.read_bytes()).hexdigest() == baseline["question_sha256"]}
        if changed or not preservation["stash_unchanged"]:
            errors.append("Protected source/history/Stash changed")
    topics = Counter(all_questions[n]["topic"] for n in observed if n in all_questions)
    result = {"batch": args.batch, "expected": len(expected), "answered": len(observed), "topics_covered": dict(topics), "errors": errors, "warnings": warnings, "relative_links_checked": link_count, "source_line_links_checked": source_count, "python_examples_ast_checked_not_executed": code_count, "preservation": preservation, "business_tests_executed": False, "paid_calls": 0}
    if args.output:
        (STATE / args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
