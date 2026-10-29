#!/usr/bin/env python3
"""Accessibility guardrail — `npm run check:a11y`.

Three failures that a sighted mouse user never notices and a screen reader cannot work around:

1. **An icon-only button with no accessible name.** `<button><Trash2 size={14} /></button>` is
   announced as "button"; there is nothing to act on.
2. **An image without `alt`** — announced as its file name, or nothing at all.
3. **A click handler on a plain `<div>`** — reachable by mouse only: no focus, no Enter/Space, no
   role. Buttons and links exist for this.

The check is a ratchet like the others: pre-existing hits freeze in `scripts/a11y-baseline.json`,
and the count only goes down.

    npm run check:a11y
    npm run check:a11y -- --list
    npm run check:a11y -- --update-baseline
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
BASELINE = Path(__file__).resolve().parent / "a11y-baseline.json"

BUTTON = re.compile(r"<button\b")
IMG = re.compile(r"<img\b")
DIV = re.compile(r"<(div|span)\b")
#: Attributes that give a control a name.
NAME_ATTRS = re.compile(r"\b(aria-label|aria-labelledby|title)\s*=")
#: A JSX child that is a component/element (icon) rather than text.
TAG_CHILD = re.compile(r"<[A-Za-z]")


def _files():
    for path in sorted(SRC.rglob("*.tsx")):
        if re.search(r"\.(test|spec)\.", path.name):
            continue
        yield path


def _tag_end(text: str, start: int) -> int:
    """Index of the `>` that closes the opening tag at `start`.

    A plain `[^>]*` stops at the `>` in `onClick={() => …}` and takes the rest of the tag for
    content, which made an icon-only button look like it had text.
    """
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == ">" and depth == 0:
            return index
        elif char in "\"'":
            quote = char
            index += 1
            while index < len(text) and text[index] != quote:
                index += 1
        index += 1
    return -1


def _attrs(text: str, match: re.Match) -> str:
    end = _tag_end(text, match.end())
    return text[match.end(): end] if end != -1 else ""


def _button_body(text: str, start: int) -> str:
    """Content between `<button …>` and its `</button>` (nested tags ignored: buttons do not nest)."""
    end = text.find("</button>", start)
    return text[start:end] if end != -1 else ""


def scan() -> dict[str, list[str]]:
    """`{file: ["icon-only button:12", …]}`."""
    problems: dict[str, list[str]] = defaultdict(list)
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text()

        for match in BUTTON.finditer(text):
            attrs = _attrs(text, match)
            if NAME_ATTRS.search(attrs):
                continue
            body = _button_body(text, _tag_end(text, match.end()) + 1)
            # `{t('header.logout')}` renders text; only a bare `<Icon />` (optionally inside braces)
            # is an icon-only button.
            without_icons = re.sub(r"\{\s*<[^>]*/>\s*\}", "", body)
            without_icons = re.sub(r"<[^>]*/>", "", without_icons)
            has_text = bool(re.search(r"[A-Za-z0-9\u4e00-\u9fff{]", without_icons))
            icon_only = bool(TAG_CHILD.search(body)) and not has_text
            if icon_only:
                line = text[: match.start()].count("\n") + 1
                problems[rel].append(f"icon-only button without a name:{line}")

        for match in IMG.finditer(text):
            if "alt=" not in _attrs(text, match):
                line = text[: match.start()].count("\n") + 1
                problems[rel].append(f"img without alt:{line}")

        for match in DIV.finditer(text):
            attrs = _attrs(text, match)
            if "onClick=" not in attrs:
                continue
            # A backdrop marked `role="presentation"` and a cell that only stops propagation are
            # plumbing, not controls.
            if 'role="presentation"' in attrs:
                continue
            # `onClick={(e) => e.stopPropagation()}` on a wrapper is plumbing, not a control.
            tail = text[match.start(): match.end() + 120]
            if re.search(r"onClick=\{\(([a-z]+)\) => \1\.stopPropagation\(\)\}", tail):
                continue
            line = text[: match.start()].count("\n") + 1
            problems[rel].append(f"{match.group(1)} with onClick (no role, not focusable):{line}")

    return dict(problems)


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

    if args.list:
        for rel in sorted(problems):
            for hit in problems[rel]:
                print(f"{rel}: {hit}")
        return 0

    if args.update_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Frozen accessibility debt, per file. Ratchet: fix a hit and re-run with "
                        "--update-baseline; never add."
                    ),
                    "files": {rel: sorted(hits) for rel, hits in sorted(problems.items())},
                },
                indent=1,
                ensure_ascii=False,
            )
            + "\n"
        )
        print(f"a11y-baseline.json updated: {sum(len(v) for v in problems.values())} hit(s)")
        return 0

    baseline = load_baseline()
    failures: list[str] = []
    for rel, hits in sorted(problems.items()):
        allowed = set(baseline.get(rel, []))
        new = [hit for hit in hits if hit not in allowed]
        if new:
            failures.append(f"{rel}: " + "; ".join(new))

    if failures:
        for failure in failures:
            print(f"check-a11y: {failure}", file=sys.stderr)
        print(
            "check-a11y: add aria-label/title to the control, alt to the image, or use a <button> — "
            "old code can be frozen with `npm run check:a11y -- --update-baseline`",
            file=sys.stderr,
        )
        return 1

    print("check-a11y: OK (controls have names, images have alt, nothing click-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
