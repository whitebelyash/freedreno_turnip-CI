#!/usr/bin/env python3
"""
Filter out freedreno_devices.py hunks from tu8_kgsl.patch.

These hunks fail to apply on newer Mesa because the file was restructured
upstream. The changes are applied separately by fix_devices.py instead.

Usage: filter_patch.py <input.patch> <output.patch>
"""

import re
import sys


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.patch> <output.patch>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        content = f.read()

    # Split into individual commits
    commits = re.split(r'(?=^From [0-9a-f]{40})', content, flags=re.MULTILINE)
    commits = [c for c in commits if c.strip()]

    out = []
    for commit in commits:
        files = re.findall(r'diff --git a/(\S+)', commit)

        # Skip commits that ONLY touch freedreno_devices.py
        if files and all('freedreno_devices.py' in f for f in files):
            subj = re.search(r'Subject: (.+?)(?:\n[^ ]|\n\n)', commit, re.DOTALL)
            name = subj.group(1).strip() if subj else "?"
            print(f"  SKIP (devices.py only): {name}")
            continue

        # Strip freedreno_devices.py hunks from mixed commits
        if any('freedreno_devices.py' in f for f in files):
            subj = re.search(r'Subject: (.+?)(?:\n[^ ]|\n\n)', commit, re.DOTALL)
            name = subj.group(1).strip() if subj else "?"
            print(f"  FILTER devices.py hunks: {name}")
            commit = re.sub(
                r'diff --git a/src/freedreno/common/freedreno_devices\.py.*?(?=diff --git|\Z)',
                '', commit, flags=re.DOTALL
            )

        out.append(commit)

    with open(sys.argv[2], 'w') as f:
        f.write(''.join(out))

    print(f"Wrote {sys.argv[2]} ({len(out)} commits kept, {len(commits) - len(out)} skipped)")


if __name__ == "__main__":
    main()
