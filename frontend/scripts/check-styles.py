#!/usr/bin/env python3
"""Design-system guardrails for the SPA — `npm run check:styles`.

The tokens in `src/styles/design-system/` only work if feature code uses them. A raw hex or a
magic pixel is not a crash: it is a component that ignores dark mode, or a spacing rhythm that
drifts one pixel at a time. Neither shows up in a typecheck.

The rules are the conventions from `docs/design-system.md`, and the debt that predates them is frozen
in `scripts/styles-baseline.json` — a **ratchet**: existing violations are tolerated, new ones fail.
Shrink the numbers; never grow them.

    npm run check:styles              # fail on anything above the baseline
    npm run check:styles -- --list     # print every hit (baseline ignored), for fixing
    npm run check:styles -- --update-baseline   # rewrite the baseline from the current tree

Deliberately not checked: `px` in borders, radii, widths and `@media` inside the token/mixin files —
those are geometry, not the spacing rhythm.
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
BASELINE = Path(__file__).resolve().parent / "styles-baseline.json"

#: Files that legitimately hold raw values (they *are* the token layer).
#: `!important` is how a utility wins against a component's own rule; that is the point of one.
IMPORTANT_ALLOWED = {"src/styles/design-system/_utilities.scss"}

TOKEN_FILES = {
    "src/styles/design-system/_css-variables.scss",
    "src/styles/design-system/_tokens.scss",
    "src/styles/design-system/_mixins.scss",
    "src/styles/design-system/_global.scss",
    # turtle-only primitives (`--space-px`, `$bp-wide-min`, …) are values too.
    "src/styles/design-system/_local-tokens.scss",
    "src/styles/design-system/_local-css-variables.scss",
}

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PX_FONT = re.compile(r"font-size:\s*[0-9]+px")
PX_SPACE = re.compile(r"(?:padding|margin|gap)[a-z-]*:\s*[^;{}]*[0-9]+px")
PX_MEDIA = re.compile(
    r"@media[^{]*[0-9]+px|@include (?:max|min)-width\(\s*[0-9]+px"
)  # `ds.$bp-*` / `lt.$bp-*` are tokens, not raw pixels
RAW_Z = re.compile(r"z-index:\s*[0-9]+")
IMPORTANT = re.compile(r"!important")
INLINE_STYLE = re.compile(r"style=\{\{")
DEBUG = re.compile(r"console\.(?:log|debug)\s*\(|^\s*debugger\b")

#: rule → (regex, applies to, hint)
SCSS_RULES = {
    "raw-hex-color": (HEX, "*.scss", "use var(--color-*) — a raw hex ignores dark mode"),
    "px-font-size": (PX_FONT, "*.scss", "use var(--text-*) from the type scale"),
    "px-spacing": (PX_SPACE, "*.scss", "use var(--space-*) on the 4px grid"),
    "px-breakpoint": (PX_MEDIA, "*.scss", "use @include max-width(ds.$bp-md-min) from _mixins.scss"),
    "raw-z-index": (RAW_Z, "*.scss", "use var(--z-*) from _css-variables.scss"),
    "important": (IMPORTANT, "*.scss", "specificity by structure, not !important"),
}
TSX_RULES = {
    "inline-style": (INLINE_STYLE, "*.tsx", "move the rule into the component's SCSS with tokens"),
}
#: Never grandfathered: a debug leftover is not debt, it is unfinished work.
HARD_RULES = {"debug-leftover": (DEBUG, ("*.ts", "*.tsx"), "remove before shipping")}


def _files(pattern: str):
    suffix = pattern.replace("*", "")          # "*.scss" → ".scss"
    for path in sorted(SRC.rglob(f"*{suffix}")):
        if not path.is_file():
            continue
        if "node_modules" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if re.search(r"\.(test|spec)\.", rel):
            continue
        yield path, rel


def scan() -> dict[str, dict[str, list[str]]]:
    """`{file: {rule: ["src/x.scss:12 — line text"]}}` for every rule, every hit."""
    hits: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for rule, (pattern, glob, _hint) in SCSS_RULES.items():
        for path, rel in _files(glob):
            if rel in TOKEN_FILES:
                continue
            if rule == "important" and rel in IMPORTANT_ALLOWED:
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.search(line):
                    hits[rel][rule].append(f"{rel}:{number} {line.strip()}")
    for rule, (pattern, glob, _hint) in TSX_RULES.items():
        for path, rel in _files(glob):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if pattern.search(line):
                    hits[rel][rule].append(f"{rel}:{number} {line.strip()[:120]}")
    return hits


def counts(hits) -> dict[str, dict[str, int]]:
    return {rel: {rule: len(lines) for rule, lines in rules.items()} for rel, rules in hits.items()}


def hard_failures() -> list[str]:
    failures = []
    for rule, (pattern, globs, hint) in HARD_RULES.items():
        for glob in globs:
            for path, rel in _files(glob):
                for number, line in enumerate(path.read_text().splitlines(), start=1):
                    if pattern.search(line):
                        failures.append(f"{rule}: {rel}:{number} — {hint}: {line.strip()[:100]}")
    return failures


def load_baseline() -> dict[str, dict[str, int]]:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text()).get("files", {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print every hit, ignoring the baseline")
    parser.add_argument("--update-baseline", action="store_true", help="freeze the current tree")
    args = parser.parse_args()

    hits = scan()
    current = counts(hits)

    if args.list:
        for rel in sorted(hits):
            for rule in sorted(hits[rel]):
                for line in hits[rel][rule]:
                    print(f"{rule:14} {line}")
        return 0

    if args.update_baseline:
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Frozen design-system debt. The check only ratchets down: fix a line and "
                        "re-run with --update-baseline to lower it; never add."
                    ),
                    "files": {rel: dict(sorted(rules.items())) for rel, rules in sorted(current.items())},
                },
                indent=1,
                sort_keys=False,
            )
            + "\n"
        )
        total = sum(sum(rules.values()) for rules in current.values())
        print(f"styles-baseline.json updated: {total} hit(s) across {len(current)} file(s)")
        return 0

    baseline = load_baseline()
    failures: list[str] = []
    for rel in sorted(current):
        for rule, count in sorted(current[rel].items()):
            allowed = baseline.get(rel, {}).get(rule, 0)
            if count > allowed:
                hint = SCSS_RULES.get(rule) or TSX_RULES.get(rule)
                message = hint[2] if hint else ""
                failures.append(
                    f"{rel}: {rule} {count} > {allowed} — {message}"
                )
    failures.extend(hard_failures())

    if failures:
        for failure in failures:
            print(f"check-styles: {failure}", file=sys.stderr)
        print(
            "check-styles: fix the line, or (for old code only) freeze it with "
            "`npm run check:styles -- --update-baseline`",
            file=sys.stderr,
        )
        return 1

    stale = [
        f"{rel}: {rule} {allowed} → {current.get(rel, {}).get(rule, 0)}"
        for rel, rules in baseline.items()
        for rule, allowed in rules.items()
        if current.get(rel, {}).get(rule, 0) < allowed
    ]
    if stale:
        print(
            f"check-styles: {len(stale)} baseline entr(y/ies) are now lower than frozen — "
            "run `npm run check:styles -- --update-baseline` to tighten it",
            file=sys.stderr,
        )
    print("check-styles: OK (no new design-system violations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
