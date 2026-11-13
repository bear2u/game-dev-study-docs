#!/usr/bin/env python3
"""Sync translated lecture Markdown files into Nimbus docs/src/content/docs/."""

import re
from pathlib import Path

BASE_DIR = Path.cwd()
SRC_DIR = BASE_DIR / "lectures" / "A_일의_자세"
DEST_DIR = BASE_DIR / "docs" / "src" / "content" / "docs" / "lectures" / "a-work-attitude"

KO_TITLES = {
    1: "놀이를 만드는 일은 놀이가 아니다",
    2: "프레젠테이션은 스피디하게",
    3: "고객에게 설명할 수 있는가?",
    4: "사양 변경 대처법",
    5: "기획서 작성법",
    6: "기획서는 단숨에 힘차게",
    7: "고생은 잊히고 작품은 남는다",
    8: "디렉터는 곧 개성이다",
    9: "어쨌든 당장 해라!!",
    10: "칼럼을 계속 쓸 수 있었던 이유",
    11: "플랜 B에 기대지 마라",
    12: "가치관의 줄기와 가지",
    13: "인풋이 강해야 아웃풋도 강하다",
    14: "내압을 높여라",
    15: "의미 없는 다수결",
    16: "암시의 힘",
    17: "콘셉트는 꺾지 않는 것",
    18: "경쟁과 풍요",
    19: "말한 것은 그대로 실현된다",
}


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
        ko_title = KO_TITLES.get(idx, short_title)
        desc = extract_first_summary(body).replace('"', '\\"')
        safe_title = f"{idx:02d}. {ko_title}".replace('"', '\\"')

        # Remove duplicate H1 in body if it matches, since Nimbus renders title as H1
        body_lines = body.lstrip().splitlines()
        if body_lines and body_lines[0].startswith("# "):
            body = "\n".join(body_lines[1:]).lstrip()

        video_url = meta.get("url", "")
        if video_url:
            # Make plain URL in metadata table clickable
            body = body.replace(f"| URL | {video_url} |", f"| URL | [{video_url}]({video_url}) |")
            top_banner = f"> 📺 **YouTube 원본 영상:** [{video_url}]({video_url})\n\n"
        else:
            top_banner = ""

        nimbus_md = f"""---
title: "{safe_title}"
description: "{desc}"
sidebar:
  order: {idx}
---

{top_banner}{body}
"""
        out_path = DEST_DIR / f"{idx:02d}.md"
        out_path.write_text(nimbus_md, encoding="utf-8")
        synced += 1

    print(f"Synced {synced} translated lectures to {DEST_DIR}")


if __name__ == "__main__":
    main()
