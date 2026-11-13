#!/usr/bin/env python3
"""Sync translated lecture Markdown files into Nimbus docs/src/content/docs/."""

import re
from pathlib import Path

BASE_DIR = Path.cwd()
SRC_DIR = BASE_DIR / "lectures" / "A_일의_자세"
DEST_DIR = BASE_DIR / "docs" / "src" / "content" / "docs" / "lectures" / "a-work-attitude"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw_fm = text[4:end]
    body = text[end + 5:]
    meta = {}
    for line in raw_fm.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, body


def extract_first_summary(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- ") or s.startswith("* "):
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", s[2:].strip())
            return clean[:120]
    return "사쿠라이 마사히로의 게임 만드는 법 강의 번역 및 핵심 정리"


def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC_DIR.glob("[0-9][0-9]_*.md"))
    synced = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        if meta.get("translated") != "true":
            continue
        idx = int(meta.get("index", "0") or "0")
        title = meta.get("title", f.stem)
        short_title = re.sub(r"\s*[\[【].*?[\]】]\s*$", "", title).strip()
        desc = extract_first_summary(body).replace('"', '\\"')
        safe_title = f"{idx:02d}. {short_title}".replace('"', '\\"')

        # Remove duplicate H1 in body if it matches, since Nimbus renders title as H1
        body_lines = body.lstrip().splitlines()
        if body_lines and body_lines[0].startswith("# "):
            body = "\n".join(body_lines[1:]).lstrip()

        nimbus_md = f"""---
title: "{safe_title}"
description: "{desc}"
sidebar:
  order: {idx}
---

{body}
"""
        out_path = DEST_DIR / f"{idx:02d}.md"
        out_path.write_text(nimbus_md, encoding="utf-8")
        synced += 1

    print(f"Synced {synced} translated lectures to {DEST_DIR}")


if __name__ == "__main__":
    main()
