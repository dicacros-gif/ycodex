from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from html import escape, unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "shorts-data.json"
INDEX_PATH = ROOT / "index.html"

KST = timezone(timedelta(hours=9))

VIDIRUN_SOURCES = [
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

HTML_SOURCES = [
    {
        "name": "Playboard Most Viewed YouTube Shorts",
        "page": "https://playboard.co/en/chart/short/",
        "window": "daily",
    },
    {
        "name": "RedToolBox Top Shorts",
        "page": "https://www.redtoolbox.io/toplist/topShorts.jsp",
        "window": "daily",
    },
    {
        "name": "TrendsFox Trending Shorts",
        "page": "https://www.trendsfox.com/trending-videos",
        "window": "live",
    },
    {
        "name": "Top1Trend YouTube Trending",
        "page": "https://t1trend.com/",
        "window": "live",
    },
]

YT_SEARCH_QUERIES = [
    "ytsearch25:#shorts dance challenge music trend",
    "ytsearch25:#shorts slowed dance edit",
    "ytsearch25:#shorts cute dance one person music",
    "ytsearch25:#shorts couple dance music",
    "ytsearch25:#shorts funny situation music edit",
    "ytsearch25:#shorts dance challenge no talking",
    "ytsearch25:#shorts 댄스 음악 챌린지",
    "ytsearch25:#shorts KPOP dance music trend",
]

CORE_TERMS = {
    "dance",
    "댄스",
    "춤",
    "dancing",
    "dancer",
    "battle",
    "backstage",
    "moonwalk",
    "michael jackson",
    "jumpstyle",
    "challenge",
    "챌린지",
    "performance",
    "stunt",
    "surprise",
    "서프라이즈",
    "situation",
    "상황",
    "prank",
    "몰래카메라",
    "magic",
    "마술",
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


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 ycodex-shorts-updater/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


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


def video_id_from_any(value: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"/vi/([A-Za-z0-9_-]{11})/",
        r"/video/([A-Za-z0-9_-]{11})(?:\?|/|$)",
        r"/youtube/video_([A-Za-z0-9_-]{11})(?:\?|/|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, value or "")
        if match:
            return match.group(1)
    return None


def normalized_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def term_hits(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if term in lower)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value or "")
    match = re.search(r"-?[\d,]+", text)
    if not match:
        return 0
    return int(match.group(0).replace(",", ""))


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


def make_candidate(
    *,
    video_id: str,
    title: str,
    channel: str,
    category: str,
    views_gained: int,
    source_rank: int,
    source_window: str,
    source_name: str,
    source_url: str,
    collected_at: str,
    extra_notes: list[str] | None = None,
    min_score: int = 4,
) -> dict[str, Any] | None:
    title = clean_text(title)
    if not video_id or not title:
        return None
    score, notes = score_candidate(title, category)
    if score < min_score:
        return None
    if extra_notes:
        notes = extra_notes + notes
    return {
        "id": video_id,
        "title": title,
        "channel": clean_text(channel),
        "category": clean_text(category),
        "shortsUrl": normalized_url(video_id),
        "thumbnail": thumbnail_url(video_id),
        "viewsGained": int(views_gained or 0),
        "sourceRank": int(source_rank or 0),
        "sourceWindow": source_window,
        "sourceName": source_name,
        "sourceUrl": source_url,
        "collectedAt": collected_at,
        "matchNotes": notes,
    }


def from_vidirun_item(raw: dict[str, Any], source: dict[str, str], collected_at: str) -> dict[str, Any] | None:
    video_id = video_id_from_thumbnail(raw.get("Thumbnail", ""))
    if not video_id:
        return None
    return make_candidate(
        video_id=video_id,
        title=str(raw.get("Title", "")),
        channel=str(raw.get("Channel", "")),
        category=str(raw.get("Category", "")),
        views_gained=parse_int(raw.get("Views Gained")),
        source_rank=parse_int(raw.get("Rank")),
        source_window=source["window"],
        source_name=source["name"],
        source_url=source["page"],
        collected_at=collected_at,
    )


def collect_vidirun(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in VIDIRUN_SOURCES:
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


def collect_playboard(collected_at: str) -> list[dict[str, Any]]:
    source = HTML_SOURCES[0]
    try:
        html = fetch_text(source["page"])
    except Exception as exc:
        print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    rank = 0
    for match in re.finditer(r'<a[^>]+href="([^"]*/en/video/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
        href, label_html = match.groups()
        title = clean_text(label_html)
        video_id = video_id_from_any(href)
        if not video_id or not title or video_id in seen:
            continue
        seen.add(video_id)
        rank += 1
        item = make_candidate(
            video_id=video_id,
            title=title,
            channel="",
            category="Playboard Shorts Chart",
            views_gained=0,
            source_rank=rank,
            source_window=source["window"],
            source_name=source["name"],
            source_url=urljoin(source["page"], href),
            collected_at=collected_at,
            extra_notes=["source: Playboard shorts chart"],
            min_score=3,
        )
        if item:
            candidates.append(item)
    return candidates


def collect_redtoolbox(collected_at: str) -> list[dict[str, Any]]:
    source = HTML_SOURCES[1]
    try:
        html = fetch_text(source["page"])
    except Exception as exc:
        print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
        return []

    candidates: list[dict[str, Any]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I):
        video_id = video_id_from_any(row)
        if not video_id:
            continue
        rank_match = re.search(r'class="rank">\s*(\d+)', row, flags=re.I)
        title_match = re.search(r'<td class="title">\s*<a[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        channel_match = re.search(r'<span class="channel">\s*<a[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        growth_match = re.search(r"<font[^>]*>\s*\+?([\d,]+)\s*</font>", row, flags=re.S | re.I)
        item = make_candidate(
            video_id=video_id,
            title=clean_text(title_match.group(1) if title_match else ""),
            channel=clean_text(channel_match.group(1) if channel_match else ""),
            category="RedToolBox Top Shorts",
            views_gained=parse_int(growth_match.group(1) if growth_match else 0),
            source_rank=parse_int(rank_match.group(1) if rank_match else 0),
            source_window=source["window"],
            source_name=source["name"],
            source_url=source["page"],
            collected_at=collected_at,
            extra_notes=["source: RedToolBox top shorts"],
            min_score=3,
        )
        if item:
            candidates.append(item)
    return candidates


def collect_trendsfox(collected_at: str) -> list[dict[str, Any]]:
    source = HTML_SOURCES[2]
    try:
        html = fetch_text(source["page"])
    except Exception as exc:
        print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    rank = 0
    image_pattern = r'<img[^>]+src="https://i\.ytimg\.com/vi/([^/]+)/[^"]+"[^>]+alt="([^"]*)"[^>]*>'
    for match in re.finditer(image_pattern, html, flags=re.S | re.I):
        video_id, alt_title = match.groups()
        if video_id in seen:
            continue
        seen.add(video_id)
        rank += 1
        tail = html[match.end() : match.end() + 1200]
        channel_match = re.search(r"<p[^>]*>(.*?)</p>", tail, flags=re.S | re.I)
        item = make_candidate(
            video_id=video_id,
            title=alt_title,
            channel=clean_text(channel_match.group(1) if channel_match else ""),
            category="TrendsFox Trending Shorts",
            views_gained=0,
            source_rank=rank,
            source_window=source["window"],
            source_name=source["name"],
            source_url=source["page"],
            collected_at=collected_at,
            extra_notes=["source: TrendsFox sample trending shorts"],
            min_score=3,
        )
        if item:
            candidates.append(item)
    return candidates


def collect_top1trend(collected_at: str) -> list[dict[str, Any]]:
    source = HTML_SOURCES[3]
    try:
        html = fetch_text(source["page"])
    except Exception as exc:
        print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a[^>]+href="(/youtube/video_([A-Za-z0-9_-]{11})[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, video_id, label_html = match.groups()
        if video_id in seen:
            continue
        seen.add(video_id)
        text = clean_text(label_html)
        rank_match = re.match(r"#?\s*(\d+)", text)
        item = make_candidate(
            video_id=video_id,
            title=re.sub(r"^#?\s*\d+\s*(?:\+\s*\d+\s*)?", "", text),
            channel="",
            category="Top1Trend YouTube Trending",
            views_gained=0,
            source_rank=parse_int(rank_match.group(1) if rank_match else 0),
            source_window=source["window"],
            source_name=source["name"],
            source_url=urljoin(source["page"], href),
            collected_at=collected_at,
            extra_notes=["source: Top1Trend YouTube trending"],
        )
        if item:
            candidates.append(item)
    return candidates


def collect_html_sources(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for collector in (collect_playboard, collect_redtoolbox, collect_trendsfox, collect_top1trend):
        candidates.extend(collector(collected_at))
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
    search_text = re.sub(r"^ytsearch\d*:", "", query)
    return make_candidate(
        video_id=video_id,
        title=title,
        channel=str(raw.get("channel") or raw.get("uploader") or ""),
        category="YouTube Search",
        views_gained=parse_int(raw.get("view_count")),
        source_rank=0,
        source_window="search",
        source_name="YouTube Shorts search via yt-dlp",
        source_url=f"https://www.youtube.com/results?search_query={quote_plus(search_text)}",
        collected_at=collected_at,
        extra_notes=["source: YouTube search result"],
    )


def collect_youtube_search(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for query in YT_SEARCH_QUERIES:
        for raw in run_yt_search(query):
            item = from_ytdlp_item(raw, query, collected_at)
            if item:
                candidates.append(item)
    return candidates


def merge_items(existing: list[dict[str, Any]], new_items: list[dict[str, Any]], max_new: int) -> list[dict[str, Any]]:
    old_by_id = {item.get("id"): item for item in existing if item.get("id")}
    ranked = sorted(new_items, key=rank_item)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ranked:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        deduped.append(item)

    selected = deduped[:max_new]
    selected_sources = {item.get("sourceName") for item in selected}
    selected_ids = {item.get("id") for item in selected}

    source_heads: dict[str, dict[str, Any]] = {}
    for item in deduped:
        source_name = item.get("sourceName") or ""
        if source_name and source_name not in source_heads:
            source_heads[source_name] = item

    for source_name, item in sorted(source_heads.items(), key=lambda pair: rank_item(pair[1])):
        if source_name in selected_sources or item.get("id") in selected_ids:
            continue
        if len(selected) < max_new:
            selected.append(item)
        else:
            replaced = selected[-1]
            selected_sources.discard(replaced.get("sourceName"))
            selected_ids.discard(replaced.get("id"))
            selected[-1] = item
        selected_sources.add(source_name)
        selected_ids.add(item.get("id"))

    fresh: list[dict[str, Any]] = []
    for item in selected:
        video_id = item.get("id")
        if not video_id:
            continue
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

    fresh_ids = {item.get("id") for item in fresh}
    tail = [item for item in existing if item.get("id") not in fresh_ids]
    return fresh + tail


def rank_item(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("sourceWindow") != "24H",
        -(item.get("viewsGained") or 0),
        item.get("sourceRank") or 9999,
    )


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def source_links(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for source in VIDIRUN_SOURCES:
        pairs.add((source["name"], source["page"]))
    for source in HTML_SOURCES:
        pairs.add((source["name"], source["page"]))
    pairs.add(("YouTube Shorts keyword searches", "https://www.youtube.com/results?search_query=%23shorts+dance+music+trend"))
    known_names = {name for name, _ in pairs}
    for item in items:
        source_name = item.get("sourceName") or ""
        if source_name and source_name not in known_names:
            pairs.add((source_name, item.get("sourceUrl") or "#"))
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
          <p class="lead">Vidirun, Playboard, RedToolBox, TrendsFox, Top1Trend, YouTube 검색에서 음악 중심 배경, 자막 없음, 1~2명 등장, 댄스 또는 짧은 상황형으로 보이는 인기 YouTube Shorts 후보를 모아 최신순으로 누적합니다.</p>
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
    <div class="notice">GitHub Actions가 매일 17:00 KST에 여러 공개 트렌드/랭킹 소스를 확인합니다. 공개 데이터는 영상 안의 실제 자막, 대사 유무, 인물 수를 직접 제공하지 않으므로 제목, 카테고리, 썸네일, 트렌드 순위를 기준으로 후보를 자동 수집하고 검수 메모를 남깁니다.</div>
    <section class="grid" aria-label="trending shorts">
{''.join(cards)}
    </section>
    <section class="source-panel" aria-label="sources">
      <span>Connected sources:</span>
      {links}
    </section>
  </main>
  <footer>
    <div class="shell">Runs on GitHub-hosted Actions at 17:00 Asia/Seoul. New matches are prepended and older links stay below.</div>
  </footer>
  <script type="application/json" id="shorts-data">{data_json}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true", help="Render index.html from existing shorts-data.json")
    parser.add_argument("--max-new", type=int, default=int(os.environ.get("MAX_NEW_SHORTS", "20")))
    args = parser.parse_args()

    existing = read_data()
    if args.render_only:
        merged = existing
    else:
        collected_at = datetime.now(KST).replace(microsecond=0).isoformat()
        candidates = collect_vidirun(collected_at)
        candidates.extend(collect_html_sources(collected_at))
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
