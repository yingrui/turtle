#!/usr/bin/env python3
"""Class guardrail — `npm run check:classes`.

Two failures that never crash and never show in a typecheck:

1. **A class used in JSX that no stylesheet defines.** Renames, moves and deletions each have a
   second half; miss it and the element silently renders unstyled. A stylesheet can also be written
   and never imported — the rules exist, the bundle never loads them (only visible in the built CSS).
2. **A component sheet nothing imports** (the file sits beside `X.tsx` but no file imports it).

Only literal `className="a b c"` values are checked. Template strings and expressions
(`` className={`btn ${active}`} ``, ternaries) are skipped on purpose: their result is unknowable
without running the app, and a checker that cries wolf gets switched off.

Pre-existing debt is frozen per file in `scripts/classes-baseline.json` (a ratchet, like the style
check): fix it, re-run with `--update-baseline`, and the number drops. Never raise it.

    npm run check:classes
    npm run check:classes -- --list
    npm run check:classes -- --update-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BASELINE = Path(__file__).resolve().parent / "classes-baseline.json"

CLASSNAME = re.compile(r'className="([^"]*)"')
CLASS_DEF = re.compile(r"\.([A-Za-z_][\w-]*)", re.M)
IMPORT_SCSS = re.compile(r"import\s+['\"]([^'\"]+\.scss)['\"]")
GLOBAL_SHEETS = (
    "src/index.scss",
    "src/App.scss",
)


def _tsx_files() -> list[Path]:
    return [
        path
        for path in sorted(list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts")))
        if not re.search(r"\.(test|spec)\.", path.name)
    ]


def _scss_files() -> list[Path]:
    return sorted(SRC.rglob("*.scss"))


def _resolve(parent: str | None, selector: str) -> str:
    """One SCSS nesting step: `&` is the parent, a bare selector is a descendant.

    Without this a BEM modifier (`&--lg` inside `.user-menu__avatar`) looks like a class that no
    stylesheet defines — the very false positive that makes a checker get switched off.
    """
    parts = [part.strip() for part in selector.split(",") if part.strip()]
    resolved = []
    for part in parts:
        if "&" in part:
            resolved.append(part.replace("&", parent or ""))
        elif parent:
            resolved.append(f"{parent} {part}")
        else:
            resolved.append(part)
    return ", ".join(resolved)


def defined_classes() -> set[str]:
    """Every class name the stylesheets define, resolving `&` nesting."""
    names: set[str] = set()
    for path in _scss_files():
        stack: list[str | None] = []
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            opens = "{" in stripped
            closes = "}" in stripped
            if opens:
                selector = stripped.split("{", 1)[0].strip()
                if selector.startswith("@"):
                    # An at-rule keeps the selector context; a one-line at-rule closes itself.
                    stack.append(None)
                    if closes:
                        stack.pop()
                    continue
                parent = next((item for item in reversed(stack) if item), None)
                resolved = _resolve(parent, selector)
                names.update(CLASS_DEF.findall(resolved))
                # `.mt-2 { margin-top: …; }` is a complete rule: resolve it, do not nest into it.
                if not closes:
                    stack.append(resolved)
                continue
            if closes and stack:
                stack.pop()
    return names


def used_classes() -> dict[str, set[str]]:
    """`{file: {class, …}}` for literal `className="…"` values."""
    used: dict[str, set[str]] = defaultdict(set)
    for path in _tsx_files():
        for value in CLASSNAME.findall(path.read_text()):
            for name in value.split():
                if name and "${" not in name:
                    used[path.relative_to(ROOT).as_posix()].add(name)
    return used


def unimported_sheets() -> set[str]:
    """Component sheets (`X.scss` beside `X.tsx`) that no file imports."""
    imported: set[str] = set()
    for path in _tsx_files():
        for target in IMPORT_SCSS.findall(path.read_text()):
            imported.add(target.split("/")[-1])
    for path in (SRC / "index.scss", SRC / "App.scss"):
        if path.exists():
            for target in re.findall(r"@use\s+['\"]([^'\"]+\.scss)['\"]", path.read_text()):
                imported.add(target.split("/")[-1])
    orphans: set[str] = set()
    for sheet in _scss_files():
        component = sheet.with_suffix(".tsx")
        if not component.exists():
            continue
        if sheet.name not in imported:
            orphans.add(sheet.relative_to(ROOT).as_posix())
    return orphans


def scan() -> dict[str, list[str]]:
    """`{file: [undefined class, …]}` — what the check reports and the baseline freezes."""
    defined = defined_classes()
    problems: dict[str, list[str]] = {}
    for rel, names in used_classes().items():
        missing = sorted(name for name in names if name not in defined)
        if missing:
            problems[rel] = missing
    return problems


def load_baseline() -> dict[str, list[str]]:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text()).get("files", {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print every hit, baseline ignored")
    parser.add_argument("--update-baseline", action="store_true", help="freeze the current tree")
    args = parser.parse_args()

    problems = scan()
    orphans = unimported_sheets()

    if args.list:
        for rel in sorted(problems):
            print(f"undefined-class {rel}: {', '.join(problems[rel])}")
        for sheet in sorted(orphans):
            print(f"unimported-sheet {sheet}: nothing imports it")
        return 0

    if args.update_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Frozen class debt: JSX class names with no stylesheet, per file. The check "
                        "only ratchets down — fix them and re-run with --update-baseline."
                    ),
                    "files": {rel: sorted(names) for rel, names in sorted(problems.items())},
                },
                indent=1,
            )
            + "\n"
        )
        print(f"classes-baseline.json updated: {len(problems)} file(s) with undefined classes")
        return 0

    baseline = load_baseline()
    failures: list[str] = []
    for rel, names in sorted(problems.items()):
        allowed = set(baseline.get(rel, []))
        new = [name for name in names if name not in allowed]
        if new:
            failures.append(f"{rel}: class(es) with no stylesheet: {', '.join(new)}")
    for sheet in sorted(orphans):
        failures.append(f"{sheet}: nothing imports this stylesheet, so its rules never load")

    if failures:
        for failure in failures:
            print(f"check-classes: {failure}", file=sys.stderr)
        print(
            "check-classes: define the class (or fix the import), or freeze old code with "
            "`npm run check:classes -- --update-baseline`",
            file=sys.stderr,
        )
        return 1

    print("check-classes: OK (every literal class is styled, every component sheet is imported)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
