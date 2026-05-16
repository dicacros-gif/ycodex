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
from urllib.parse import quote_plus, urlencode, urljoin

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

PLAYBOARD_REGION_SLUGS = {
    "global": "worldwide",
    "kr": "south-korea",
    "us": "united-states",
    "jp": "japan",
    "mx": "mexico",
    "de": "germany",
    "br": "brazil",
    "id": "indonesia",
    "ar": "argentina",
    "ph": "philippines",
    "es": "spain",
    "it": "italy",
    "fr": "france",
    "uz": "uzbekistan",
    "dz": "algeria",
    "kz": "kazakhstan",
    "vn": "viet-nam",
}

PLAYBOARD_SOURCES = [
    {
        "name": f"Playboard Shorts Daily - {REGION_BY_KEY[region]['label']}",
        "page": f"https://playboard.co/chart/short/most-viewed-all-videos-in-{slug}-daily",
        "window": "daily",
        "region": region,
    }
    for region, slug in PLAYBOARD_REGION_SLUGS.items()
]

REDTOOLBOX_SOURCES = [
    {
        "name": "RedToolBox Top Shorts",
        "page": "https://www.redtoolbox.io/toplist/topShorts.jsp?day=1&type=VIEW",
        "window": "daily",
    },
    {
        "name": "RedToolBox Top Shorts",
        "page": "https://www.redtoolbox.io/toplist/topShorts.jsp?day=7&type=VIEW",
        "window": "weekly",
    },
    {
        "name": "RedToolBox Top Shorts",
        "page": "https://www.redtoolbox.io/toplist/topShorts.jsp?day=30&type=VIEW",
        "window": "monthly",
    },
]

YTTRACK_REGION_CODES = {
    "kr": "KR",
    "us": "US",
    "mx": "MX",
    "br": "BR",
    "ar": "AR",
    "es": "ES",
}

YTTRACK_CATEGORY_IDS = [
    ("24", "Entertainment"),
    ("23", "Comedy"),
    ("10", "Music"),
]

CHARTIKA_REGION_IDS = {
    "global": "gl",
    "kr": "kr",
    "us": "us",
    "jp": "jp",
    "mx": "mx",
    "de": "de",
    "br": "br",
    "id": "id",
    "ar": "ar",
    "ph": "ph",
    "es": "es",
    "it": "it",
    "fr": "fr",
    "uz": "uz",
    "dz": "dz",
    "kz": "kz",
    "vn": "vn",
}

RANKING_SOURCE_LIMIT = int(os.environ.get("RANKING_SOURCE_LIMIT", "18"))
YT_SEARCH_LIMIT = int(os.environ.get("YT_SEARCH_LIMIT", "12"))
MIN_DISPLAY_VIEWS = int(os.environ.get("MIN_DISPLAY_VIEWS", "3000"))
PUBLISHED_METADATA_LIMIT = int(os.environ.get("PUBLISHED_METADATA_LIMIT", "200"))
VIRAL_VIEW_THRESHOLD = int(os.environ.get("VIRAL_VIEW_THRESHOLD", "100000000"))

CORE_TERMS = {
    "dance",
    "dances",
    "danced",
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
    "performing",
    "stunt",
    "fail",
    "funny",
    "humor",
    "reaction",
    "react",
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
    "official video",
    "music video",
    "trailer",
    "shopping",
    "haul",
    "animal",
    "animals",
    "cat",
    "cats",
    "dog",
    "dogs",
    "duck",
    "puppy",
    "pet",
    "pets",
    "강아지",
    "고양이",
    "food",
    "street food",
    "recipe",
    "dessert",
    "ice cream",
    "lollipop",
    "cocomelon",
    "learn",
    "learning",
    "count",
    "number",
    "kids",
    "children",
    "criança",
    "crianças",
    "nursery",
    "baby",
    "toddler",
    "toy",
    "toys",
    "asmr",
    "아기",
    "동요",
    "동화",
    "gameplay",
    "minecraft",
    "roblox",
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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
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
        item.setdefault("likeCount", None)
        normalized.append(item)
    return normalized


def parse_collected_at(value: Any) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        collected = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if collected.tzinfo is None:
        collected = collected.replace(tzinfo=KST)
    return collected.astimezone(timezone.utc)


def newest_first_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -parse_collected_at(item.get("collectedAt")).timestamp(),
        *rank_item(item),
        item.get("id") or "",
    )


def order_items_newest_first(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(normalize_items(items), key=newest_first_key)


def write_data(items: list[dict[str, Any]]) -> None:
    items = order_items_newest_first(items)
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
    hits = []
    for term in terms:
        term_lower = term.lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9\s'-]*", term_lower):
            pattern = rf"(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])"
            if re.search(pattern, lower):
                hits.append(term)
        elif term_lower in lower:
            hits.append(term)
    return sorted(hits)


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


def fmt_count(value: Any) -> str:
    if value is None or value == "":
        return "확인 필요"
    count = parse_int(value)
    if count <= 0:
        return "확인 필요"
    return f"{count:,}"


def normalize_published_at(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
        except Exception:
            return ""

    text = clean_text(str(value))
    if not text:
        return ""
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    match = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def fmt_published(value: Any) -> str:
    return normalize_published_at(value) or "확인 필요"


def fmt_registered(value: Any) -> str:
    if not value:
        return "확인 필요"
    registered = parse_collected_at(value).astimezone(KST)
    if registered.year == 1970:
        return "확인 필요"
    return registered.strftime("%Y-%m-%d %H:%M")


def fmt_footer_update(value: Any | None = None) -> str:
    if value:
        updated = parse_collected_at(value).astimezone(KST)
    else:
        updated = datetime.now(KST)
    return f"{updated.month}/{updated.day} {updated.hour:02d}:{updated.minute:02d}"


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
    score -= len(exclude_hits) * 5

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
    published_at: Any = "",
    like_count: Any = None,
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
        "likeCount": parse_int(like_count) if like_count is not None else None,
        "sourceRank": int(source_rank or 0),
        "sourceWindow": source_window,
        "sourceName": source_name,
        "sourceUrl": source_url,
        "collectedAt": collected_at,
        "publishedAt": normalize_published_at(published_at),
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
    candidates: list[dict[str, Any]] = []
    for source in PLAYBOARD_SOURCES:
        try:
            html = fetch_text(source["page"])
        except Exception as exc:
            print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
            continue

        seen: set[str] = set()
        row_pattern = r'<tr class="chart__row"[^>]*>(.*?)(?=<tr class="chart__row"|</tbody>)'
        for row in re.findall(row_pattern, html, flags=re.S | re.I):
            video_id = video_id_from_any(row)
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            rank_match = re.search(r'<div class="current"[^>]*>\s*(\d+)\s*</div>', row, flags=re.S | re.I)
            title_match = re.search(r'class="title__label"[^>]*title="([^"]+)"', row, flags=re.S | re.I)
            if not title_match:
                title_match = re.search(r'<td class="thumbnail"[^>]*>.*?title="([^"]+)"', row, flags=re.S | re.I)
            published_match = re.search(r'<div class="title__date"[^>]*>\s*([^<]+?)\s*</div>', row, flags=re.S | re.I)
            channel_match = re.search(r'class="channel__wrapper"[^>]*title="([^"]+)"', row, flags=re.S | re.I)
            views_match = re.search(r'<td class="score"[^>]*>.*?>([\d,]+)\s*</span>', row, flags=re.S | re.I)
            href_match = re.search(r'href="([^"]*/video/[A-Za-z0-9_-]{11}[^"]*)"', row, flags=re.S | re.I)
            item = make_candidate(
                region=source["region"],
                video_id=video_id,
                title=clean_text(title_match.group(1) if title_match else ""),
                channel=clean_text(channel_match.group(1) if channel_match else ""),
                category="Playboard Shorts Chart",
                views_gained=parse_int(views_match.group(1) if views_match else 0),
                source_rank=parse_int(rank_match.group(1) if rank_match else 0),
                source_window=source["window"],
                source_name=source["name"],
                source_url=urljoin(source["page"], href_match.group(1) if href_match else source["page"]),
                collected_at=collected_at,
                published_at=published_match.group(1) if published_match else "",
                extra_notes=["source: Playboard regional shorts chart"],
                min_score=0,
            )
            if item:
                candidates.append(item)
                if len(seen) >= RANKING_SOURCE_LIMIT:
                    break
    return candidates


def collect_redtoolbox(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in REDTOOLBOX_SOURCES:
        try:
            html = fetch_text(source["page"])
        except Exception as exc:
            print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
            continue

        count = 0
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
                extra_notes=[f"source: RedToolBox top shorts {source['window']} chart"],
                min_score=0,
            )
            if item:
                candidates.append(item)
                count += 1
                if count >= RANKING_SOURCE_LIMIT:
                    break
    return candidates


def collect_trendsfox(collected_at: str) -> list[dict[str, Any]]:
    source = HTML_SOURCES[0]
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
    source = HTML_SOURCES[1]
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


def collect_yttrack(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for region, region_code in YTTRACK_REGION_CODES.items():
        for category_id, category_name in YTTRACK_CATEGORY_IDS:
            params = urlencode(
                {
                    "categoryId": category_id,
                    "regionCode": region_code,
                    "maxResults": str(RANKING_SOURCE_LIMIT),
                }
            )
            page = f"https://yttrack.com/search.php?{params}"
            try:
                html = fetch_text(page)
            except Exception as exc:
                print(f"warning: failed to fetch {page}: {exc}", file=sys.stderr)
                continue

            row_pattern = r"<tr><th scope='row'>\s*(\d+)\s*</th>(.*?)(?=<tr><th scope='row'>|</tbody>)"
            for rank_text, row in re.findall(row_pattern, html, flags=re.S | re.I):
                cells = re.findall(r"<td>(.*?)</td>", row, flags=re.S | re.I)
                if len(cells) < 4:
                    continue
                video_id = video_id_from_any(cells[0])
                title = clean_text(cells[2])
                if not video_id or not title or "short" not in f"{title} {row}".lower():
                    continue
                channel = clean_text(cells[1])
                item = make_candidate(
                    region=region,
                    video_id=video_id,
                    title=title,
                    channel=channel,
                    category=category_name,
                    views_gained=parse_int(cells[3]),
                    source_rank=parse_int(rank_text),
                    source_window="regional",
                    source_name=f"YTTrack Trending - {REGION_BY_KEY[region]['label']} {category_name}",
                    source_url=page,
                    collected_at=collected_at,
                    extra_notes=["source: YTTrack regional trending chart"],
                    min_score=0,
                )
                if item:
                    candidates.append(item)
    return candidates


def collect_chartika(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    local_date = collected_at[:10]
    for region, chartika_region in CHARTIKA_REGION_IDS.items():
        for chapter_id, category_name in (("main", "Entertainment"), ("music", "Music")):
            params = urlencode(
                {
                    "method": "getChart",
                    "region_id": chartika_region,
                    "chapter_id": chapter_id,
                    "period_type": "day",
                    "start_date": local_date,
                    "end_date": local_date,
                    "local_date": local_date,
                }
            )
            api_url = f"https://api.chartika.com/api.php?{params}"
            page = f"https://chartika.com/{chartika_region}/{chapter_id}"
            try:
                payload = fetch_json(api_url)
            except Exception as exc:
                print(f"warning: failed to fetch {api_url}: {exc}", file=sys.stderr)
                continue

            rows = (payload.get("data") or {}).get("items") or []
            count = 0
            for raw in rows:
                video_id = str(raw.get("video_id") or "")
                duration = parse_int(raw.get("duration"))
                if not video_id or duration <= 0 or duration > 180:
                    continue
                item = make_candidate(
                    region=region,
                    video_id=video_id,
                    title=str(raw.get("title") or ""),
                    channel=str(raw.get("channel_title") or ""),
                    category=category_name,
                    views_gained=parse_int(raw.get("points")),
                    source_rank=parse_int(raw.get("position")),
                    source_window="chart-day",
                    source_name=f"Chartika {REGION_BY_KEY[region]['label']} {category_name} Chart",
                    source_url=page,
                    collected_at=collected_at,
                    published_at=raw.get("published_at"),
                    extra_notes=[f"source: Chartika regional chart", f"duration: {duration}s"],
                    min_score=3,
                )
                if item:
                    candidates.append(item)
                    count += 1
                    if count >= RANKING_SOURCE_LIMIT:
                        break
    return candidates


def collect_html_sources(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for collector in (
        collect_playboard,
        collect_redtoolbox,
        collect_yttrack,
        collect_chartika,
        collect_trendsfox,
        collect_top1trend,
    ):
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


def run_yt_metadata(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for index in range(0, len(video_ids), 40):
        chunk = video_ids[index : index + 40]
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--skip-download",
            "--dump-json",
            "--ignore-errors",
            "--no-warnings",
            *[normalized_url(video_id) for video_id in chunk],
        ]
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
        except Exception as exc:
            print(f"warning: yt-dlp metadata failed: {exc}", file=sys.stderr)
            continue
        if proc.returncode != 0 and proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        for line in proc.stdout.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            video_id = payload.get("id")
            if video_id:
                metadata[video_id] = payload
    return metadata


def enrich_video_metadata(items: list[dict[str, Any]]) -> None:
    targets: list[str] = []
    seen: set[str] = set()
    for item in items:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        if item.get("likeCount") is None or not item.get("publishedAt") or parse_int(item.get("viewsGained")) < MIN_DISPLAY_VIEWS:
            targets.append(video_id)
            seen.add(video_id)
            if len(targets) >= PUBLISHED_METADATA_LIMIT:
                break
    if not targets:
        return

    metadata = run_yt_metadata(targets)
    for item in items:
        payload = metadata.get(item.get("id"))
        if not payload:
            continue
        published_at = normalize_published_at(
            payload.get("upload_date") or payload.get("timestamp") or payload.get("release_timestamp")
        )
        if published_at:
            item["publishedAt"] = published_at
        view_count = parse_int(payload.get("view_count"))
        if view_count:
            item["viewsGained"] = view_count
        if payload.get("like_count") is not None:
            item["likeCount"] = parse_int(payload.get("like_count"))


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
        source_name="YouTube keyword search",
        source_url=f"https://www.youtube.com/results?search_query={quote_plus(search_text)}",
        collected_at=collected_at,
        published_at=raw.get("upload_date") or raw.get("timestamp") or raw.get("release_timestamp") or "",
        like_count=raw.get("like_count"),
        extra_notes=["source: YouTube search result"],
    )


def collect_youtube_search(collected_at: str, region_keys: set[str] | None = None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for region in REGIONS:
        if region_keys is not None and region["key"] not in region_keys:
            continue
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
                    "likeCount": item.get("likeCount") if item.get("likeCount") is not None else old.get("likeCount"),
                    "sourceRank": item.get("sourceRank") or old.get("sourceRank"),
                    "sourceWindow": item.get("sourceWindow") or old.get("sourceWindow"),
                    "sourceName": item.get("sourceName") or old.get("sourceName"),
                    "sourceUrl": item.get("sourceUrl") or old.get("sourceUrl"),
                    "collectedAt": item.get("collectedAt") or old.get("collectedAt"),
                    "publishedAt": item.get("publishedAt") or old.get("publishedAt"),
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
    return order_items_newest_first(fresh + tail)


def regions_needing_search(candidates: list[dict[str, Any]], max_new: int) -> set[str]:
    counts = {region["key"]: 0 for region in REGIONS}
    seen: set[str] = set()
    for item in sorted(candidates, key=rank_item):
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        region = item.get("region") or "global"
        if region not in counts:
            region = "global"
        if counts[region] < max_new:
            counts[region] += 1
    return {region for region, count in counts.items() if count < max_new}


def source_priority(item: dict[str, Any]) -> int:
    name = str(item.get("sourceName") or "")
    if "Vidirun" in name:
        return 0
    if "Playboard" in name:
        return 1
    if "RedToolBox" in name:
        return 2
    if "YTTrack" in name:
        return 3
    if "Chartika" in name:
        return 4
    if "TrendsFox" in name:
        return 5
    if "Top1Trend" in name:
        return 6
    if "YouTube Search" in name:
        return 9
    return 7


def is_displayable(item: dict[str, Any]) -> bool:
    return parse_int(item.get("viewsGained")) >= MIN_DISPLAY_VIEWS and bool(item.get("publishedAt"))


def rank_item(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        REGIONS.index(REGION_BY_KEY.get(item.get("region") or "global", REGION_BY_KEY["global"])),
        source_priority(item),
        item.get("sourceWindow") != "24H",
        -(item.get("viewsGained") or 0),
        item.get("sourceRank") or 9999,
    )


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def parse_date(value: Any) -> datetime.date | None:
    normalized = normalize_published_at(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def source_links(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for source in VIDIRUN_SOURCES:
        pairs.add((source["name"], source["page"]))
    for source in PLAYBOARD_SOURCES:
        pairs.add((source["name"], source["page"]))
    for source in REDTOOLBOX_SOURCES:
        pairs.add((f"{source['name']} {source['window']}", source["page"]))
    pairs.add(("Playboard regional YouTube Shorts charts", "https://playboard.co/chart/short/most-viewed-all-videos-in-worldwide-daily"))
    pairs.add(("RedToolBox daily/weekly/monthly top Shorts", "https://www.redtoolbox.io/toplist/topShorts.jsp"))
    pairs.add(("YTTrack regional YouTube trending charts", "https://yttrack.com/"))
    pairs.add(("Chartika regional YouTube charts", "https://chartika.com/"))
    for source in HTML_SOURCES:
        pairs.add((source["name"], source["page"]))
    pairs.add(("YouTube Shorts keyword searches", "https://www.youtube.com/results?search_query=%23shorts+dance+music+trend"))
    known_names = {name for name, _ in pairs}
    for item in items:
        source_name = item.get("sourceName") or ""
        if source_name == "YouTube keyword search":
            continue
        if source_name and source_name not in known_names:
            pairs.add((source_name, item.get("sourceUrl") or "#"))
    return sorted(pairs)


TREND_CLUSTERS = [
    {
        "key": "dance",
        "label": "댄스·음악 챌린지",
        "terms": {
            "dance",
            "dances",
            "dancing",
            "dancer",
            "댄스",
            "춤",
            "challenge",
            "챌린지",
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
            "music",
            "musica",
            "música",
            "musik",
            "musiqa",
        },
    },
    {
        "key": "edit",
        "label": "편집·슬로우드 사운드",
        "terms": {"edit", "edits", "slowed", "funk", "phonk", "beat", "montagem", "jumpstyle", "velocity"},
    },
    {
        "key": "situation",
        "label": "상황형 코미디·짧은 사건",
        "terms": {
            "funny",
            "comedy",
            "humor",
            "prank",
            "surprise",
            "saved",
            "happened",
            "wild",
            "angry",
            "movie",
            "series",
            "상황",
            "마술",
        },
    },
    {
        "key": "performance",
        "label": "스포츠·퍼포먼스 순간",
        "terms": {"football", "f1", "formula1", "stunt", "battle", "moonwalk", "michael jackson", "backstage", "reveal"},
    },
    {
        "key": "kpop",
        "label": "K-pop·아이돌 파생",
        "terms": {"kpop", "k-pop", "bts", "new jeans", "newjeans", "jisoo", "blackpink", "소녀시대", "뉴진스", "방탄소년단"},
    },
]


def item_text(item: dict[str, Any]) -> str:
    notes = " ".join(str(note) for note in item.get("matchNotes", []))
    return f"{item.get('title', '')} {item.get('category', '')} {notes}"


def item_cluster_keys(item: dict[str, Any]) -> list[str]:
    text = item_text(item)
    keys = [cluster["key"] for cluster in TREND_CLUSTERS if term_hits(text, cluster["terms"])]
    return keys or ["other"]


def cluster_label(key: str) -> str:
    for cluster in TREND_CLUSTERS:
        if cluster["key"] == key:
            return cluster["label"]
    return "기타 신호"


def cluster_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {cluster["key"]: 0 for cluster in TREND_CLUSTERS}
    counts["other"] = 0
    for item in items:
        for key in item_cluster_keys(item):
            counts[key] += 1
    return counts


def top_cluster(items: list[dict[str, Any]]) -> tuple[str, int]:
    counts = cluster_counts(items)
    key, count = max(counts.items(), key=lambda pair: pair[1])
    return key, count


def trend_ratio(counts: dict[str, int], key: str, total: int) -> float:
    if total <= 0:
        return 0.0
    return counts.get(key, 0) / total


def compact_title(title: str, limit: int = 46) -> str:
    title = clean_text(title)
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip() + "..."


def published_age_days(item: dict[str, Any]) -> int | None:
    published = parse_date(item.get("publishedAt"))
    if not published:
        return None
    today = datetime.now(KST).date()
    return max((today - published).days, 0)


def brief_popularity_reason(item: dict[str, Any]) -> str:
    views = parse_int(item.get("viewsGained"))
    clusters = item_cluster_keys(item)
    labels = [cluster_label(key) for key in clusters if key != "other"]
    text = item_text(item).lower()
    reasons: list[str] = []

    if "situation" in clusters:
        reasons.append("첫 장면만 봐도 갈등이나 반전이 이해되는 상황형 포맷")
    if "dance" in clusters:
        reasons.append("음악·동작을 따라 하거나 다시 보기 쉬운 반복 구조")
    if "edit" in clusters:
        reasons.append("슬로우드/펑크/빠른 편집처럼 짧은 몰입감을 만드는 사운드 신호")
    if "performance" in clusters:
        reasons.append("스포츠·스턴트·무대 순간처럼 결과를 끝까지 확인하게 하는 장면")
    if "kpop" in clusters:
        reasons.append("K-pop·아이돌 팬덤과 챌린지 확산에 올라탈 수 있는 소재")
    if any(term in text for term in ("magic", "surprise", "saved", "reveal", "defying", "wild")):
        reasons.append("호기심을 여는 키워드가 있어 마지막 장면까지 보게 만듦")
    if any(term in text for term in ("funny", "comedy", "humor", "prank")):
        reasons.append("언어 장벽이 낮은 웃음 코드로 공유 가능성이 큼")

    age = published_age_days(item)
    if age is not None and age <= 10 and views >= 10_000_000:
        reasons.append("게시 직후 짧은 기간에 높은 조회수를 만든 초기 확산 속도")
    if views >= VIRAL_VIEW_THRESHOLD:
        reasons.append("1억뷰 이상으로 확장될 만큼 국가·언어를 넘어서는 즉시성이 있음")
    elif views >= 30_000_000:
        reasons.append("1억뷰 후보권에 가까운 대중적 훅과 재시청 신호가 있음")

    if not reasons and labels:
        reasons.append(f"{', '.join(labels[:2])} 요소가 명확해 피드에서 빠르게 이해됨")
    if not reasons:
        reasons.append("짧은 제목과 시각적 상황이 결합되어 스크롤 중 멈춰 볼 가능성이 큼")

    return "인기 이유 " + " · ".join(reasons[:3])


def match_note_terms(item: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for note in item.get("matchNotes", []):
        note_text = clean_text(str(note))
        lower = note_text.lower()
        if ":" not in note_text or not any(marker in lower for marker in ("keyword", "signal")):
            continue
        _, values = note_text.split(":", 1)
        existing = {term.lower() for term in terms}
        for value in re.split(r"[,/]", values):
            term = clean_text(value).strip(" #")
            if term and term.lower() not in existing:
                terms.append(term)
                existing.add(term.lower())
    return terms[:5]


def popularity_reason_points(item: dict[str, Any]) -> list[str]:
    views = parse_int(item.get("viewsGained"))
    clusters = item_cluster_keys(item)
    labels = [cluster_label(key) for key in clusters if key != "other"]
    text = item_text(item).lower()
    age = published_age_days(item)
    terms = match_note_terms(item)
    region = str(item.get("regionLabel") or "Global")
    source = str(item.get("sourceName") or "ranking source")
    window = str(item.get("sourceWindow") or "trend")
    rank = item.get("sourceRank")

    if views >= VIRAL_VIEW_THRESHOLD:
        tier = "1억뷰 돌파형"
    elif views >= 30_000_000:
        tier = "1억뷰 근접 대형 확산권"
    elif views >= 10_000_000:
        tier = "중대형 급상승권"
    else:
        tier = "지역 탭 검토 후보"

    source_detail = f"{source} {window}"
    if rank:
        source_detail += f" rank {rank}"

    hook_parts: list[str] = []
    if "situation" in clusters:
        hook_parts.append("상황·반전·코미디 신호가 제목에서 바로 읽혀 결과를 확인하려는 궁금증을 만듭니다")
    if "dance" in clusters:
        hook_parts.append("음악과 동작이 중심이라 첫 프레임만으로 장르가 전달되고 따라 하기 쉽습니다")
    if "edit" in clusters:
        hook_parts.append("슬로우드·펑크·빠른 컷 편집이 분위기를 먼저 만들며 피드에서 즉시 구분됩니다")
    if "performance" in clusters:
        hook_parts.append("퍼포먼스나 스턴트성 장면은 성공 여부를 끝까지 보게 하는 긴장감이 있습니다")
    if "kpop" in clusters:
        hook_parts.append("K-pop·아이돌 파생 소재는 팬덤 반응과 챌린지 참여로 재확산되기 쉽습니다")
    if any(term in text for term in ("magic", "surprise", "saved", "reveal", "defying", "wild")):
        hook_parts.append("마술·구출·공개·놀라움 계열 키워드가 마지막 장면까지 보게 만드는 질문을 던집니다")
    if any(term in text for term in ("funny", "comedy", "humor", "prank")):
        hook_parts.append("웃음 코드는 언어 의존도가 낮아 다른 국가 피드에서도 이해되기 쉽습니다")
    if not hook_parts:
        hook_parts.append("짧은 제목과 시각적 상황이 결합되어 스크롤 중 멈춰 볼 가능성이 있습니다")

    if "dance" in clusters or "edit" in clusters:
        retention = "사운드와 동작의 루프가 맞물려 같은 구간을 다시 보게 만들고, 리믹스나 따라 하기 행동으로 이어질 수 있습니다"
    elif "situation" in clusters or "performance" in clusters:
        retention = "초반에 질문을 던지고 끝에서 결과를 회수하는 구조라 완주율과 반복 시청을 동시에 노립니다"
    elif "kpop" in clusters:
        retention = "팬덤이 댓글·공유·저장으로 반응하기 쉬워 초기 반응 속도를 키우는 데 유리합니다"
    else:
        retention = "핵심 장면을 빠르게 보여 주는 숏폼 문법이라 긴 설명 없이도 시청 판단이 가능합니다"

    if views >= VIRAL_VIEW_THRESHOLD:
        velocity = "이미 1억뷰를 넘은 사례라 클릭률, 완주율, 반복 시청, 공유 신호가 여러 지역에서 동시에 작동했을 가능성이 큽니다"
    elif views >= 30_000_000:
        velocity = "3천만뷰 이상이면 1억뷰 후보군으로 볼 수 있으며, 추가 추천 노출이나 리믹스가 붙을 때 더 크게 확장될 수 있습니다"
    elif age is not None and age <= 10 and views >= 10_000_000:
        velocity = f"게시 후 {age}일 안에 1천만뷰 이상을 만든 초기 속도가 강해 알고리즘 테스트 구간을 빠르게 통과한 신호로 볼 수 있습니다"
    elif window == "24H":
        velocity = "24H 랭킹 출처에서 잡힌 항목이라 최신 피드 반응은 있지만, 장기 확산 여부는 다음 업데이트에서 확인해야 합니다"
    else:
        velocity = "현재는 지역·소스 단위의 인기 신호가 먼저 보이며, 누적 반복 시청이 붙어야 더 큰 조회수로 커질 수 있습니다"

    keyword_detail = f"감지 키워드: {', '.join(terms)}" if terms else "감지 키워드: 제목·소스 신호 중심"
    pattern_detail = f"분석 패턴: {', '.join(labels)}" if labels else "분석 패턴: 짧은 상황 이해와 시각적 훅 중심"

    return [
        f"{region} 탭에서 {fmt_int(views)} views로 확인된 {tier} 쇼츠",
        f"{source_detail}에 포착되어 단순 검색보다 랭킹·트렌드 출처의 반응 신호가 있음",
        keyword_detail,
        *hook_parts[:3],
        retention,
        velocity,
        pattern_detail,
    ]


def popularity_reason(item: dict[str, Any]) -> str:
    return " ".join(popularity_reason_points(item))


def card_popularity_points(item: dict[str, Any]) -> list[str]:
    points = popularity_reason_points(item)
    selected = [points[0]]
    if len(points) > 2:
        selected.append(points[2])
    if len(points) > 3:
        selected.append(points[3])
    if len(points) > 6:
        selected.append(points[-2])
    return selected[:4]


RECENT_MEGA_CASE_NOTES: dict[str, list[str]] = {
    "HsKltJyJ-UI": [
        "최근 업로드 후 1억뷰를 넘긴 사례로, 제목이 바로 질문을 던져 결과를 확인하고 싶게 만듭니다.",
        "마술·코미디·두 인물 관계가 한 장면 안에서 이해되어 언어 장벽 없이 글로벌 피드로 확장되기 쉽습니다.",
        "손동작과 반전 결과가 핵심이라 첫 시청 후에도 다시 보며 트릭을 확인하는 반복 시청이 발생합니다.",
        "funny/comedy 태그가 기대값을 명확히 만들고, 짧은 상황극 구조가 끝까지 보는 완주율 신호를 만듭니다.",
    ],
    "ZdXwPHwdwhY": [
        "일본 탭에서 1억뷰를 넘긴 코미디 사례로, 표정과 행동 중심의 짧은 상황이 언어 없이도 바로 전달됩니다.",
        "제목의 funny 신호가 클릭 전 기대를 낮은 비용으로 설명하고, 결과 확인형 장면이 이탈을 줄입니다.",
        "복잡한 배경보다 인물 반응이 중심이라 모바일 화면에서 즉시 읽히고, 공유할 때 맥락 설명이 거의 필요 없습니다.",
        "웃음 포인트가 짧고 반복 가능해 같은 장면을 다시 보거나 주변 사람에게 보여 주는 행동으로 이어지기 좋습니다.",
    ],
    "tgOQlzCqc0M": [
        "Astronomia 사운드와 셔플 동작이 결합된 1억뷰 이상 댄스 사례로, 음악 훅이 시작 즉시 장르를 알려 줍니다.",
        "아이·네온·셔플이라는 시각 대비가 강해 썸네일만으로도 궁금증을 만들고 첫 프레임 흡입력이 큽니다.",
        "동작이 루프 구조와 잘 맞아 다시 보기, 따라 하기, 리믹스 가능성이 동시에 열립니다.",
        "대사보다 음악과 몸동작이 핵심이라 지역 탭을 넘어 글로벌 추천 피드에서 소비되기 쉽습니다.",
    ],
    "FWMyxmIu1Ss": [
        "Squid Game Challenge라는 글로벌 IP 신호와 공주 콘셉트의 대비가 첫 순간부터 상황을 이해시키는 사례입니다.",
        "챌린지 포맷은 결과를 끝까지 보게 만들고, 익숙한 IP는 클릭 전 설명 비용을 크게 낮춥니다.",
        "의상·게임 규칙·반응이 시각적으로 읽혀 자막이 없어도 장면의 긴장과 재미가 전달됩니다.",
        "트렌드 IP를 짧은 퍼포먼스로 재가공해 검색·추천·공유에서 모두 발견될 접점을 넓혔습니다.",
    ],
    "9Egj8PiHiak": [
        "멕시코 탭에서 1억뷰를 넘긴 코미디 사례로, 강한 행동 훅과 짧은 반응이 바로 시선을 붙잡습니다.",
        "말보다 표정·행동 중심이라 문화권이 달라도 장면의 농담을 빠르게 이해할 수 있습니다.",
        "짧은 상황형 코미디는 마지막 반응을 확인하려는 완주율과 다시 보는 행동을 동시에 만들기 쉽습니다.",
        "funny/comedy 태그와 반복 가능한 캐릭터성이 결합해 추천 피드에서 다음 노출을 받을 근거를 만듭니다.",
    ],
}


def mega_case_points(item: dict[str, Any]) -> list[str]:
    custom = RECENT_MEGA_CASE_NOTES.get(str(item.get("id")))
    if custom:
        return custom

    points = card_popularity_points(item)
    clusters = [cluster_label(key) for key in item_cluster_keys(item) if key != "other"]
    if clusters:
        points.append(f"핵심 패턴은 {', '.join(clusters[:2])}이며, 첫 장면에서 장르와 기대 보상이 빠르게 전달됩니다.")
    points.append("1억뷰 구간은 클릭률만으로 설명되기보다 완주율, 반복 시청, 공유, 지역 확장이 함께 맞물린 결과로 봐야 합니다.")
    return points[:4]


HIGHLIGHT_TERMS: list[tuple[str, str]] = [
    ("metric", "1억뷰"),
    ("metric", "3천만뷰"),
    ("metric", "1천만뷰"),
    ("metric", "조회수"),
    ("metric", "좋아요"),
    ("metric", "views"),
    ("region", "글로벌"),
    ("region", "멕시코"),
    ("region", "독일"),
    ("region", "브라질"),
    ("region", "인도네시아"),
    ("region", "아르헨티나"),
    ("region", "필리핀"),
    ("region", "스페인"),
    ("region", "이탈리아"),
    ("region", "프랑스"),
    ("region", "우즈베키스탄"),
    ("region", "알제리"),
    ("region", "카자흐스탄"),
    ("region", "베트남"),
    ("region", "KR"),
    ("region", "US"),
    ("region", "JP"),
    ("source", "Playboard"),
    ("source", "Vidirun"),
    ("source", "RedToolBox"),
    ("source", "YTTrack"),
    ("source", "Chartika"),
    ("source", "YouTube"),
    ("source", "랭킹"),
    ("source", "트렌드"),
    ("signal", "상황형 코미디·짧은 사건"),
    ("signal", "댄스·음악 챌린지"),
    ("signal", "편집·슬로우드 사운드"),
    ("signal", "스포츠·퍼포먼스 순간"),
    ("signal", "K-pop·아이돌 안무"),
    ("signal", "감지 키워드"),
    ("signal", "핵심 패턴"),
    ("signal", "분석 패턴"),
    ("signal", "반복 시청"),
    ("signal", "완주율"),
    ("signal", "공유"),
    ("signal", "리믹스"),
    ("signal", "클릭률"),
    ("signal", "클릭 유지율"),
    ("signal", "지역 확장"),
    ("signal", "댄스"),
    ("signal", "음악"),
    ("signal", "챌린지"),
    ("signal", "코미디"),
    ("signal", "magic"),
    ("signal", "dance"),
    ("signal", "challenge"),
    ("signal", "funny"),
    ("signal", "comedy"),
    ("signal", "slowed"),
    ("signal", "edit"),
]

HIGHLIGHT_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\s*(?:views|뷰))?|\d+(?:%p|개|뷰)")


def highlight_term_pattern(term: str) -> str:
    pattern = re.escape(escape(term))
    if term.isascii() and any(char.isalpha() for char in term):
        return rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
    return pattern


def highlight_text(text: Any) -> str:
    safe = escape(str(text))
    spans: list[tuple[int, int, str]] = []
    for class_name, term in HIGHLIGHT_TERMS:
        term_pattern = highlight_term_pattern(term)
        for match in re.finditer(term_pattern, safe, flags=re.I):
            spans.append((match.start(), match.end(), class_name))
    for match in HIGHLIGHT_NUMBER_RE.finditer(safe):
        spans.append((match.start(), match.end(), "metric"))

    selected: list[tuple[int, int, str]] = []
    occupied_until = -1
    for start, end, class_name in sorted(spans, key=lambda span: (span[0], -(span[1] - span[0]))):
        if start < occupied_until:
            continue
        selected.append((start, end, class_name))
        occupied_until = end

    if not selected:
        return safe

    output: list[str] = []
    cursor = 0
    for start, end, class_name in selected:
        output.append(safe[cursor:start])
        output.append(f'<strong class="text-mark text-mark--{class_name}">{safe[start:end]}</strong>')
        cursor = end
    output.append(safe[cursor:])
    return "".join(output)


def render_points(points: list[str]) -> str:
    return "\n".join(f"<li>{highlight_text(point)}</li>" for point in points)


def source_label(item: dict[str, Any]) -> str:
    label = clean_text(str(item.get("sourceName") or "ranking source"))
    window = clean_text(str(item.get("sourceWindow") or ""))
    rank = item.get("sourceRank")
    if window:
        label += f" {window}"
    if rank:
        label += f" rank {rank}"
    return label


def render_mega_case_card(item: dict[str, Any]) -> str:
    source_url = str(item.get("sourceUrl") or item.get("shortsUrl") or "#")
    return f"""
        <article class="mega-case-card">
          <a class="mega-case-thumb" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">
            <img src="{escape(item.get('thumbnail') or thumbnail_url(item['id']))}" alt="{escape(str(item.get('title', 'YouTube Shorts thumbnail')))}">
          </a>
          <div class="mega-case-body">
            <h3><a href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">{escape(compact_title(str(item.get('title', '')), 72))}</a></h3>
            <div class="mega-case-meta">
              <span><b>조회수</b><strong class="text-mark text-mark--metric">{fmt_int(item.get('viewsGained'))}</strong></span>
              <span><b>좋아요</b><strong class="text-mark text-mark--metric">{fmt_count(item.get('likeCount'))}</strong></span>
            </div>
            <a class="mega-case-source" href="{escape(source_url)}" target="_blank" rel="noopener">{highlight_text('근거: ' + source_label(item))}</a>
            <ul class="mega-case-points">{render_points(mega_case_points(item))}</ul>
          </div>
        </article>"""


def render_mega_view_analysis(items: list[dict[str, Any]]) -> str:
    mega_items = [item for item in items if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD]
    near_items = [
        item
        for item in sorted(items, key=lambda row: parse_int(row.get("viewsGained")), reverse=True)
        if parse_int(item.get("viewsGained")) >= 30_000_000
    ][:6]
    analysis_items = mega_items or near_items or sorted(items, key=lambda row: parse_int(row.get("viewsGained")), reverse=True)[:6]
    counts = cluster_counts(analysis_items)
    top_patterns = [
        cluster_label(key)
        for key, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
        if count and key != "other"
    ][:3]
    top_pattern_text = ", ".join(top_patterns) if top_patterns else "상황 이해가 빠른 짧은 장면"

    mega_summary = (
        f"현재 표시 영상 중 {len(mega_items)}개가 1억뷰 이상입니다."
        if mega_items
        else "현재 표시 영상에는 1억뷰 이상이 많지 않아, 3천만뷰 이상 근접 사례까지 함께 봅니다."
    )
    top_line = ""
    if analysis_items:
        top = max(analysis_items, key=lambda row: parse_int(row.get("viewsGained")))
        top_line = (
            f"가장 강한 사례는 {compact_title(str(top.get('title', '')), 54)}"
            f" ({fmt_int(top.get('viewsGained'))} views)입니다."
        )

    principles = [
        "초반 1초 안에 무슨 일이 벌어지는지 보여 주고, 설명 없이도 이해되는 장면이 유리합니다.",
        "댄스·마술·스턴트·짧은 갈등처럼 끝을 확인하고 싶은 구조가 반복 시청을 만듭니다.",
        "슬로우드 사운드, 펑크, 익숙한 음악, 강한 리듬은 같은 영상을 여러 번 보게 만드는 접착제 역할을 합니다.",
        "자막이나 언어 의존도가 낮을수록 국가별 탭을 넘어 글로벌 피드에서 확장되기 쉽습니다.",
        "1억뷰는 조회수 하나의 폭발보다 클릭 유지율, 반복 시청, 공유, 리믹스 가능성이 동시에 맞을 때 나옵니다.",
    ]
    principle_items = render_points(principles)
    hero_points = [mega_summary]
    if top_line:
        hero_points.append(top_line)
    hero_points.append(f"현재 데이터에서는 {top_pattern_text} 신호가 특히 강합니다.")
    hero_point_items = render_points(hero_points)

    recent_mega_items = sorted(
        mega_items,
        key=lambda row: (parse_date(row.get("publishedAt")) or datetime.min.date(), parse_int(row.get("viewsGained"))),
        reverse=True,
    )[:3]
    recent_case_cards = "\n".join(render_mega_case_card(item) for item in recent_mega_items)
    recent_case_section = (
        f"""
      <div class="mega-case-section">
        <div class="mega-section-heading">
          <h3>최근 1억뷰 달성 사례</h3>
        </div>
        <div class="mega-case-list">{recent_case_cards}</div>
      </div>"""
        if recent_case_cards
        else ""
    )

    examples = "\n".join(
        f"""
        <article class="mega-example">
          <a class="mega-example-thumb" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">
            <img src="{escape(item.get('thumbnail') or thumbnail_url(item['id']))}" alt="{escape(str(item.get('title', 'YouTube Shorts thumbnail')))}">
          </a>
          <div class="mega-example-body">
            <a class="mega-example-title" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">{escape(compact_title(str(item.get('title', '')), 64))}</a>
            <span>{highlight_text(f"{fmt_int(item.get('viewsGained'))} views")}</span>
            <ul>{render_points(popularity_reason_points(item)[:4])}</ul>
          </div>
        </article>"""
        for item in analysis_items
    )

    return f"""
    <section class="region-panel mega-panel" data-region-panel="mega" aria-label="1억뷰 분석">
      <div class="mega-hero">
        <div>
          <h2>1억뷰 분석</h2>
          <ul class="mega-hero-points">{hero_point_items}</ul>
        </div>
        <strong>{len(mega_items)}</strong>
      </div>
{recent_case_section}
      <div class="mega-grid">
        <div class="mega-block">
          <h3>왜 1억뷰가 나오는가</h3>
          <ul>{principle_items}</ul>
        </div>
        <div class="mega-block">
          <h3>현재 데이터의 1억뷰·근접 사례</h3>
          <div class="mega-examples">{examples}</div>
        </div>
      </div>
    </section>"""


def render_trend_analysis(items: list[dict[str, Any]]) -> str:
    dated_items = [(item, parse_date(item.get("publishedAt"))) for item in items]
    dated_items = [(item, published) for item, published in dated_items if published]
    if not dated_items:
        return ""

    latest_date = max(published for _, published in dated_items)
    cutoff = latest_date - timedelta(days=6)
    recent = [item for item, published in dated_items if published >= cutoff]
    previous = [item for item, published in dated_items if published < cutoff]
    analysis_base = recent or [item for item, _ in dated_items]

    recent_key, recent_count = top_cluster(analysis_base)
    recent_counts = cluster_counts(analysis_base)
    previous_counts = cluster_counts(previous)
    comparison = []
    if previous:
        for key in recent_counts:
            delta = trend_ratio(recent_counts, key, len(analysis_base)) - trend_ratio(previous_counts, key, len(previous))
            comparison.append((delta, key))
    comparison.sort(reverse=True)
    rising_delta, rising_key = comparison[0] if comparison else (0.0, recent_key)

    region_counts: dict[str, int] = {}
    for item in analysis_base:
        region_counts[item["region"]] = region_counts.get(item["region"], 0) + 1
    region_focus = sorted(region_counts.items(), key=lambda pair: pair[1], reverse=True)[:3]
    region_text = ", ".join(f"{REGION_BY_KEY[key]['label']} {count}개" for key, count in region_focus)

    top_view_item = max(analysis_base, key=lambda item: parse_int(item.get("viewsGained")))
    top_view_clusters = ", ".join(cluster_label(key) for key in item_cluster_keys(top_view_item)[:2])
    if not top_view_clusters:
        top_view_clusters = "복합 트렌드"

    if rising_delta >= 0.08:
        shift_sentence = f"이전 누적 대비 {cluster_label(rising_key)} 비중이 약 {round(rising_delta * 100)}%p 높아졌습니다."
    elif rising_delta <= -0.08:
        shift_sentence = f"최근 표본에서는 {cluster_label(rising_key)} 비중이 이전보다 낮아져, 관심이 다른 포맷으로 분산됩니다."
    else:
        shift_sentence = "최근 표본은 이전 누적과 큰 급변보다는 기존 강세 포맷이 유지되는 흐름입니다."

    recent_range = f"{cutoff.isoformat()}~{latest_date.isoformat()}"
    notes = [
        f"최근 {recent_range} 게시 영상 {len(analysis_base)}개 기준으로 {cluster_label(recent_key)} 신호가 가장 큽니다.",
        shift_sentence,
        f"지역별로는 {region_text or '여러 지역'}에서 새 게시물이 많이 잡히며, 지역 탭마다 코미디·댄스·편집형 비중이 다르게 나타납니다.",
        f"조회수 상위 최근 사례는 {compact_title(str(top_view_item.get('title', '')))} ({fmt_int(top_view_item.get('viewsGained'))} views)이며, {top_view_clusters} 쪽 신호가 강합니다.",
    ]

    note_items = render_points(notes)
    top_badges = "\n".join(
        f"<li>{highlight_text(f'{cluster_label(key)} {count}')}</li>"
        for key, count in sorted(recent_counts.items(), key=lambda pair: pair[1], reverse=True)[:4]
        if count
    )
    return f"""
    <section class="trend-brief" aria-label="trend analysis">
      <div class="trend-heading">
        <strong>트렌드 분석</strong>
        <ul class="trend-meta">
          <li>{highlight_text(f'{len(items)}개 표시 영상')}</li>
          <li>{highlight_text(f'{MIN_DISPLAY_VIEWS:,}뷰 이상')}</li>
        </ul>
      </div>
      <ul class="trend-badges">{top_badges}</ul>
      <ul class="trend-notes">{note_items}</ul>
    </section>"""


def render_card(item: dict[str, Any], index: int) -> str:
    reason_items = render_points(card_popularity_points(item))
    return f"""
      <article class="short-card">
        <a class="thumb-link" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener" aria-label="Open {escape(item['title'])} on YouTube Shorts">
          <img src="{escape(item['thumbnail'])}" alt="{escape(item['title'])} thumbnail" loading="lazy">
          <span class="rank">#{index}</span>
        </a>
        <div class="short-body">
          <h2>{escape(item['title'])}</h2>
          <div class="stats-row">
            <span><b>조회수</b><strong class="text-mark text-mark--metric">{fmt_count(item.get('viewsGained'))}</strong></span>
            <span><b>좋아요</b><strong class="text-mark text-mark--metric">{fmt_count(item.get('likeCount'))}</strong></span>
          </div>
          <div class="popularity" aria-label="인기 이유">
            <strong>인기 이유</strong>
            <ul>{reason_items}</ul>
          </div>
        </div>
      </article>"""


def group_items_by_region(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {region["key"]: [] for region in REGIONS}
    seen: set[str] = set()
    for item in order_items_newest_first(items):
        video_id = item.get("id")
        if not video_id or video_id in seen or not is_displayable(item):
            continue
        seen.add(video_id)
        grouped[item["region"]].append(item)
    return grouped


def render_index(items: list[dict[str, Any]]) -> str:
    items = order_items_newest_first(items)
    grouped = group_items_by_region(items)
    display_items = [item for region_items in grouped.values() for item in region_items]
    trend_analysis = render_trend_analysis(display_items)
    mega_count = sum(1 for item in display_items if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD)

    tab_parts = []
    for region in REGIONS:
        tab_parts.append(
            f"""<button class="tab-button{' active' if region['key'] == 'global' else ''}" type="button" data-region-tab="{region['key']}">{escape(region['label'])}<span>{len(grouped[region['key']])}</span></button>"""
        )
        if region["key"] == "global":
            tab_parts.append(
                f"""<button class="tab-button" type="button" data-region-tab="mega">1억뷰 분석<span>{mega_count}</span></button>"""
            )
    tab_buttons = "\n".join(tab_parts)

    panels = [render_mega_view_analysis(display_items)]
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
        f'<li><a href="{escape(url)}" target="_blank" rel="noopener">{highlight_text(name)}</a></li>'
        for name, url in source_links(display_items)
    )

    data_json = escape(json.dumps(items, ensure_ascii=False), quote=False)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shorts</title>
  <meta name="description" content="지역별 인기 YouTube Shorts 후보 모음">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    @font-face {{
      font-family: "SOK500";
      src: local("SamsungOneKorean500"), local("SamsungOneKorean 500");
      font-weight: 500;
      font-style: normal;
      font-display: swap;
    }}
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
      --tab-red: #dc2626;
      --tab-red-dark: #991b1b;
      --tab-red-soft: #fee2e2;
      --tab-red-wash: #fff5f5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Sans KR", "SOK500", "Malgun Gothic", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--wash);
      color: var(--ink);
      letter-spacing: 0;
      overflow-x: hidden;
    }}
    a {{ color: inherit; }}
    .text-mark {{
      display: inline;
      border-radius: 5px;
      padding: 0 3px;
      font-weight: 900;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .text-mark--metric {{
      background: #fee2e2;
      color: #b91c1c;
    }}
    .text-mark--region {{
      background: #ccfbf1;
      color: #0f766e;
    }}
    .text-mark--source {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .text-mark--signal {{
      background: #fef3c7;
      color: #a16207;
    }}
    .shell {{
      width: calc(100% - 28px);
      max-width: 100%;
      margin: 0 auto;
    }}
    header {{
      border-bottom: 1px solid #fecaca;
      background: var(--tab-red-wash);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      overflow: visible;
      padding: 10px 0;
    }}
    .tab-button {{
      border: 1px solid var(--tab-red);
      border-radius: 999px;
      background: var(--surface);
      color: var(--tab-red-dark);
      padding: 7px 9px;
      font: inherit;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }}
    .tab-button span {{
      min-width: 22px;
      padding: 2px 6px;
      border-radius: 999px;
      background: var(--tab-red-soft);
      color: var(--tab-red-dark);
      font-size: 12px;
      transition: background 0.18s ease, color 0.18s ease;
    }}
    .tab-button:hover {{
      background: var(--tab-red-dark);
      border-color: var(--tab-red-dark);
      color: white;
      box-shadow: 0 4px 14px rgba(220, 38, 38, 0.24);
      transform: translateY(-1px);
    }}
    .tab-button:hover span {{
      background: white;
      color: var(--tab-red-dark);
    }}
    .tab-button.active {{
      background: var(--tab-red);
      border-color: var(--tab-red);
      color: white;
    }}
    .tab-button.active:hover {{
      background: var(--tab-red-dark);
      border-color: var(--tab-red-dark);
    }}
    .tab-button.active span {{
      background: rgba(255, 255, 255, 0.18);
      color: white;
    }}
    .tab-button.active:hover span {{
      background: white;
      color: var(--tab-red-dark);
    }}
    main {{
      padding: 14px 0 44px;
    }}
    .trend-brief {{
      border-bottom: 1px solid var(--line);
      padding: 2px 0 16px;
      margin-bottom: 16px;
    }}
    .trend-heading {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .trend-heading > strong {{
      font-size: 15px;
      line-height: 1.3;
    }}
    .trend-meta {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      font-weight: 700;
    }}
    .trend-meta li {{
      white-space: nowrap;
    }}
    .trend-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0 0 10px;
      padding-left: 18px;
      list-style: disc;
    }}
    .trend-badges li {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: #344054;
      padding: 5px 8px 5px 6px;
      font-size: 11px;
      font-weight: 700;
      margin-left: 14px;
    }}
    .trend-notes {{
      margin: 0;
      padding-left: 18px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 10px 14px;
    }}
    .trend-notes li {{
      border-left: 3px solid var(--accent);
      padding-left: 10px;
      color: #344054;
      font-size: 13px;
      line-height: 1.55;
    }}
    .mega-panel {{
      background: transparent;
    }}
    .mega-hero {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 16px;
      margin-bottom: 10px;
    }}
    .mega-hero h2 {{
      margin: 0 0 8px;
      font-size: 20px;
      line-height: 1.25;
    }}
    .mega-hero-points {{
      margin: 0;
      padding-left: 18px;
      color: #344054;
      font-size: 14px;
      line-height: 1.65;
    }}
    .mega-hero-points li + li {{
      margin-top: 3px;
    }}
    .mega-hero > strong {{
      min-width: 48px;
      border-radius: 8px;
      background: var(--ink);
      color: white;
      padding: 10px;
      text-align: center;
      font-size: 22px;
      line-height: 1;
    }}
    .mega-case-section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 14px;
      margin-bottom: 12px;
    }}
    .mega-section-heading {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 14px;
      margin-bottom: 12px;
    }}
    .mega-section-heading h3 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.3;
    }}
    .mega-case-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 14px;
    }}
    .mega-case-card {{
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 13px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 10px;
    }}
    .mega-case-thumb {{
      display: block;
      width: 100%;
      aspect-ratio: 9 / 16;
      overflow: hidden;
      border-radius: 6px;
      background: #dbe4ee;
    }}
    .mega-case-thumb img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .mega-case-body h3 {{
      margin: 0 0 8px;
      font-size: 14px;
      line-height: 1.35;
    }}
    .mega-case-body h3 a {{
      color: var(--ink);
      text-decoration: none;
    }}
    .mega-case-body h3 a:hover {{
      color: var(--tab-red);
      text-decoration: underline;
    }}
    .mega-case-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 7px;
    }}
    .mega-case-meta span {{
      border-radius: 999px;
      background: var(--tab-red-wash);
      color: var(--tab-red-dark);
      padding: 4px 7px;
      font-size: 11px;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }}
    .mega-case-meta b {{
      margin-right: 4px;
      color: #7f1d1d;
    }}
    .mega-case-meta .text-mark,
    .stats-row .text-mark {{
      background: transparent;
      color: var(--tab-red-dark);
      padding: 0;
    }}
    .mega-case-source {{
      display: inline-block;
      margin-bottom: 8px;
      color: var(--focus);
      font-size: 11px;
      font-weight: 800;
      line-height: 1.35;
      text-decoration: none;
    }}
    .mega-case-source:hover {{
      text-decoration: underline;
    }}
    .mega-case-points {{
      margin: 0;
      padding-left: 17px;
      color: #344054;
      font-size: 12px;
      line-height: 1.55;
    }}
    .mega-case-points li + li {{
      margin-top: 4px;
    }}
    .mega-grid {{
      display: grid;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
      gap: 12px;
    }}
    .mega-block {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 14px;
    }}
    .mega-block h3 {{
      margin: 0 0 10px;
      font-size: 15px;
      line-height: 1.3;
    }}
    .mega-block ul {{
      margin: 0;
      padding-left: 18px;
      color: #344054;
      font-size: 13px;
      line-height: 1.6;
    }}
    .mega-examples {{
      display: grid;
      gap: 10px;
    }}
    .mega-example {{
      border-top: 1px solid var(--line);
      padding-top: 10px;
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }}
    .mega-example:first-child {{
      border-top: 0;
      padding-top: 0;
    }}
    .mega-example-thumb {{
      display: block;
      aspect-ratio: 9 / 16;
      overflow: hidden;
      border-radius: 7px;
      background: #d8e0ea;
    }}
    .mega-example-thumb img {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .mega-example-title {{
      display: block;
      color: var(--focus);
      font-size: 13px;
      font-weight: 800;
      line-height: 1.35;
      text-decoration: none;
    }}
    .mega-example-title:hover {{
      text-decoration: underline;
    }}
    .mega-example span {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }}
    .mega-example ul {{
      margin: 6px 0 0;
      padding-left: 17px;
      color: #344054;
      font-size: 12px;
      line-height: 1.5;
    }}
    .mega-example li + li {{
      margin-top: 3px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
      gap: 18px;
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
      border-radius: 16px;
      overflow: hidden;
      display: block;
      min-height: 100%;
      padding: 0;
      box-shadow: 0 6px 22px rgba(15, 23, 42, 0.08);
      transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
    }}
    .short-card:hover {{
      transform: translateY(-4px);
      border-color: rgba(220, 38, 38, 0.38);
      box-shadow: 0 14px 36px rgba(220, 38, 38, 0.14);
    }}
    .thumb-link {{
      position: relative;
      display: block;
      width: 100%;
      aspect-ratio: 9 / 16;
      background: #dbe4ee;
      overflow: hidden;
      border-radius: 0;
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
      min-width: 26px;
      height: 26px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.72);
      color: white;
      border-radius: 8px;
      padding: 0 7px;
      font-size: 11px;
      font-weight: 800;
    }}
    .short-body {{
      min-width: 0;
      padding: 10px 11px 12px;
      display: flex;
      flex-direction: column;
      gap: 7px;
    }}
    .short-card h2 {{
      margin: 0;
      font-size: 12.5px;
      line-height: 1.38;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      min-height: 2.75em;
    }}
    .short-card h2 a {{
      text-decoration: none;
    }}
    .short-card h2 a:hover {{
      text-decoration: underline;
    }}
    .stats-row {{
      margin: 0;
      color: var(--muted);
      font-size: 10.5px;
      line-height: 1.38;
    }}
    .stats-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px 8px;
    }}
    .stats-row span {{
      border: 0;
      border-radius: 0;
      background: transparent;
      color: #991b1b;
      padding: 0;
      font-weight: 800;
      min-width: 0;
    }}
    .stats-row b {{
      display: inline;
      color: #667085;
      font-size: 10px;
      line-height: 1.15;
      margin-right: 3px;
    }}
    .popularity {{
      color: #92400e;
      border: 0;
      border-left: 2px solid #f97316;
      border-radius: 8px;
      background: rgba(255, 140, 0, 0.08);
      padding: 7px 8px;
      display: block;
    }}
    .popularity > strong {{
      display: block;
      color: #b45309;
      background: transparent;
      font-size: 10.5px;
      line-height: 1.2;
      font-weight: 800;
      letter-spacing: 0;
      margin-bottom: 4px;
    }}
    .popularity ul {{
      margin: 0;
      padding-left: 14px;
      font-size: 10.5px;
      line-height: 1.45;
    }}
    .popularity li {{
      margin: 0 0 4px;
      padding-left: 1px;
    }}
    .popularity li:last-child {{
      margin-bottom: 0;
    }}
    .source-panel {{
      margin-top: 26px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    .source-panel > strong {{
      display: block;
      color: #344054;
      font-size: 13px;
      font-weight: 800;
      margin-bottom: 8px;
    }}
    .source-links {{
      margin: 0;
      padding-left: 18px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 6px 18px;
    }}
    .source-panel a {{
      color: var(--focus);
      text-decoration: none;
      border-bottom: 1px solid rgba(29, 78, 216, 0.25);
    }}
    .footer-update {{
      margin: 18px 0 0;
      padding: 14px 0 4px;
      border-top: 1px solid var(--line);
      color: #475467;
      font-size: 13px;
      font-weight: 800;
      text-align: center;
    }}
    @media (max-width: 720px) {{
      .shell {{ width: calc(100% - 16px); max-width: 100%; }}
      .tabs {{ gap: 5px; padding: 8px 0; }}
      .tab-button {{ padding: 6px 8px; font-size: 11px; gap: 5px; }}
      .tab-button span {{ min-width: 18px; padding: 1px 5px; font-size: 10px; }}
      .trend-heading {{ align-items: flex-start; flex-direction: column; gap: 4px; }}
      .trend-meta li {{ white-space: normal; }}
      .mega-grid {{ grid-template-columns: 1fr; }}
      .mega-hero {{ flex-direction: column; }}
      .mega-section-heading {{ flex-direction: column; align-items: flex-start; gap: 5px; }}
      .mega-case-list {{ grid-template-columns: 1fr; }}
      .mega-case-card {{ grid-template-columns: 96px minmax(0, 1fr); }}
      .mega-example {{ grid-template-columns: 78px minmax(0, 1fr); gap: 10px; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
      .short-body {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="shell">
      <nav class="tabs" aria-label="region tabs">
        {tab_buttons}
      </nav>
    </div>
  </header>
  <main class="shell">
{trend_analysis}
{''.join(panels)}
    <section class="source-panel" aria-label="sources">
      <strong>연결 소스</strong>
      <ul class="source-links">{links}</ul>
    </section>
    <div class="footer-update">업데이트 {escape(fmt_footer_update(os.environ.get("SITE_UPDATED_AT")))}</div>
  </main>
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
        needed_regions = regions_needing_search(candidates, args.max_new)
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            print("warning: yt-dlp is not installed; skipping YouTube search queries", file=sys.stderr)
        else:
            if needed_regions:
                print(
                    "ranking sources need YouTube search fallback for: "
                    + ", ".join(region["label"] for region in REGIONS if region["key"] in needed_regions),
                    file=sys.stderr,
                )
                candidates.extend(collect_youtube_search(collected_at, needed_regions))
            else:
                print("ranking sources filled every region; skipping YouTube search fallback", file=sys.stderr)
        merged = merge_items(existing, candidates, args.max_new)
        try:
            import yt_dlp  # noqa: F401
        except Exception:
            print("warning: yt-dlp is not installed; skipping publish-date enrichment", file=sys.stderr)
        else:
            enrich_video_metadata(merged)
        write_data(merged)

    INDEX_PATH.write_text(render_index(merged), encoding="utf-8")
    print(f"rendered {INDEX_PATH} with {len(merged)} shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
