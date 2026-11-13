#!/usr/bin/env python3
"""Fetch all lectures from Masahiro Sakurai's YouTube channel (@sora_sakurai_jp),
translate transcripts to Korean, and organize them by category into Markdown files.

Supports:
- Polite randomized delays between requests to avoid YouTube rate limiting
- Resume / skip already-downloaded videos
- Preserving original Japanese transcript inside a collapsible <details> block
- Writing a manifest.json for progress tracking and index generation
"""

import argparse
import json
import random
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import IpBlocked, RequestBlocked

# Ordered category playlists from @sora_sakurai_jp
CATEGORY_PLAYLISTS = [
    ("A_일의_자세", "A. 일의 자세 (仕事の姿勢)", "PLi8SA3sbzYVSSlN3Ekb1nEpxnFuVzGz3_"),
    ("B_게임성", "B. 게임성 (ゲーム性)", "PLi8SA3sbzYVSFrVkTeXP_NCuUcirSDddm"),
    ("C_기획_게임설계", "C. 기획·게임 설계 (企画・ゲーム設計)", "PLi8SA3sbzYVRzUK6Wqd_g6ZGjDpIWZdim"),
    ("D_사양", "D. 사양 (仕様)", "PLi8SA3sbzYVSQmkQUa-zz7BcKL8YWAt8a"),
    ("E_팀_운영", "E. 팀 운영 (チーム運営)", "PLi8SA3sbzYVTsJ4O5sKk_-2uAHJjIJk2p"),
    ("F_그래픽", "F. 그래픽 (グラフィック)", "PLi8SA3sbzYVSv8__vPS9dhQYCzVg5Ez9f"),
    ("G_모션", "G. 모션 (モーション)", "PLi8SA3sbzYVTwi9CkssHtstuocOXuPvK3"),
    ("H_이펙트", "H. 이펙트 (エフェクト)", "PLi8SA3sbzYVROBDht_21q0DaJb8AlASdI"),
    ("I_사운드", "I. 사운드 (サウンド)", "PLi8SA3sbzYVQryiiSEl0L5H2omvrhKyF5"),
    ("J_UI", "J. UI", "PLi8SA3sbzYVTl4FV0rLnSsf6ElOh-_Cv1"),
    ("K_프로그램_테크니컬", "K. 프로그램·테크니컬 (プログラム・テクニカル)", "PLi8SA3sbzYVQ1BwwoVauT0-4S4xsHGopj"),
    ("L_홍보", "L. 홍보 (広報)", "PLi8SA3sbzYVRuEkXSbiqoZMd4GkLBCll_"),
    ("M_잡담", "M. 잡담 (雑談)", "PLi8SA3sbzYVQU0vD0T9pv5g6U-bbWS-Og"),
    ("N_기획_콘셉트", "N. 기획 콘셉트 (企画コンセプト)", "PLi8SA3sbzYVRKPT3PMcU1VGkFZU5No9KZ"),
    ("S_스페셜", "S. 스페셜 (スペシャル)", "PLi8SA3sbzYVSYL5r-ys6u0BbqUWTmhj8H"),
    ("Z_공지_및_요약", "공지 및 요약 (お知らせ・まとめ)", "PLi8SA3sbzYVQHxNJdF-TSJ75Xl0X7ep4t"),
]

CHANNEL_NAME = "桜井政博のゲーム作るには"
BASE_DIR = Path.cwd()
LECTURES_DIR = BASE_DIR / "lectures"
MANIFEST_PATH = BASE_DIR / "manifest.json"


def safe_filename(text: str, max_len: int = 60) -> str:
    """Create a filesystem-safe filename preserving Japanese/Korean/ASCII characters."""
    text = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len].strip(" ._")


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "알 수 없음"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_playlist_entries(playlist_id: str) -> list[dict]:
    """Fetch video entries from a YouTube playlist using yt-dlp flat-playlist."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(f"yt-dlp failed for {playlist_id}: {res.stderr.strip()}")
    data = json.loads(res.stdout)
    entries = []
    for idx, entry in enumerate(data.get("entries") or [], start=1):
        vid = entry.get("id")
        if not vid:
            continue
        entries.append({
            "index": idx,
            "video_id": vid,
            "title": entry.get("title") or "Untitled",
            "duration": entry.get("duration") or 0,
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    return entries


def find_existing_file(video_id: str) -> Path | None:
    if not LECTURES_DIR.exists():
        return None
    matches = list(LECTURES_DIR.rglob(f"*_\\[{video_id}\\].md"))
    return matches[0] if matches else None


def snippets_to_paragraphs(snippets, with_timestamps: bool = True) -> str:
    """Group transcript snippets into readable paragraphs."""
    lines = []
    buf = []
    para_start = None
    for s in snippets:
        text = s.text.replace("\n", " ").strip()
        if not text:
            continue
        if para_start is None:
            para_start = s.start
        buf.append(text)
        # Break paragraph every ~6 snippets or on sentence-ending punctuation
        if len(buf) >= 6 or (len(buf) >= 3 and text.endswith((".", "。", "!", "?", "다.", "요.", "까?"))):
            prefix = f"**[{format_timestamp(para_start)}]** " if with_timestamps else ""
            lines.append(f"{prefix}{' '.join(buf)}")
            buf = []
            para_start = None
    if buf:
        prefix = f"**[{format_timestamp(para_start or 0)}]** " if with_timestamps else ""
        lines.append(f"{prefix}{' '.join(buf)}")
    return "\n\n".join(lines)


def fetch_transcript_ko_and_ja(api: YouTubeTranscriptApi, video_id: str) -> tuple[str, str, str]:
    """Return (ko_text, ja_text, caption_type).

    If native Korean captions exist, returns both/Korean.
    Otherwise fetches original Japanese (or first available) captions without
    forcing YouTube auto-translation when YouTube blocks or omits 'ko'.
    """
    tlist = api.list(video_id)
    available = list(tlist)

    ko_transcript = None
    ja_transcript = None

    for t in available:
        if t.language_code == "ko" or t.language_code.startswith("ko-"):
            if ko_transcript is None or not t.is_generated:
                ko_transcript = t
        if t.language_code == "ja" or t.language_code.startswith("ja-"):
            if ja_transcript is None or not t.is_generated:
                ja_transcript = t

    caption_type = "unknown"
    ja_text = ""
    ko_text = ""

    if ja_transcript is not None:
        ja_snips = ja_transcript.fetch()
        ja_text = snippets_to_paragraphs(ja_snips, with_timestamps=True)
        caption_type = f"ja-{'auto' if ja_transcript.is_generated else 'manual'}"

    if ko_transcript is not None:
        ko_snips = ko_transcript.fetch()
        ko_text = snippets_to_paragraphs(ko_snips, with_timestamps=True)
        caption_type = f"ko-{'auto' if ko_transcript.is_generated else 'manual'}"
    elif ja_transcript is not None:
        # Try YouTube translation only if 'ko' is explicitly listed in translation_languages
        can_ko = any(
            getattr(tl, "language_code", "") == "ko"
            for tl in getattr(ja_transcript, "translation_languages", [])
        )
        if can_ko:
            try:
                ko_snips = ja_transcript.translate("ko").fetch()
                ko_text = snippets_to_paragraphs(ko_snips, with_timestamps=True)
                caption_type = f"ja({'auto' if ja_transcript.is_generated else 'manual'})->ko"
            except Exception:
                pass
    elif available:
        base = available[0]
        snips = base.fetch()
        ja_text = snippets_to_paragraphs(snips, with_timestamps=True)
        caption_type = f"{base.language_code}-{'auto' if base.is_generated else 'manual'}"
    else:
        raise RuntimeError("No transcripts available")

    return ko_text, ja_text, caption_type


def yaml_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_markdown(
    cat_label: str,
    entry: dict,
    ko_text: str,
    ja_text: str,
    caption_type: str,
) -> str:
    vid = entry["video_id"]
    title = entry["title"]
    duration_str = format_duration(entry.get("duration"))
    today = date.today().isoformat()

    if ko_text:
        body = f"""## 🇰🇷 한국어 자막

{ko_text}"""
        if ja_text:
            body += f"""

---

<details>
<summary>🇯🇵 일본어 원문 자막 펼치기</summary>

{ja_text}

</details>"""
    else:
        body = f"""## 🇰🇷 한국어 번역 및 핵심 정리

> _원문 자막을 바탕으로 한국어 번역·정리 대기 중_

## 🇯🇵 일본어 원문 자막

{ja_text}"""

    return f"""---
title: "{yaml_escape(title)}"
category: "{yaml_escape(cat_label)}"
index: {entry['index']}
channel: "{yaml_escape(CHANNEL_NAME)}"
url: "{entry['url']}"
video_id: "{vid}"
duration: "{duration_str}"
caption_type: "{caption_type}"
translated: {"true" if ko_text else "false"}
fetched: "{today}"
tags:
  - sakurai-game-dev
  - yt-transcript
---

# {entry['index']:02d}. {title}

| 항목 | 내용 |
|------|------|
| 카테고리 | {cat_label} |
| URL | {entry['url']} |
| 재생 시간 | {duration_str} |
| 자막 유형 | `{caption_type}` |
| 수집일 | {today} |

{body}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-delay", type=float, default=2.5, help="Minimum delay between requests (sec)")
    parser.add_argument("--max-delay", type=float, default=4.5, help="Maximum delay between requests (sec)")
    parser.add_argument("--only-category", type=str, default="", help="Only fetch category folder prefix (e.g. A_)")
    args = parser.parse_args()

    LECTURES_DIR.mkdir(parents=True, exist_ok=True)
    api = YouTubeTranscriptApi()

    manifest = {"updated": date.today().isoformat(), "categories": []}
    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    cat_map = {c["folder"]: c for c in manifest.get("categories", [])}

    total_fetched = 0
    total_skipped = 0
    total_failed = 0

    for folder, cat_label, plist_id in CATEGORY_PLAYLISTS:
        if args.only_category and not folder.startswith(args.only_category):
            continue

        print(f"\n=== [{cat_label}] 목록 조회 중... ===", flush=True)
        try:
            entries = get_playlist_entries(plist_id)
        except Exception as e:
            print(f"  [ERROR] 재생목록 조회 실패: {e}", flush=True)
            continue

        print(f"  -> {len(entries)}개 영상 확인", flush=True)
        cat_dir = LECTURES_DIR / folder
        cat_dir.mkdir(parents=True, exist_ok=True)

        cat_record = {
            "folder": folder,
            "label": cat_label,
            "playlist_id": plist_id,
            "videos": [],
        }

        for entry in entries:
            vid = entry["video_id"]
            existing = find_existing_file(vid)
            if existing is not None:
                total_skipped += 1
                cat_record["videos"].append({
                    **entry,
                    "status": "done",
                    "file": str(existing.relative_to(BASE_DIR)),
                })
                continue

            # Polite delay before each network request
            delay = random.uniform(args.min_delay, args.max_delay)
            time.sleep(delay)

            success = False
            last_err = ""
            ip_blocked = False
            for attempt in range(1, 3):
                try:
                    ko_text, ja_text, caption_type = fetch_transcript_ko_and_ja(api, vid)
                    md_content = build_markdown(cat_label, entry, ko_text, ja_text, caption_type)
                    fname = f"{entry['index']:02d}_{safe_filename(entry['title'])}_[{vid}].md"
                    out_path = cat_dir / fname
                    out_path.write_text(md_content, encoding="utf-8")
                    total_fetched += 1
                    print(f"  [OK] ({entry['index']:02d}/{len(entries)}) {entry['title']} -> {fname}", flush=True)
                    cat_record["videos"].append({
                        **entry,
                        "status": "done",
                        "file": str(out_path.relative_to(BASE_DIR)),
                    })
                    success = True
                    break
                except (IpBlocked, RequestBlocked) as e:
                    last_err = f"{type(e).__name__}: YouTube IP rate limit"
                    ip_blocked = True
                    break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)}"
                    if "429" in last_err or "blocking requests from your IP" in last_err:
                        ip_blocked = True
                        break
                    break

            if ip_blocked:
                print(f"  [STOP - IP BLOCKED] {entry['title']} ({vid}): 잠시 후 다시 실행하세요. (기존 파일은 자동 스킵됩니다)", flush=True)
                cat_map[folder] = cat_record
                manifest["updated"] = date.today().isoformat()
                manifest["categories"] = [cat_map[f] for f, _, _ in CATEGORY_PLAYLISTS if f in cat_map]
                MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                sys.exit(1)

            if not success:
                total_failed += 1
                print(f"  [FAIL] ({entry['index']:02d}/{len(entries)}) {entry['title']} ({vid}): {last_err[:120]}", flush=True)
                cat_record["videos"].append({
                    **entry,
                    "status": "failed",
                    "error": last_err[:200],
                })

        cat_map[folder] = cat_record
        manifest["updated"] = date.today().isoformat()
        manifest["categories"] = [cat_map[f] for f, _, _ in CATEGORY_PLAYLISTS if f in cat_map]
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"\n=== 완료: 새로 수집 {total_fetched}개 / 기존 스킵 {total_skipped}개 / 실패 {total_failed}개 ===",
        flush=True,
    )


if __name__ == "__main__":
    main()
