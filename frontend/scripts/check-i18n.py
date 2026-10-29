#!/usr/bin/env python3
"""i18n guardrail — `npm run check:i18n`.

A missing translation key does not crash: i18next prints the key itself, so the UI silently shows
`portfolio.poolColRank`. A key present in English and missing in Chinese is the same bug with fewer
symptoms. Neither shows up in a typecheck.

Both resources live in `src/i18n/config.ts`; this reads them by indentation (they are hand-written
object literals with a consistent shape) and compares:

1. every literal `t('…')` key in `src/` exists in **both** languages;
2. the two languages have the **same key set** (no key that exists only in one).

Dynamic keys (`` t(`factor.direction.${dir}`) ``) are skipped on purpose: their value is not knowable
without running the app. Keys that interpolate are checked as a prefix — every key under
`factor.direction.` must exist.

    npm run check:i18n            # report and exit non-zero on a problem
    npm run check:i18n -- --list  # also print the keys it compared
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "src" / "i18n" / "config.ts"
SRC = ROOT / "src"

T_CALL = re.compile(r"\bt\(\s*'([^']+)'")
T_TEMPLATE = re.compile(r"\bt\(\s*`([^`]*)\$\{")

LOCALES = ROOT / "src" / "i18n" / "locales"


def _flatten(node: object, prefix: str = "") -> set[str]:
    """Dotted keys from a nested locale object."""
    keys: set[str] = set()
    if isinstance(node, dict):
        for name, value in node.items():
            dotted = f"{prefix}.{name}" if prefix else name
            if isinstance(value, dict):
                keys |= _flatten(value, dotted)
            else:
                keys.add(dotted)
    return keys


def resource_keys() -> dict[str, set[str]]:
    """`{'en': {...}, 'zh': {...}}` — the two JSON resources the app loads."""
    return {
        "en": _flatten(json.loads((LOCALES / "en.json").read_text())),
        "zh": _flatten(json.loads((LOCALES / "zh-CN.json").read_text())),
    }


def used_keys() -> tuple[set[str], set[str]]:
    """Literal keys, and prefixes from template keys (`factor.direction.${x}` → `factor.direction.`)."""
    literal: set[str] = set()
    prefixes: set[str] = set()
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in (".ts", ".tsx") or "i18n" in path.parts:
            continue
        if re.search(r"\.(test|spec)\.", path.name):
            continue
        text = path.read_text()
        literal.update(T_CALL.findall(text))
        for template in T_TEMPLATE.findall(text):
            prefixes.add(template.rstrip("."))
    return literal, prefixes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print the key counts and compared keys")
    args = parser.parse_args()

    languages = resource_keys()
    if set(languages) != {"en", "zh"}:
        print(f"check-i18n: could not read both resources (found {sorted(languages)})", file=sys.stderr)
        return 1

    literal, prefixes = used_keys()
    problems: list[str] = []

    for language, keys in languages.items():
        for key in sorted(literal):
            if key not in keys:
                problems.append(f"missing in {language}: '{key}'")
        for prefix in sorted(prefixes):
            if not any(key.startswith(prefix + ".") for key in keys):
                problems.append(f"missing in {language}: no key under '{prefix}.'")

    only_en = languages["en"] - languages["zh"]
    only_zh = languages["zh"] - languages["en"]
    for key in sorted(only_en):
        problems.append(f"defined in en only: '{key}'")
    for key in sorted(only_zh):
        problems.append(f"defined in zh only: '{key}'")

    if args.list:
        print(f"en {len(languages['en'])} keys · zh {len(languages['zh'])} keys · used {len(literal)}")

    for problem in problems:
        print(f"check-i18n: {problem}", file=sys.stderr)

    if problems:
        print(
            f"check-i18n: {len(problems)} problem(s) — a missing key renders as the key itself",
            file=sys.stderr,
        )
        return 1

    print("check-i18n: OK (every used key exists in both languages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
