from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "shorts-data.json"
INDEX_PATH = ROOT / "index.html"

KST = timezone(timedelta(hours=9))

SOURCES = [
    {
        "name": "Vidirun Top 50 Short-Form Videos",
        "window": "24H",
        "page": "https://vidirun.com/format-short",
        "json": "https://raw.githubusercontent.com/wpbosch/vidirun_json/main/vidirun_video_Top50_Short_24H.json",
    },
    {
        "name": "Vidirun Top 50 Short-Form Videos",
        "window": "7D",
        "page": "https://vidirun.com/format-short",
        "json": "https://raw.githubusercontent.com/wpbosch/vidirun_json/main/vidirun_video_Top50_Short_7D.json",
    },
]

YT_SEARCH_QUERIES = [
    "ytsearch20:#shorts dance challenge music trend",
    "ytsearch20:#shorts slowed dance edit",
    "ytsearch20:#shorts cute dance one person music",
    "ytsearch20:#shorts couple dance music",
    "ytsearch20:#shorts funny situation music edit",
]

CORE_TERMS = {
    "dance",
    "dancing",
    "dancer",
    "battle",
    "backstage",
    "moonwalk",
    "michael jackson",
    "jumpstyle",
    "challenge",
    "performance",
    "stunt",
    "surprise",
    "situation",
    "prank",
    "magic",
    "cute",
    "saved",
    "happened",
    "couldn",
    "defying",
}

SUPPORT_TERMS = {
    "slowed",
    "funk",
    "phonk",
    "edit",
    "trend",
    "trending",
    "music",
    "beat",
}

EXCLUDE_TERMS = {
    "lyrics",
    "lyric",
    "caption",
    "subtitles",
    "tutorial",
    "how to",
    "mashup",
    "compilation",
    "ranking",
    "rank ",
    "news",
    "podcast",
    "full movie",
    "audio",
    "song only",
    "shopping",
    "haul",
    "animal",
    "animals",
    "gameplay",
}

PREFERRED_CATEGORIES = {
    "Comedy",
    "Entertainment",
    "People & Blogs",
    "Music",
    "Sports",
    "Howto & Style",
}


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 ycodex-shorts-updater/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def read_data() -> list[dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def write_data(items: list[dict[str, Any]]) -> None:
    DATA_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def video_id_from_thumbnail(url: str) -> str | None:
    match = re.search(r"/vi/([^/]+)/", url or "")
    return match.group(1) if match else None


def normalized_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def term_hits(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if term in lower)


def score_candidate(title: str, category: str = "") -> tuple[int, list[str]]:
    text = f"{title} {category}".lower()
    core_hits = term_hits(text, CORE_TERMS)
    support_hits = term_hits(text, SUPPORT_TERMS)
    exclude_hits = term_hits(text, EXCLUDE_TERMS)
    score = len(core_hits) * 3 + len(support_hits)
    if not core_hits:
        score -= 3
    if category in PREFERRED_CATEGORIES:
        score += 1
    if "#shorts" in text or "shorts" in text:
        score += 1
    score -= len(exclude_hits) * 3

    notes = []
    if core_hits:
        notes.append("core keyword: " + ", ".join(core_hits[:4]))
    if support_hits:
        notes.append("music/trend signal: " + ", ".join(support_hits[:3]))
    if category in PREFERRED_CATEGORIES:
        notes.append("preferred category")
    if "#shorts" in text or "shorts" in text:
        notes.append("shorts text signal")
    if exclude_hits:
        notes.append("excluded signal: " + ", ".join(exclude_hits[:3]))
    notes.append("manual visual/audio check recommended")
    return score, notes


def from_vidirun_item(raw: dict[str, Any], source: dict[str, str], collected_at: str) -> dict[str, Any] | None:
    video_id = video_id_from_thumbnail(raw.get("Thumbnail", ""))
    if not video_id:
        return None
    title = str(raw.get("Title", "")).strip()
    category = str(raw.get("Category", "")).strip()
    score, notes = score_candidate(title, category)
    if score < 4:
        return None
    return {
        "id": video_id,
        "title": title,
        "channel": str(raw.get("Channel", "")).strip(),
        "category": category,
        "shortsUrl": normalized_url(video_id),
        "thumbnail": thumbnail_url(video_id),
        "viewsGained": int(raw.get("Views Gained") or 0),
        "sourceRank": int(raw.get("Rank") or 0),
        "sourceWindow": source["window"],
        "sourceName": source["name"],
        "sourceUrl": source["page"],
        "collectedAt": collected_at,
        "matchNotes": notes,
    }


def collect_vidirun(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in SOURCES:
        try:
            rows = fetch_json(source["json"])
        except Exception as exc:
            print(f"warning: failed to fetch {source['json']}: {exc}", file=sys.stderr)
            continue
        for raw in rows:
            item = from_vidirun_item(raw, source, collected_at)
            if item:
                candidates.append(item)
    return candidates


def run_yt_search(query: str) -> list[dict[str, Any]]:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--dump-single-json",
        "--flat-playlist",
        query,
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=90, check=False)
    except Exception as exc:
        print(f"warning: yt-dlp search failed for {query}: {exc}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        return []
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return payload.get("entries") or []


def from_ytdlp_item(raw: dict[str, Any], query: str, collected_at: str) -> dict[str, Any] | None:
    video_id = raw.get("id")
    duration = raw.get("duration")
    if not video_id:
        return None
    if isinstance(duration, (int, float)) and duration > 180:
        return None
    title = str(raw.get("title", "")).strip()
    score, notes = score_candidate(title, "")
    if score < 4:
        return None
    return {
        "id": video_id,
        "title": title,
        "channel": str(raw.get("channel") or raw.get("uploader") or "").strip(),
        "category": "YouTube Search",
        "shortsUrl": normalized_url(video_id),
        "thumbnail": thumbnail_url(video_id),
        "viewsGained": int(raw.get("view_count") or 0),
        "sourceRank": 0,
        "sourceWindow": "search",
        "sourceName": "YouTube Shorts search via yt-dlp",
        "sourceUrl": f"https://www.youtube.com/results?search_query={quote_plus(query.replace('ytsearch20:', ''))}",
        "collectedAt": collected_at,
        "matchNotes": notes,
    }


def collect_youtube_search(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for query in YT_SEARCH_QUERIES:
        for raw in run_yt_search(query):
            item = from_ytdlp_item(raw, query, collected_at)
            if item:
                candidates.append(item)
    return candidates


def merge_items(existing: list[dict[str, Any]], new_items: list[dict[str, Any]], max_new: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    old_by_id = {item.get("id"): item for item in existing if item.get("id")}
    ranked = sorted(
        new_items,
        key=lambda item: (
            item.get("sourceWindow") != "24H",
            -(item.get("viewsGained") or 0),
            item.get("sourceRank") or 9999,
        ),
    )
    fresh: list[dict[str, Any]] = []
    for item in ranked:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        if video_id in old_by_id:
            old = old_by_id[video_id]
            old.update(
                {
                    "title": item.get("title") or old.get("title"),
                    "channel": item.get("channel") or old.get("channel"),
                    "category": item.get("category") or old.get("category"),
                    "viewsGained": item.get("viewsGained") or old.get("viewsGained"),
                    "sourceRank": item.get("sourceRank") or old.get("sourceRank"),
                    "sourceWindow": item.get("sourceWindow") or old.get("sourceWindow"),
                    "sourceName": item.get("sourceName") or old.get("sourceName"),
                    "sourceUrl": item.get("sourceUrl") or old.get("sourceUrl"),
                    "collectedAt": item.get("collectedAt") or old.get("collectedAt"),
                    "matchNotes": item.get("matchNotes") or old.get("matchNotes"),
                }
            )
            fresh.append(old)
        else:
            fresh.append(item)
        if len(fresh) >= max_new:
            break

    fresh_ids = {item.get("id") for item in fresh}
    tail = [item for item in existing if item.get("id") not in fresh_ids]
    return fresh + tail


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def source_links(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs = {
        (item.get("sourceName") or "Source", item.get("sourceUrl") or "#")
        for item in items
    }
    pairs.add(("TrendsFox Trending Videos", "https://www.trendsfox.com/trending-videos"))
    pairs.add(("Apify YouTube Most Popular Shorts actor notes", "https://apify.com/coregent/youtube-most-popular-shorts"))
    return sorted(pairs)


def render_index(items: list[dict[str, Any]]) -> str:
    latest = items[0].get("collectedAt", "") if items else ""
    cards = []
    for index, item in enumerate(items, start=1):
        notes = "".join(f"<li>{escape(str(note))}</li>" for note in item.get("matchNotes", []))
        cards.append(
            f"""
      <article class="short-card">
        <a class="thumb-link" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">
          <img src="{escape(item['thumbnail'])}" alt="{escape(item['title'])} thumbnail" loading="lazy">
          <span class="rank">#{index}</span>
        </a>
        <div class="short-body">
          <div class="meta-row">
            <span>{escape(str(item.get('sourceWindow', 'trend')))}</span>
            <span>{fmt_int(item.get('viewsGained'))} views gained</span>
          </div>
          <h2><a href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">{escape(item['title'])}</a></h2>
          <p class="channel">{escape(str(item.get('channel') or 'Unknown channel'))}</p>
          <p class="source">Source: <a href="{escape(str(item.get('sourceUrl') or '#'))}" target="_blank" rel="noopener">{escape(str(item.get('sourceName') or 'source'))}</a>{' · rank ' + str(item.get('sourceRank')) if item.get('sourceRank') else ''}</p>
          <ul class="notes">{notes}</ul>
        </div>
      </article>"""
        )

    links = "\n".join(
        f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(name)}</a>'
        for name, url in source_links(items)
    )

    data_json = escape(json.dumps(items, ensure_ascii=False), quote=False)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YouTube Shorts Trend Watch</title>
  <meta name="description" content="음악 중심, 자막 없는 1~2인 댄스/상황형 인기 YouTube Shorts 후보 모음">
  <style>
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #667085;
      --line: #d9e2ec;
      --surface: #ffffff;
      --wash: #f4f7fb;
      --accent: #0d9488;
      --accent-2: #c2410c;
      --focus: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Pretendard, "Noto Sans KR", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--wash);
      color: var(--ink);
      letter-spacing: 0;
    }}
    a {{ color: inherit; }}
    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: #f9fbfd;
    }}
    .topbar {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 20px;
      padding: 28px 0 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 3vw, 40px);
      line-height: 1.15;
      font-weight: 800;
    }}
    .lead {{
      margin: 0;
      max-width: 720px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.65;
    }}
    .status {{
      min-width: 220px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 12px;
      font-size: 13px;
      color: var(--muted);
    }}
    .status strong {{
      display: block;
      color: var(--ink);
      font-size: 16px;
      margin-top: 4px;
    }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 16px 0 18px;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      padding: 8px 11px;
      font-size: 13px;
      color: #475467;
    }}
    main {{
      padding: 24px 0 44px;
    }}
    .notice {{
      border-left: 4px solid var(--accent);
      background: var(--surface);
      padding: 14px 16px;
      border-radius: 8px;
      margin-bottom: 18px;
      color: #344054;
      font-size: 14px;
      line-height: 1.65;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }}
    .short-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      min-height: 100%;
    }}
    .thumb-link {{
      position: relative;
      display: block;
      aspect-ratio: 9 / 16;
      background: #dbe4ee;
      overflow: hidden;
    }}
    .thumb-link img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .rank {{
      position: absolute;
      top: 8px;
      left: 8px;
      background: rgba(24, 33, 47, 0.86);
      color: white;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      font-weight: 700;
    }}
    .short-body {{
      padding: 13px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .meta-row {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--accent-2);
      font-size: 12px;
      font-weight: 700;
    }}
    .short-card h2 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.35;
    }}
    .short-card h2 a {{
      text-decoration: none;
    }}
    .short-card h2 a:hover {{
      text-decoration: underline;
    }}
    .channel,
    .source {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .source a {{
      color: var(--focus);
      text-decoration: none;
    }}
    .notes {{
      margin: 2px 0 0;
      padding-left: 18px;
      color: #475467;
      font-size: 12px;
      line-height: 1.45;
    }}
    .source-panel {{
      margin-top: 26px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .source-panel a {{
      color: var(--focus);
      text-decoration: none;
      border-bottom: 1px solid rgba(29, 78, 216, 0.25);
    }}
    footer {{
      border-top: 1px solid var(--line);
      padding: 20px 0 32px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 720px) {{
      .topbar {{ align-items: stretch; flex-direction: column; }}
      .status {{ min-width: 0; }}
      .grid {{ grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="shell">
      <div class="topbar">
        <div>
          <h1>YouTube Shorts Trend Watch</h1>
          <p class="lead">음악 중심 배경, 자막 없음, 1~2명 등장, 댄스 또는 짧은 상황형으로 보이는 인기 YouTube Shorts 후보를 위에서부터 최신순으로 누적합니다.</p>
        </div>
        <div class="status">
          Last update
          <strong>{escape(latest or "not yet")}</strong>
        </div>
      </div>
      <div class="filters" aria-label="collection rules">
        <span class="chip">music-first</span>
        <span class="chip">no visible captions target</span>
        <span class="chip">1-2 people target</span>
        <span class="chip">dance or situation</span>
        <span class="chip">new items stay on top</span>
      </div>
    </div>
  </header>
  <main class="shell">
    <div class="notice">공개 랭킹 데이터는 영상 안의 실제 자막, 대사 유무, 인물 수를 직접 제공하지 않습니다. 이 페이지는 제목, 카테고리, 썸네일, 트렌드 순위를 기준으로 후보를 자동 수집하고, 최종 조건 확인이 필요한 항목에는 검수 메모를 남깁니다.</div>
    <section class="grid" aria-label="trending shorts">
{''.join(cards)}
    </section>
    <section class="source-panel" aria-label="sources">
      <span>Sources used:</span>
      {links}
    </section>
  </main>
  <footer>
    <div class="shell">Daily schedule target: 17:00 Asia/Seoul. Data is preserved by prepending new matches and keeping older links below.</div>
  </footer>
  <script type="application/json" id="shorts-data">{data_json}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true", help="Render index.html from existing shorts-data.json")
    parser.add_argument("--max-new", type=int, default=int(os.environ.get("MAX_NEW_SHORTS", "10")))
    args = parser.parse_args()

    existing = read_data()
    if args.render_only:
        merged = existing
    else:
        collected_at = datetime.now(KST).replace(microsecond=0).isoformat()
        candidates = collect_vidirun(collected_at)
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            print("warning: yt-dlp is not installed; skipping YouTube search queries", file=sys.stderr)
        else:
            candidates.extend(collect_youtube_search(collected_at))
        merged = merge_items(existing, candidates, args.max_new)
        write_data(merged)

    INDEX_PATH.write_text(render_index(merged), encoding="utf-8")
    print(f"rendered {INDEX_PATH} with {len(merged)} shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
