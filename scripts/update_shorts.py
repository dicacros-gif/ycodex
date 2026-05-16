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

REGIONS = [
    {"key": "global", "label": "글로벌", "queries": [
        "#shorts dance challenge music trend",
        "#shorts slowed dance edit",
        "#shorts cute dance one person music",
    ]},
    {"key": "kr", "label": "KR", "queries": [
        "#shorts 댄스 음악 챌린지",
        "한국 쇼츠 댄스 음악 트렌드",
    ]},
    {"key": "us", "label": "US", "queries": [
        "#shorts dance challenge music USA",
        "US trending shorts dance music",
    ]},
    {"key": "jp", "label": "JP", "queries": [
        "#shorts ダンス 音楽 チャレンジ 日本",
        "Japan shorts dance challenge music",
    ]},
    {"key": "mx", "label": "멕시코", "queries": [
        "#shorts baile musica tendencia Mexico",
        "Mexico dance challenge shorts music",
    ]},
    {"key": "de", "label": "독일", "queries": [
        "#shorts tanz musik trend deutschland",
        "Germany dance challenge shorts music",
    ]},
    {"key": "br", "label": "브라질", "queries": [
        "#shorts danca musica tendencia Brasil",
        "Brazil dance challenge shorts funk",
    ]},
    {"key": "id", "label": "인도네시아", "queries": [
        "#shorts joget musik viral Indonesia",
        "Indonesia dance challenge shorts music",
    ]},
    {"key": "ar", "label": "아르헨티나", "queries": [
        "#shorts baile musica tendencia Argentina",
        "Argentina dance challenge shorts music",
    ]},
    {"key": "ph", "label": "필리핀", "queries": [
        "#shorts dance challenge music Philippines",
        "Philippines trending shorts dance music",
    ]},
    {"key": "es", "label": "스페인", "queries": [
        "#shorts baile musica tendencia Espana",
        "Spain dance challenge shorts music",
    ]},
    {"key": "it", "label": "이탈리아", "queries": [
        "#shorts ballo musica tendenza Italia",
        "Italy dance challenge shorts music",
    ]},
    {"key": "fr", "label": "프랑스", "queries": [
        "#shorts danse musique tendance France",
        "France dance challenge shorts music",
    ]},
    {"key": "uz", "label": "우즈베키스탄", "queries": [
        "#shorts raqs musiqa trend Uzbekistan",
        "Uzbekistan dance challenge shorts music",
    ]},
    {"key": "dz", "label": "알제리", "queries": [
        "#shorts danse musique Algerie",
        "Algeria dance challenge shorts music",
    ]},
    {"key": "kz", "label": "카자흐스탄", "queries": [
        "#shorts bi muzyka Kazakhstan",
        "Kazakhstan dance challenge shorts music",
    ]},
    {"key": "vn", "label": "베트남", "queries": [
        "#shorts nhay nhac trend Viet Nam",
        "Vietnam dance challenge shorts music",
    ]},
]

REGION_BY_KEY = {region["key"]: region for region in REGIONS}

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

YT_SEARCH_LIMIT = int(os.environ.get("YT_SEARCH_LIMIT", "12"))

CORE_TERMS = {
    "dance",
    "댄스",
    "춤",
    "baile",
    "ballo",
    "danse",
    "danca",
    "dança",
    "joget",
    "tari",
    "tanz",
    "raqs",
    "nhay",
    "nhảy",
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
    "musica",
    "música",
    "musik",
    "musiqa",
    "nhac",
    "nhạc",
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
    return normalize_items(json.loads(DATA_PATH.read_text(encoding="utf-8")))


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        region = item.get("region") or "global"
        if region not in REGION_BY_KEY:
            region = "global"
        item["region"] = region
        item["regionLabel"] = REGION_BY_KEY[region]["label"]
        normalized.append(item)
    return normalized


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
    region: str,
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
    if region not in REGION_BY_KEY:
        region = "global"
    score, notes = score_candidate(title, category)
    if score < min_score:
        return None
    if extra_notes:
        notes = extra_notes + notes
    return {
        "id": video_id,
        "region": region,
        "regionLabel": REGION_BY_KEY[region]["label"],
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
        region="global",
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
            region="global",
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
            region="global",
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
            region="global",
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
            region="global",
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


def from_ytdlp_item(raw: dict[str, Any], query: str, region: str, collected_at: str) -> dict[str, Any] | None:
    video_id = raw.get("id")
    duration = raw.get("duration")
    if not video_id:
        return None
    if isinstance(duration, (int, float)) and duration > 180:
        return None
    title = str(raw.get("title", "")).strip()
    search_text = re.sub(r"^ytsearch\d*:", "", query)
    return make_candidate(
        region=region,
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
    for region in REGIONS:
        for text_query in region["queries"]:
            query = f"ytsearch{YT_SEARCH_LIMIT}:{text_query}"
            for raw in run_yt_search(query):
                item = from_ytdlp_item(raw, query, region["key"], collected_at)
                if item:
                    candidates.append(item)
    return candidates


def merge_items(existing: list[dict[str, Any]], new_items: list[dict[str, Any]], max_new: int) -> list[dict[str, Any]]:
    old_by_id = {item.get("id"): item for item in existing if item.get("id")}
    ranked = sorted(new_items, key=rank_item)

    candidates_by_region: dict[str, list[dict[str, Any]]] = {region["key"]: [] for region in REGIONS}
    seen: set[str] = set()
    for item in ranked:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        region = item.get("region") or "global"
        if region not in candidates_by_region:
            region = "global"
        candidates_by_region[region].append(item)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for region in REGIONS:
        count = 0
        for item in candidates_by_region[region["key"]]:
            video_id = item.get("id")
            if not video_id or video_id in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(video_id)
            count += 1
            if count >= max_new:
                break

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
                    "region": item.get("region") or old.get("region") or "global",
                    "regionLabel": item.get("regionLabel") or old.get("regionLabel") or "Global",
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
    tail: list[dict[str, Any]] = []
    seen_ids = set(fresh_ids)
    for item in existing:
        video_id = item.get("id")
        if not video_id or video_id in seen_ids:
            continue
        seen_ids.add(video_id)
        tail.append(item)
    return fresh + tail


def rank_item(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        REGIONS.index(REGION_BY_KEY.get(item.get("region") or "global", REGION_BY_KEY["global"])),
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


def render_card(item: dict[str, Any], index: int) -> str:
    notes = "".join(f"<li>{escape(str(note))}</li>" for note in item.get("matchNotes", []))
    source_rank = f" · rank {item.get('sourceRank')}" if item.get("sourceRank") else ""
    return f"""
      <article class="short-card">
        <div class="thumb-link">
          <img src="{escape(item['thumbnail'])}" alt="{escape(item['title'])} thumbnail" loading="lazy">
          <span class="rank">#{index}</span>
        </div>
        <div class="short-body">
          <div class="meta-row">
            <span>{escape(str(item.get('regionLabel') or 'Global'))} · {escape(str(item.get('sourceWindow', 'trend')))}</span>
            <span>{fmt_int(item.get('viewsGained'))} views</span>
          </div>
          <h2>{escape(item['title'])}</h2>
          <p class="video-url"><a href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">Open YouTube Short</a></p>
          <p class="channel">{escape(str(item.get('channel') or 'Unknown channel'))}</p>
          <p class="source">Source: <a href="{escape(str(item.get('sourceUrl') or '#'))}" target="_blank" rel="noopener">{escape(str(item.get('sourceName') or 'source'))}</a>{escape(source_rank)}</p>
          <ul class="notes">{notes}</ul>
        </div>
      </article>"""


def group_items_by_region(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {region["key"]: [] for region in REGIONS}
    seen: set[str] = set()
    for item in normalize_items(items):
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        grouped[item["region"]].append(item)
    return grouped


def render_index(items: list[dict[str, Any]]) -> str:
    items = normalize_items(items)
    latest = items[0].get("collectedAt", "") if items else ""
    grouped = group_items_by_region(items)

    tab_buttons = "\n".join(
        f"""<button class="tab-button{' active' if region['key'] == 'global' else ''}" type="button" data-region-tab="{region['key']}">{escape(region['label'])}<span>{len(grouped[region['key']])}</span></button>"""
        for region in REGIONS
    )

    panels = []
    for region in REGIONS:
        region_cards = "".join(render_card(item, index) for index, item in enumerate(grouped[region["key"]], start=1))
        if not region_cards:
            region_cards = '<div class="empty-state">No matching Shorts collected for this region yet.</div>'
        panels.append(
            f"""
    <section class="region-panel{' active' if region['key'] == 'global' else ''}" data-region-panel="{region['key']}" aria-label="{escape(region['label'])} trending shorts">
      <div class="grid">{region_cards}
      </div>
    </section>"""
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
  <meta name="description" content="지역별 인기 YouTube Shorts 후보 모음">
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
    .tabs {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 0 0 18px;
      scrollbar-width: thin;
    }}
    .tab-button {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: #344054;
      padding: 9px 12px;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }}
    .tab-button span {{
      min-width: 22px;
      padding: 2px 6px;
      border-radius: 999px;
      background: #edf2f7;
      color: #475467;
      font-size: 12px;
    }}
    .tab-button.active {{
      background: var(--ink);
      border-color: var(--ink);
      color: white;
    }}
    .tab-button.active span {{
      background: rgba(255, 255, 255, 0.18);
      color: white;
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
      grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
      gap: 9px;
      align-items: stretch;
    }}
    .region-panel {{
      display: none;
    }}
    .region-panel.active {{
      display: block;
    }}
    .empty-state {{
      grid-column: 1 / -1;
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 26px;
      background: var(--surface);
      color: var(--muted);
      font-size: 14px;
      text-align: center;
    }}
    .short-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: row;
      min-height: 100%;
    }}
    .thumb-link {{
      position: relative;
      display: block;
      flex: 0 0 74px;
      width: 74px;
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
      top: 5px;
      left: 5px;
      background: rgba(24, 33, 47, 0.86);
      color: white;
      border-radius: 999px;
      padding: 3px 6px;
      font-size: 10px;
      font-weight: 700;
    }}
    .short-body {{
      min-width: 0;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 5px;
    }}
    .meta-row {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--accent-2);
      font-size: 10px;
      font-weight: 700;
    }}
    .short-card h2 {{
      margin: 0;
      font-size: 13px;
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .short-card h2 a {{
      text-decoration: none;
    }}
    .short-card h2 a:hover {{
      text-decoration: underline;
    }}
    .channel,
    .video-url,
    .source {{
      margin: 0;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }}
    .video-url a {{
      color: var(--focus);
      overflow-wrap: anywhere;
      text-decoration: none;
    }}
    .source a {{
      color: var(--focus);
      text-decoration: none;
    }}
    .notes {{
      display: none;
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
      .grid {{ grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }}
      .thumb-link {{ flex-basis: 68px; width: 68px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="shell">
      <div class="topbar">
        <div>
          <h1>YouTube Shorts Trend Watch</h1>
          <p class="lead">글로벌, KR, US, JP, 멕시코, 독일, 브라질, 인도네시아, 아르헨티나, 필리핀, 스페인, 이탈리아, 프랑스, 우즈베키스탄, 알제리, 카자흐스탄, 베트남 탭별로 음악 중심 배경, 자막 없음, 1~2명 등장, 댄스 또는 짧은 상황형으로 보이는 인기 YouTube Shorts 후보를 수집합니다.</p>
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
        <span class="chip">region tabs</span>
        <span class="chip">no duplicate videos</span>
        <span class="chip">new items stay on top</span>
      </div>
    </div>
  </header>
  <main class="shell">
    <div class="notice">GitHub Actions가 매일 17:00 KST에 여러 공개 트렌드/랭킹 소스와 지역별 검색어를 확인합니다. 같은 YouTube 영상 ID는 전체 탭에서 한 번만 배치하며, 공개 데이터가 제공하지 않는 자막·대사·인물 수 조건은 검수 메모로 남깁니다.</div>
    <nav class="tabs" aria-label="region tabs">
      {tab_buttons}
    </nav>
{''.join(panels)}
    <section class="source-panel" aria-label="sources">
      <span>Connected sources:</span>
      {links}
    </section>
  </main>
  <footer>
    <div class="shell">Runs on GitHub-hosted Actions at 17:00 Asia/Seoul. New region matches are prepended and older unique links stay below.</div>
  </footer>
  <script type="application/json" id="shorts-data">{data_json}</script>
  <script>
    const buttons = Array.from(document.querySelectorAll("[data-region-tab]"));
    const panelsByRegion = new Map(Array.from(document.querySelectorAll("[data-region-panel]")).map((panel) => [panel.dataset.regionPanel, panel]));

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const region = button.dataset.regionTab;
        buttons.forEach((item) => item.classList.toggle("active", item === button));
        panelsByRegion.forEach((panel, key) => panel.classList.toggle("active", key === region));
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true", help="Render index.html from existing shorts-data.json")
    parser.add_argument("--max-new", type=int, default=int(os.environ.get("MAX_NEW_SHORTS_PER_REGION", "8")))
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
