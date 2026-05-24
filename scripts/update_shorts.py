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
INSIGHTS_PATH = ROOT / "insights-data.json"
INDEX_PATH = ROOT / "index.html"

KST = timezone(timedelta(hours=9))

REGIONS = [
    {"key": "global", "label": "글로벌", "queries": [
        "#shorts dance challenge music trend",
        "#shorts slowed dance edit",
        "#shorts cute dance one person music",
    ]},
    {"key": "kr", "label": "대한민국", "queries": [
        "#shorts 댄스 음악 챌린지",
        "한국 쇼츠 댄스 음악 트렌드",
    ]},
    {"key": "us", "label": "미국", "queries": [
        "#shorts dance challenge music USA",
        "US trending shorts dance music",
    ]},
    {"key": "jp", "label": "일본", "queries": [
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

COUNTRY_LABEL_ALIASES = {
    "KR": "대한민국",
    "US": "미국",
    "JP": "일본",
}


def region_label_for_key(key: Any) -> str:
    region = REGION_BY_KEY.get(str(key or "global"))
    return str(region["label"]) if region else str(REGION_BY_KEY["global"]["label"])


def normalize_country_labels(text: Any) -> str:
    output = str(text)
    for short_label, country_label in COUNTRY_LABEL_ALIASES.items():
        output = re.sub(rf"(?<![A-Za-z0-9]){re.escape(short_label)}(?![A-Za-z0-9])", country_label, output)
    return output


def item_region_label(item: dict[str, Any]) -> str:
    return region_label_for_key(item.get("region") or "global")

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

PLAYBOARD_WINDOWS = (
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("total", "All-time"),
)

PLAYBOARD_SOURCES = [
    {
        "name": f"Playboard Shorts {label} - {REGION_BY_KEY[region]['label']}",
        "page": f"https://playboard.co/chart/short/most-viewed-all-videos-in-{slug}-{window}",
        "window": window,
        "region": region,
    }
    for region, slug in PLAYBOARD_REGION_SLUGS.items()
    for window, label in PLAYBOARD_WINDOWS
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

TUBETRENDING_SOURCES = [
    {
        "name": "TubeTrending Most Viewed New Shorts",
        "page": "https://www.tubetrending.com/?duration=shorts&lang=en",
        "window": "48H",
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

YOUTUBE_API_REGION_CODES = {
    "global": "",
    "kr": "KR",
    "us": "US",
    "jp": "JP",
    "mx": "MX",
    "de": "DE",
    "br": "BR",
    "id": "ID",
    "ar": "AR",
    "ph": "PH",
    "es": "ES",
    "it": "IT",
    "fr": "FR",
    "uz": "UZ",
    "dz": "DZ",
    "kz": "KZ",
    "vn": "VN",
}

RANKING_SOURCE_LIMIT = int(os.environ.get("RANKING_SOURCE_LIMIT", "36"))
YT_SEARCH_LIMIT = int(os.environ.get("YT_SEARCH_LIMIT", "16"))
YOUTUBE_API_SEARCH_LIMIT = int(os.environ.get("YOUTUBE_API_SEARCH_LIMIT", "8"))
YOUTUBE_API_DETAILS_LIMIT = int(os.environ.get("YOUTUBE_API_DETAILS_LIMIT", "1000"))
YOUTUBE_API_RECENT_DAYS = int(os.environ.get("YOUTUBE_API_RECENT_DAYS", "30"))
MIN_DISPLAY_VIEWS = int(os.environ.get("MIN_DISPLAY_VIEWS", "10000"))
YOUTUBE_API_MIN_DISPLAY_VIEWS = int(os.environ.get("YOUTUBE_API_MIN_DISPLAY_VIEWS", "10000"))
PUBLISHED_METADATA_LIMIT = int(os.environ.get("PUBLISHED_METADATA_LIMIT", "500"))
YT_DLP_SEARCH_TIMEOUT_SECONDS = int(os.environ.get("YT_DLP_SEARCH_TIMEOUT_SECONDS", "60"))
YT_DLP_METADATA_TIMEOUT_SECONDS = int(os.environ.get("YT_DLP_METADATA_TIMEOUT_SECONDS", "180"))
SKIP_YT_DLP_METADATA = os.environ.get("SKIP_YT_DLP_METADATA", "").strip().lower() in {"1", "true", "yes"}
VIRAL_VIEW_THRESHOLD = int(os.environ.get("VIRAL_VIEW_THRESHOLD", "100000000"))
VIRAL_NEW_ITEMS_LIMIT = int(os.environ.get("VIRAL_NEW_ITEMS_LIMIT", "100"))
VIRAL_DISPLAY_LIMIT = int(os.environ.get("VIRAL_DISPLAY_LIMIT", "48"))
SHORTS_MAX_DURATION_SECONDS = int(os.environ.get("SHORTS_MAX_DURATION_SECONDS", "39"))
SHORTS_MIN_ASPECT_RATIO = float(os.environ.get("SHORTS_MIN_ASPECT_RATIO", "0.48"))
SHORTS_MAX_ASPECT_RATIO = float(os.environ.get("SHORTS_MAX_ASPECT_RATIO", "0.64"))
INSIGHT_HISTORY_LIMIT = int(os.environ.get("INSIGHT_HISTORY_LIMIT", "14"))
LIKE_POPULARITY_WEIGHT = int(os.environ.get("LIKE_POPULARITY_WEIGHT", "85"))

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


def read_insights() -> list[dict[str, Any]]:
    if not INSIGHTS_PATH.exists():
        return []
    try:
        payload = json.loads(INSIGHTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def write_insights(snapshots: list[dict[str, Any]]) -> None:
    INSIGHTS_PATH.write_text(
        json.dumps(snapshots[:INSIGHT_HISTORY_LIMIT], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def content_signature(item: dict[str, Any]) -> str:
    title = clean_text(str(item.get("title") or "")).lower()
    signature = re.sub(r"\W+", " ", title, flags=re.UNICODE).strip()
    if len(signature) >= 12:
        return f"title:{signature}"
    return f"id:{item.get('id') or ''}"


def text_signature(value: Any) -> str:
    return re.sub(r"\W+", " ", clean_text(str(value)).lower(), flags=re.UNICODE).strip()


def unique_texts(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        signature = text_signature(value)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        unique.append(value)
    return unique


def bulletize_text(value: Any) -> str:
    text = clean_text(str(value)).replace("...", "…")
    replacements = [
        ("확인해야 합니다", "확인 필요"),
        ("점검해야 합니다", "점검 필요"),
        ("봐야 합니다", "봐야 함"),
        ("작동했을 가능성이 큽니다", "작동 가능성 큼"),
        ("가능성이 큽니다", "가능성 큼"),
        ("설명 비용이 거의 필요 없습니다", "설명 비용 낮음"),
        ("맥락 설명이 거의 필요 없습니다", "맥락 설명 거의 불필요"),
        ("필요 없습니다", "불필요"),
        ("보여 주고", "제시하고"),
        ("보여 줍니다", "제시"),
        ("알려 줍니다", "전달"),
        ("만들어 줍니다", "만듦"),
        ("만듭니다", "만듦"),
        ("나옵니다", "나옴"),
        ("나타납니다", "나타남"),
        ("잡힙니다", "잡힘"),
        ("남깁니다", "남김"),
        ("던집니다", "던짐"),
        ("노립니다", "노림"),
        ("이어집니다", "이어짐"),
        ("열립니다", "열림"),
        ("줄입니다", "줄임"),
        ("낮춥니다", "낮춤"),
        ("붙잡습니다", "붙잡음"),
        ("유리합니다", "유리"),
        ("발생합니다", "발생"),
        ("전달됩니다", "전달됨"),
        ("이해됩니다", "이해됨"),
        ("확장됩니다", "확장됨"),
        ("구분됩니다", "구분됨"),
        ("분산됩니다", "분산됨"),
        ("반영합니다", "반영"),
        ("우선합니다", "우선"),
        ("시도합니다", "시도"),
        ("확인합니다", "확인"),
        ("있습니다", "있음"),
        ("없습니다", "없음"),
        ("쉽습니다", "쉬움"),
        ("어렵습니다", "어려움"),
        ("강합니다", "강함"),
        ("큽니다", "큼"),
        ("작습니다", "작음"),
        ("좋습니다", "좋음"),
        ("넓혔습니다", "넓힘"),
        ("입니다", "임"),
        ("합니다", "함"),
        ("됩니다", "됨"),
    ]
    for before, after in replacements:
        text = text.replace(before, after)
    text = re.sub(r"([가-힣]+)졌습니다", r"\1짐", text)
    text = re.sub(r"([가-힣]+)았습니다", r"\1음", text)
    text = re.sub(r"([가-힣]+)었습니다", r"\1음", text)
    text = text.replace("이며,", " /")
    text = text.replace("이고,", " /")
    text = text.replace("라면,", "라면 /")
    text = re.sub(r"\s*\.\s+", " / ", text)
    text = re.sub(r"[.。]+$", "", text)
    text = re.sub(r"\s*/\s*", " / ", text)
    text = re.sub(r"(?<=\d)\s*/\s*(?=\d)", "/", text)
    text = re.sub(r"(?:\s*/\s*){2,}", " / ", text)
    text = re.sub(r"\s+", " ", text).strip(" .。")
    return text


def unique_content_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_signatures: set[str] = set()
    for item in items:
        video_id = str(item.get("id") or "")
        signature = content_signature(item)
        if not video_id or video_id in seen_ids or signature in seen_signatures:
            continue
        seen_ids.add(video_id)
        seen_signatures.add(signature)
        unique.append(item)
    return unique


def dedupe_accumulated_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return unique_content_items(order_items_newest_first(items))


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


def fmt_duration(value: Any) -> str:
    seconds = parse_int(value)
    if seconds <= 0:
        return "--:--"
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes}:{remainder:02d}"


def parse_iso8601_duration(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        text,
    )
    if not match:
        return parse_int(text)
    days = parse_int(match.group("days"))
    hours = parse_int(match.group("hours"))
    minutes = parse_int(match.group("minutes"))
    seconds = parse_int(match.group("seconds"))
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def video_dimensions_from_payload(payload: dict[str, Any]) -> tuple[int, int]:
    width = parse_int(payload.get("width"))
    height = parse_int(payload.get("height"))
    if width and height:
        return width, height

    resolution = str(payload.get("resolution") or "")
    match = re.search(r"(\d{2,5})\s*x\s*(\d{2,5})", resolution)
    if match:
        return parse_int(match.group(1)), parse_int(match.group(2))

    best: tuple[int, int] = (0, 0)
    best_area = 0
    for fmt in payload.get("formats") or []:
        fmt_width = parse_int(fmt.get("width"))
        fmt_height = parse_int(fmt.get("height"))
        if not fmt_width or not fmt_height:
            continue
        if fmt.get("vcodec") == "none":
            continue
        area = fmt_width * fmt_height
        if area > best_area:
            best = (fmt_width, fmt_height)
            best_area = area
    return best


def is_9x16_short_shape(duration: Any, width: Any, height: Any) -> bool:
    duration_value = parse_int(duration)
    width_value = parse_int(width)
    height_value = parse_int(height)
    if duration_value <= 0 or duration_value > SHORTS_MAX_DURATION_SECONDS:
        return False
    if width_value <= 0 or height_value <= 0 or height_value <= width_value:
        return False
    ratio = width_value / height_value
    return SHORTS_MIN_ASPECT_RATIO <= ratio <= SHORTS_MAX_ASPECT_RATIO


def set_shape_metadata(item: dict[str, Any], *, duration: Any = None, width: Any = None, height: Any = None) -> None:
    duration_value = parse_int(duration if duration is not None else item.get("duration"))
    width_value = parse_int(width if width is not None else item.get("width"))
    height_value = parse_int(height if height is not None else item.get("height"))
    if duration_value:
        item["duration"] = duration_value
    if width_value and height_value:
        item["width"] = width_value
        item["height"] = height_value
        item["aspectRatio"] = round(width_value / height_value, 4)
    item["isShort9x16"] = is_9x16_short_shape(
        item.get("duration"),
        item.get("width"),
        item.get("height"),
    )


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
    duration: Any = None,
    width: Any = None,
    height: Any = None,
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
    item = {
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
    set_shape_metadata(item, duration=duration, width=width, height=height)
    return item


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
        min_score=-2,
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
                min_score=-2,
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
                min_score=-2,
            )
            if item:
                candidates.append(item)
                count += 1
                if count >= RANKING_SOURCE_LIMIT:
                    break
    return candidates


def collect_tubetrending(collected_at: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in TUBETRENDING_SOURCES:
        try:
            html = fetch_text(source["page"])
        except Exception as exc:
            print(f"warning: failed to fetch {source['page']}: {exc}", file=sys.stderr)
            continue

        rows: list[dict[str, Any]] = []
        for script in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, flags=re.S | re.I):
            try:
                payload = json.loads(unescape(script).strip())
            except Exception:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "ItemList":
                raw_rows = payload.get("itemListElement") or []
                rows.extend(raw for raw in raw_rows if isinstance(raw, dict))

        if not rows:
            for rank, video_id, title in re.findall(
                r'"position"\s*:\s*(\d+).*?"url"\s*:\s*"https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})".*?"name"\s*:\s*"([^"]+)"',
                html,
                flags=re.S | re.I,
            ):
                rows.append({"position": rank, "url": f"https://www.youtube.com/watch?v={video_id}", "name": title})

        seen: set[str] = set()
        for raw in rows:
            video_id = video_id_from_any(str(raw.get("url") or ""))
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            item = make_candidate(
                region="global",
                video_id=video_id,
                title=clean_text(str(raw.get("name") or "")),
                channel="",
                category="TubeTrending Shorts 48H",
                views_gained=0,
                source_rank=parse_int(raw.get("position")),
                source_window=source["window"],
                source_name=source["name"],
                source_url=source["page"],
                collected_at=collected_at,
                extra_notes=["source: TubeTrending most viewed new videos shorts filter"],
                min_score=-2,
            )
            if item:
                candidates.append(item)
                if len(seen) >= RANKING_SOURCE_LIMIT:
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
            min_score=0,
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
            min_score=0,
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
                    min_score=-2,
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
                if not video_id or duration <= 0 or duration > SHORTS_MAX_DURATION_SECONDS:
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
                    duration=duration,
                    width=raw.get("width"),
                    height=raw.get("height"),
                    extra_notes=[f"source: Chartika regional chart", f"duration: {duration}s"],
                    min_score=-2,
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
        collect_tubetrending,
        collect_yttrack,
        collect_chartika,
        collect_trendsfox,
        collect_top1trend,
    ):
        candidates.extend(collector(collected_at))
    return candidates


def youtube_api_key() -> str:
    return (os.environ.get("YOUTUBE_API_KEY") or os.environ.get("YT") or "").strip()


def youtube_api_published_after() -> str:
    recent_floor = datetime.now(timezone.utc) - timedelta(days=YOUTUBE_API_RECENT_DAYS)
    return recent_floor.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_youtube_api_video_details(video_ids: list[str], api_key: str) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for index in range(0, len(video_ids), 50):
        chunk = video_ids[index : index + 50]
        if not chunk:
            continue
        params = urlencode(
            {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(chunk),
                "key": api_key,
            }
        )
        payload = fetch_json(f"https://www.googleapis.com/youtube/v3/videos?{params}")
        for raw in payload.get("items") or []:
            video_id = raw.get("id")
            if video_id:
                details[str(video_id)] = raw
    return details


def probable_shorts_source(item: dict[str, Any]) -> bool:
    notes = " ".join(str(note) for note in item.get("matchNotes") or [])
    haystack = " ".join(
        str(value or "")
        for value in (
            item.get("sourceName"),
            item.get("sourceUrl"),
            item.get("sourceWindow"),
            item.get("category"),
            item.get("title"),
            notes,
        )
    ).lower()
    return any(marker in haystack for marker in ("short", "#shorts", "short-form"))


def append_match_note(item: dict[str, Any], note: str) -> None:
    notes = item.setdefault("matchNotes", [])
    if isinstance(notes, list) and note not in notes:
        notes.append(note)


def enrich_candidates_with_youtube_api_metadata(items: list[dict[str, Any]]) -> None:
    api_key = youtube_api_key()
    if not api_key:
        return

    targets: list[str] = []
    seen: set[str] = set()
    for item in items:
        video_id = item.get("id")
        if not video_id or video_id in seen:
            continue
        needs_shape = (
            item.get("isShort9x16") is not True
            or not item.get("duration")
            or not item.get("width")
            or not item.get("height")
        )
        if (
            needs_shape
            or item.get("likeCount") is None
            or not item.get("publishedAt")
            or parse_int(item.get("viewsGained")) < min_display_views_for_item(item)
        ):
            targets.append(str(video_id))
            seen.add(str(video_id))
            if len(targets) >= YOUTUBE_API_DETAILS_LIMIT:
                break

    if not targets:
        return

    try:
        details_by_id = fetch_youtube_api_video_details(targets, api_key)
    except Exception as exc:
        print(f"warning: YouTube Data API details enrichment failed: {exc}", file=sys.stderr)
        return

    for item in items:
        details = details_by_id.get(str(item.get("id") or ""))
        if not details:
            continue
        snippet = details.get("snippet") or {}
        statistics = details.get("statistics") or {}
        content_details = details.get("contentDetails") or {}

        published_at = normalize_published_at(snippet.get("publishedAt"))
        if published_at:
            item["publishedAt"] = published_at
        if snippet.get("channelTitle") and not item.get("channel"):
            item["channel"] = clean_text(snippet.get("channelTitle"))

        view_count = parse_int(statistics.get("viewCount"))
        if view_count and view_count >= parse_int(item.get("viewsGained")):
            item["viewsGained"] = view_count
        if statistics.get("likeCount") is not None:
            item["likeCount"] = parse_int(statistics.get("likeCount"))

        duration = parse_iso8601_duration(content_details.get("duration"))
        width = item.get("width")
        height = item.get("height")
        if duration and duration <= SHORTS_MAX_DURATION_SECONDS and (not parse_int(width) or not parse_int(height)):
            if probable_shorts_source(item):
                width, height = 1080, 1920
                append_match_note(item, "portrait inferred from shorts source")
        set_shape_metadata(item, duration=duration or None, width=width, height=height)
        append_match_note(item, "metadata: YouTube Data API video details")


def collect_youtube_api(collected_at: str) -> list[dict[str, Any]]:
    api_key = youtube_api_key()
    if not api_key:
        print("warning: YOUTUBE_API_KEY or YT is not set; skipping YouTube Data API collection", file=sys.stderr)
        return []

    candidates: list[dict[str, Any]] = []
    published_after = youtube_api_published_after()
    for region in REGIONS:
        seen_region_ids: set[str] = set()
        for query_index, query_text in enumerate(region["queries"], start=1):
            search_params: dict[str, str] = {
                "part": "snippet",
                "type": "video",
                "videoDuration": "short",
                "order": "viewCount",
                "maxResults": str(YOUTUBE_API_SEARCH_LIMIT),
                "publishedAfter": published_after,
                "q": query_text,
                "key": api_key,
            }
            region_code = YOUTUBE_API_REGION_CODES.get(region["key"], "")
            if region_code:
                search_params["regionCode"] = region_code

            try:
                search_payload = fetch_json(f"https://www.googleapis.com/youtube/v3/search?{urlencode(search_params)}")
            except Exception as exc:
                print(f"warning: YouTube Data API search failed for {region['label']}: {exc}", file=sys.stderr)
                if "HTTP Error 403" in str(exc):
                    return candidates
                continue

            search_rows = search_payload.get("items") or []
            video_ids: list[str] = []
            search_snippets: dict[str, dict[str, Any]] = {}
            ranks: dict[str, int] = {}
            for rank, row in enumerate(search_rows, start=1):
                video_id = str((row.get("id") or {}).get("videoId") or "")
                if not video_id or video_id in seen_region_ids or video_id in search_snippets:
                    continue
                video_ids.append(video_id)
                search_snippets[video_id] = row.get("snippet") or {}
                ranks[video_id] = ((query_index - 1) * YOUTUBE_API_SEARCH_LIMIT) + rank

            try:
                details_by_id = fetch_youtube_api_video_details(video_ids, api_key)
            except Exception as exc:
                print(f"warning: YouTube Data API video details failed for {region['label']}: {exc}", file=sys.stderr)
                details_by_id = {}

            for video_id in video_ids:
                details = details_by_id.get(video_id) or {}
                snippet = details.get("snippet") or search_snippets.get(video_id) or {}
                statistics = details.get("statistics") or {}
                content_details = details.get("contentDetails") or {}
                duration = parse_iso8601_duration(content_details.get("duration"))
                if not duration or duration > SHORTS_MAX_DURATION_SECONDS:
                    continue
                item = make_candidate(
                    region=region["key"],
                    video_id=video_id,
                    title=str(snippet.get("title") or ""),
                    channel=str(snippet.get("channelTitle") or ""),
                    category="YouTube Data API Shorts Search",
                    views_gained=parse_int(statistics.get("viewCount")),
                    source_rank=ranks.get(video_id, 0),
                    source_window="api-viewCount",
                    source_name=f"YouTube Data API - {region['label']}",
                    source_url=f"https://www.youtube.com/results?search_query={quote_plus(query_text)}",
                    collected_at=collected_at,
                    published_at=snippet.get("publishedAt"),
                    like_count=statistics.get("likeCount"),
                    duration=duration,
                    width=1080,
                    height=1920,
                    extra_notes=[
                        "source: YouTube Data API v3",
                        f"api query: {query_text}",
                        "official search and video metadata",
                        "api short-duration shorts candidate",
                    ],
                    min_score=-2,
                )
                if item:
                    candidates.append(item)
                    seen_region_ids.add(video_id)
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
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=YT_DLP_SEARCH_TIMEOUT_SECONDS,
            check=False,
        )
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
            proc = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=YT_DLP_METADATA_TIMEOUT_SECONDS,
                check=False,
            )
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
        needs_shape = (
            item.get("isShort9x16") is not True
            or not item.get("duration")
            or not item.get("width")
            or not item.get("height")
        )
        if (
            needs_shape
            or item.get("likeCount") is None
            or not item.get("publishedAt")
            or parse_int(item.get("viewsGained")) < MIN_DISPLAY_VIEWS
        ):
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
        width, height = video_dimensions_from_payload(payload)
        set_shape_metadata(item, duration=payload.get("duration"), width=width, height=height)


def from_ytdlp_item(raw: dict[str, Any], query: str, region: str, collected_at: str) -> dict[str, Any] | None:
    video_id = raw.get("id")
    duration = raw.get("duration")
    if not video_id:
        return None
    if isinstance(duration, (int, float)) and duration > SHORTS_MAX_DURATION_SECONDS:
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
        duration=raw.get("duration"),
        width=raw.get("width"),
        height=raw.get("height"),
        extra_notes=["source: YouTube search result"],
        min_score=-2,
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


def update_existing_item(old: dict[str, Any], new: dict[str, Any]) -> None:
    old["title"] = old.get("title") or new.get("title") or ""
    old["region"] = old.get("region") or new.get("region") or "global"
    old["regionLabel"] = region_label_for_key(old.get("region"))
    old["channel"] = new.get("channel") or old.get("channel")
    old["category"] = new.get("category") or old.get("category")
    if parse_int(new.get("viewsGained")) >= parse_int(old.get("viewsGained")):
        old["viewsGained"] = new.get("viewsGained") or old.get("viewsGained")
    if new.get("likeCount") is not None:
        old["likeCount"] = new.get("likeCount")
    old["sourceRank"] = new.get("sourceRank") or old.get("sourceRank")
    old["sourceWindow"] = new.get("sourceWindow") or old.get("sourceWindow")
    old["sourceName"] = new.get("sourceName") or old.get("sourceName")
    old["sourceUrl"] = new.get("sourceUrl") or old.get("sourceUrl")
    old["publishedAt"] = new.get("publishedAt") or old.get("publishedAt")
    old["matchNotes"] = new.get("matchNotes") or old.get("matchNotes")
    old["duration"] = new.get("duration") or old.get("duration")
    old["width"] = new.get("width") or old.get("width")
    old["height"] = new.get("height") or old.get("height")
    old["aspectRatio"] = new.get("aspectRatio") or old.get("aspectRatio")
    old["isShort9x16"] = new.get("isShort9x16") if new.get("isShort9x16") is not None else old.get("isShort9x16")
    old["lastSeenAt"] = new.get("collectedAt") or old.get("lastSeenAt") or old.get("collectedAt")
    old.setdefault("collectedAt", new.get("collectedAt"))
    set_shape_metadata(old)


def merge_items(existing: list[dict[str, Any]], new_items: list[dict[str, Any]], max_new: int) -> list[dict[str, Any]]:
    # Keep the archive append-only: only brand-new, non-duplicate videos are placed above history.
    existing_unique = dedupe_accumulated_items(existing)
    old_by_id = {item.get("id"): item for item in existing_unique if item.get("id")}
    old_by_signature = {content_signature(item): item for item in existing_unique if content_signature(item)}
    ranked = sorted(new_items, key=rank_item)

    candidates_by_region: dict[str, list[dict[str, Any]]] = {region["key"]: [] for region in REGIONS}
    seen: set[str] = set()
    seen_signatures: set[str] = set()
    for item in ranked:
        video_id = item.get("id")
        signature = content_signature(item)
        if not video_id or video_id in seen or signature in seen_signatures:
            continue
        seen.add(video_id)
        seen_signatures.add(signature)
        existing_item = old_by_id.get(video_id) or old_by_signature.get(signature)
        if existing_item:
            update_existing_item(existing_item, item)
            continue
        if not is_collectable_new_item(item):
            continue
        region = item.get("region") or "global"
        if region not in candidates_by_region:
            region = "global"
        candidates_by_region[region].append(item)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_signatures: set[str] = set()
    for region in REGIONS:
        count = 0
        for item in candidates_by_region[region["key"]]:
            video_id = item.get("id")
            signature = content_signature(item)
            if not video_id or video_id in selected_ids or signature in selected_signatures:
                continue
            selected.append(item)
            selected_ids.add(video_id)
            selected_signatures.add(signature)
            count += 1
            if count >= max_new:
                break

    viral_added = 0
    viral_candidates = sorted(
        (
            item
            for rows in candidates_by_region.values()
            for item in rows
            if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD
        ),
        key=lambda item: (parse_int(item.get("viewsGained")), popularity_score(item), parse_int(item.get("likeCount"))),
        reverse=True,
    )
    for item in viral_candidates:
        video_id = item.get("id")
        signature = content_signature(item)
        if not video_id or video_id in selected_ids or signature in selected_signatures:
            continue
        selected.append(item)
        selected_ids.add(video_id)
        selected_signatures.add(signature)
        viral_added += 1
        if viral_added >= VIRAL_NEW_ITEMS_LIMIT:
            break

    return order_items_newest_first(selected + existing_unique)


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


def is_short_9x16_item(item: dict[str, Any]) -> bool:
    set_shape_metadata(item)
    return item.get("isShort9x16") is True


def filter_shortform_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if is_short_9x16_item(item)]


def prune_shortform_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in dedupe_accumulated_items(items) if is_collectable_new_item(item)]


def source_priority(item: dict[str, Any]) -> int:
    name = str(item.get("sourceName") or "")
    if "Vidirun" in name:
        return 0
    if "Playboard" in name:
        return 1
    if "RedToolBox" in name:
        return 2
    if "TubeTrending" in name:
        return 3
    if "YTTrack" in name:
        return 4
    if "Chartika" in name:
        return 5
    if "TrendsFox" in name:
        return 6
    if "Top1Trend" in name:
        return 7
    if "YouTube Data API" in name:
        return 8
    if "YouTube Search" in name or "YouTube keyword" in name:
        return 9
    return 10


SOURCE_FAMILY_LABELS = {
    "Vidirun": "Vidirun 24H/7D 숏폼 랭킹",
    "Playboard": "Playboard 지역별 Shorts Daily",
    "RedToolBox": "RedToolBox 일/주/월 Top Shorts",
    "TubeTrending": "TubeTrending 48H 신규 Shorts",
    "YTTrack": "YTTrack 지역·카테고리 트렌드",
    "Chartika": "Chartika 지역 차트",
    "TrendsFox": "TrendsFox 라이브 트렌딩",
    "Top1Trend": "Top1Trend YouTube Trending",
    "YouTubeDataAPI": "YouTube Data API 공식 검색 소스",
    "YouTube": "YouTube 검색 보강",
    "Other": "기타 공개 소스",
}

GLOBAL_CRAWL_SOURCE_LABELS = [
    "Vidirun",
    "Playboard",
    "RedToolBox",
    "TubeTrending",
    "YTTrack",
    "Chartika",
    "TrendsFox",
    "Top1Trend",
    "YouTubeDataAPI",
]


def source_family(item: dict[str, Any]) -> str:
    name = str(item.get("sourceName") or "")
    if "youtube data api" in name.lower():
        return "YouTubeDataAPI"
    for family in GLOBAL_CRAWL_SOURCE_LABELS:
        if family.lower() in name.lower():
            return family
    if "youtube" in name.lower():
        return "YouTube"
    return "Other"


def source_family_label(family: str) -> str:
    return SOURCE_FAMILY_LABELS.get(family, family)


def is_youtube_data_api_item(item: dict[str, Any]) -> bool:
    return source_family(item) == "YouTubeDataAPI"


def min_display_views_for_item(item: dict[str, Any]) -> int:
    if is_youtube_data_api_item(item):
        return YOUTUBE_API_MIN_DISPLAY_VIEWS
    return MIN_DISPLAY_VIEWS


def is_collectable_new_item(item: dict[str, Any]) -> bool:
    return (
        parse_int(item.get("viewsGained")) >= min_display_views_for_item(item)
        and is_short_9x16_item(item)
    )


def is_displayable(item: dict[str, Any]) -> bool:
    return (
        parse_int(item.get("viewsGained")) >= min_display_views_for_item(item)
        and bool(item.get("publishedAt"))
        and is_short_9x16_item(item)
    )


def popularity_score(item: dict[str, Any]) -> int:
    views = parse_int(item.get("viewsGained"))
    likes = parse_int(item.get("likeCount"))
    return views + (likes * LIKE_POPULARITY_WEIGHT)


def rank_item(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        REGIONS.index(REGION_BY_KEY.get(item.get("region") or "global", REGION_BY_KEY["global"])),
        source_priority(item),
        item.get("sourceWindow") != "24H",
        -popularity_score(item),
        -parse_int(item.get("viewsGained")),
        -parse_int(item.get("likeCount")),
        item.get("sourceRank") or 9999,
    )


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return "0"


def duration_limit_text() -> str:
    if SHORTS_MAX_DURATION_SECONDS == 39:
        return "40초 미만"
    return f"{SHORTS_MAX_DURATION_SECONDS}초 이하"


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
    for source in TUBETRENDING_SOURCES:
        pairs.add((f"{source['name']} {source['window']}", source["page"]))
    pairs.add(("Playboard regional YouTube Shorts charts", "https://playboard.co/chart/short/most-viewed-all-videos-in-worldwide-daily"))
    pairs.add(("RedToolBox daily/weekly/monthly top Shorts", "https://www.redtoolbox.io/toplist/topShorts.jsp"))
    pairs.add(("YTTrack regional YouTube trending charts", "https://yttrack.com/"))
    pairs.add(("Chartika regional YouTube charts", "https://chartika.com/"))
    for source in HTML_SOURCES:
        pairs.add((source["name"], source["page"]))
    pairs.add(("YouTube Data API v3", "https://developers.google.com/youtube/v3"))
    pairs.add(("YouTube Shorts keyword searches", "https://www.youtube.com/results?search_query=%23shorts+dance+music+trend"))
    pairs = {(normalize_country_labels(name), url) for name, url in pairs}
    known_names = {name for name, _ in pairs}
    for item in items:
        source_name = normalize_country_labels(item.get("sourceName") or "")
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
    return "제목·조회수 기반 급상승"


def cluster_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {cluster["key"]: 0 for cluster in TREND_CLUSTERS}
    counts["other"] = 0
    for item in items:
        for key in item_cluster_keys(item):
            counts[key] += 1
    return counts


def top_cluster(items: list[dict[str, Any]]) -> tuple[str, int]:
    counts = cluster_counts(items)
    ranked = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    for key, count in ranked:
        if key != "other" and count:
            return key, count
    return ranked[0]


def top_signal_terms(items: list[dict[str, Any]], terms: list[str], limit: int = 5) -> list[tuple[str, int]]:
    counts = {term: 0 for term in terms}
    term_set = set(terms)
    for item in items:
        for term in term_hits(item_text(item), term_set):
            counts[term] += 1
    return [(term, count) for term, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True) if count][:limit]


def pct_text(count: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{round(count / total * 100)}%"


def cluster_mix_text(items: list[dict[str, Any]], limit: int = 3) -> str:
    counts = cluster_counts(items)
    ranked = [
        (key, count)
        for key, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
        if count and key != "other"
    ]
    if not ranked:
        ranked = [(key, count) for key, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True) if count]
    return ", ".join(
        f"{cluster_label(key)} {count}개({pct_text(count, len(items))})"
        for key, count in ranked[:limit]
    )


def top_signal_text(items: list[dict[str, Any]], limit: int = 5) -> str:
    terms = top_signal_terms(
        items,
        ["dance", "challenge", "funny", "comedy", "music", "song", "trend", "viral", "fyp", "shuffle", "magic", "prank", "tutorial"],
        limit,
    )
    return ", ".join(f"{term} {count}개" for term, count in terms) or "상위 제목 훅 분산"


def average_int(values: list[int]) -> int:
    values = [value for value in values if value]
    return round(sum(values) / len(values)) if values else 0


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


def title_hashtags(item: dict[str, Any]) -> list[str]:
    title = str(item.get("title") or "")
    tags = re.findall(r"#([\w가-힣ぁ-んァ-ン一-龥]+)", title, flags=re.UNICODE)
    unique: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append("#" + tag)
    return unique[:5]


def title_specific_hook_points(item: dict[str, Any]) -> list[str]:
    title = clean_text(str(item.get("title") or ""))
    text = title.lower()
    compact = compact_title(title, 54)
    points: list[str] = []

    if "?" in title or "？" in title:
        points.append(f"제목 '{compact}'가 질문형으로 열려 결과 확인 욕구를 만듦")
    if re.search(r"\bvs\b| versus ", text, flags=re.I):
        points.append(f"제목 '{compact}' 안에 비교 구도가 있어 전후 차이를 끝까지 확인하게 만듦")
    if re.search(r"대결|전쟁|world cup|fifa", text, flags=re.I):
        points.append(f"제목 '{compact}' 안에 경쟁 구도가 있어 승패·결과를 끝까지 보게 만듦")
    if any(term in text for term in ("magic", "마술", "trick", "reveal")):
        points.append(f"제목 '{compact}'의 마술·공개 신호가 트릭을 다시 확인하게 만듦")
    if re.search(r"\b(saved|rescue|almost|curse|unexpected|ending)\b|cost him", text):
        points.append(f"제목 '{compact}'가 위기·반전·결말을 먼저 던져 완주 동기를 만듦")
    if any(term in text for term in ("funny", "comedy", "humor", "prank", "laugh", "웃", "코미디")):
        points.append(f"제목 '{compact}'의 코미디 신호가 언어 장벽 낮은 공유 포인트를 만듦")
    if any(term in text for term in ("dance", "댄스", "춤", "challenge", "챌린지", "shuffle", "joget", "baile")):
        points.append(f"제목 '{compact}'의 댄스·챌린지 신호가 따라 하기와 반복 시청을 유도")
    if any(term in text for term in ("tutorial", "how to", "making", "backstage", "result")):
        points.append(f"제목 '{compact}'가 과정과 결과를 함께 암시해 전후 비교 욕구를 만듦")
    if any(term in text for term in ("k-pop", "kpop", "idol", "bts", "blackpink", "뉴진스", "아이돌")):
        points.append(f"제목 '{compact}'의 K-pop·팬덤 신호가 댓글·공유 반응을 모으기 쉬움")
    if any(term in text for term in ("song", "music", "노래", "음악", "trend", "trending", "phonk", "slowed")):
        points.append(f"제목 '{compact}'에 사운드·트렌드 단서가 있어 첫 프레임 전에 장르 기대가 형성됨")

    hashtags = title_hashtags(item)
    if hashtags:
        points.append(f"해시태그 {', '.join(hashtags[:4])}가 검색 발견성과 추천 테스트 진입점을 넓힘")

    emoji_count = len(re.findall(r"[^\w\s#.,:;!?？'\"/|()\-가-힣ぁ-んァ-ン一-龥]", title, flags=re.UNICODE))
    if emoji_count >= 2:
        points.append(f"이모지 {emoji_count}개가 감정 톤을 즉시 보여 줘 작은 썸네일에서도 분위기가 읽힘")

    if not points:
        points.append(f"제목 '{compact}'가 짧은 장면 기대를 먼저 만들어 스크롤 정지 포인트로 작동")
    return points


def metric_specific_points(item: dict[str, Any]) -> list[str]:
    views = parse_int(item.get("viewsGained"))
    likes = parse_int(item.get("likeCount"))
    duration = parse_int(item.get("duration"))
    age = published_age_days(item)
    points: list[str] = []

    if likes and views:
        like_rate = likes / views * 100
        if like_rate >= 3:
            points.append(f"좋아요율 약 {like_rate:.1f}%로 조회 대비 반응 밀도가 높아 추천 신호가 강함")
        elif like_rate >= 1:
            points.append(f"좋아요 {fmt_int(likes)}개가 붙어 단순 노출보다 실제 반응이 확인됨")
        else:
            points.append(f"조회수 {fmt_int(views)} 대비 좋아요 {fmt_int(likes)}개로 대량 노출형 확산 신호가 큼")
    elif views:
        points.append(f"공개 메타데이터 기준 조회수 {fmt_int(views)}회로 탭 내 비교 우선순위가 높음")

    if age is not None and views:
        if age <= 14:
            daily_views = max(round(views / max(age, 1)), 1)
            points.append(f"게시 후 {age}일 기준 하루 평균 약 {fmt_int(daily_views)} views 속도로 초기 확산이 빠름")
        elif views >= 10_000_000:
            points.append(f"게시 후 {age}일이 지나도 {fmt_int(views)} views를 유지해 장기 추천 노출이 남아 있음")

    if duration:
        if duration <= 15:
            points.append(f"{duration}초 길이라 훅과 결과를 빠르게 회수해 반복 재생에 유리")
        elif duration <= 35:
            points.append(f"{duration}초 구성으로 상황 전개와 결과 확인을 한 번에 담기 좋음")
        else:
            points.append(f"{duration}초 길이로 짧은 서사·챌린지 과정을 보여 줄 여유가 있음")

    source_rank = parse_int(item.get("sourceRank"))
    source_window = clean_text(str(item.get("sourceWindow") or ""))
    if source_rank:
        points.append(f"{source_window or 'source'} rank {source_rank}로 포착되어 같은 소스 안에서도 상위 반응 신호가 있음")
    return points


def popularity_reason_points(item: dict[str, Any]) -> list[str]:
    views = parse_int(item.get("viewsGained"))
    clusters = item_cluster_keys(item)
    labels = [cluster_label(key) for key in clusters if key != "other"]
    text = item_text(item).lower()
    age = published_age_days(item)
    terms = match_note_terms(item)
    region = item_region_label(item)
    source = normalize_country_labels(item.get("sourceName") or "ranking source")
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
        velocity = f"{source_detail} 신호와 {fmt_int(views)} views가 결합된 초기 후보 / 다음 수집에서 좋아요·순위 변화로 확장성 확인 필요"

    keyword_detail = f"감지 키워드: {', '.join(terms)}" if terms else "감지 키워드: 제목·소스 신호 중심"
    pattern_detail = f"분석 패턴: {', '.join(labels)}" if labels else "분석 패턴: 짧은 상황 이해와 시각적 훅 중심"

    return [
        f"{region} 탭에서 {fmt_int(views)} views로 확인된 {tier} 쇼츠",
        f"{source_detail}에 포착되어 단순 검색보다 랭킹·트렌드 출처의 반응 신호가 있음",
        keyword_detail,
        *title_specific_hook_points(item)[:4],
        *metric_specific_points(item)[:4],
        *hook_parts[:3],
        retention,
        velocity,
        pattern_detail,
    ]


def popularity_reason(item: dict[str, Any]) -> str:
    return " ".join(popularity_reason_points(item))


def card_popularity_points(item: dict[str, Any]) -> list[str]:
    points = popularity_reason_points(item)
    title_points = title_specific_hook_points(item)
    metric_points = metric_specific_points(item)
    selected = [points[0]]
    if title_points:
        selected.append(title_points[0])
    if metric_points:
        selected.append(metric_points[0])
    if len(metric_points) > 1:
        selected.append(metric_points[1])
    elif len(title_points) > 1:
        selected.append(title_points[1])
    elif len(points) > 2:
        selected.append(points[2])
    return unique_texts(selected)[:4]


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
    ("metric", "3,000뷰"),
    ("metric", "24H"),
    ("region", "글로벌"),
    ("region", "대한민국"),
    ("region", "미국"),
    ("region", "일본"),
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
    ("source", "Playboard"),
    ("source", "Vidirun"),
    ("source", "RedToolBox"),
    ("source", "TubeTrending"),
    ("source", "YTTrack"),
    ("source", "Chartika"),
    ("source", "TrendsFox"),
    ("source", "Top1Trend"),
    ("source", "YouTube Data API"),
    ("source", "API"),
    ("source", "YouTube"),
    ("source", "랭킹"),
    ("source", "트렌드"),
    ("source", "소스"),
    ("source", "공개 랭킹"),
    ("source", "글로벌 크롤링"),
    ("source", "크롤링"),
    ("source", "검색 보강"),
    ("source", "교차 확인"),
    ("source", "라이브 트렌딩"),
    ("source", "Top Shorts"),
    ("signal", "영상 제작자"),
    ("signal", "제작자"),
    ("signal", "공통 패턴"),
    ("signal", "국가별 콘텐츠 차별점"),
    ("signal", "실패 패턴"),
    ("signal", "저성과"),
    ("signal", "하위권"),
    ("signal", "결과 회수"),
    ("signal", "보상"),
    ("signal", "제작 포인트"),
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
    ("signal", "급상승권"),
    ("signal", "대형 확산권"),
    ("signal", "지역 탭 검토 후보"),
    ("signal", "초기 속도"),
    ("signal", "초기 반응"),
    ("signal", "알고리즘"),
    ("signal", "추천 노출"),
    ("signal", "추천 피드"),
    ("signal", "반응 신호"),
    ("signal", "인기 신호"),
    ("signal", "상황형 포맷"),
    ("signal", "상황극"),
    ("signal", "상황"),
    ("signal", "반전"),
    ("signal", "갈등"),
    ("signal", "궁금증"),
    ("signal", "호기심"),
    ("signal", "웃음 코드"),
    ("signal", "언어 장벽"),
    ("signal", "첫 장면"),
    ("signal", "첫 프레임"),
    ("signal", "시각적 훅"),
    ("signal", "음악 훅"),
    ("signal", "훅"),
    ("signal", "루프"),
    ("signal", "사운드"),
    ("signal", "펑크"),
    ("signal", "빠른 컷"),
    ("signal", "편집"),
    ("signal", "마술"),
    ("signal", "구출"),
    ("signal", "공개"),
    ("signal", "놀라움"),
    ("signal", "스턴트"),
    ("signal", "퍼포먼스"),
    ("signal", "K-pop"),
    ("signal", "아이돌"),
    ("signal", "팬덤"),
    ("signal", "확산"),
    ("signal", "재확산"),
    ("signal", "숏폼"),
    ("signal", "모바일"),
    ("signal", "따라 하기"),
    ("signal", "다시 보기"),
    ("signal", "재시청"),
    ("signal", "댄스"),
    ("signal", "음악"),
    ("signal", "챌린지"),
    ("signal", "코미디"),
    ("signal", "Astronomia"),
    ("signal", "Squid Game"),
    ("signal", "IP"),
    ("signal", "shuffle"),
    ("signal", "magic"),
    ("signal", "dance"),
    ("signal", "challenge"),
    ("signal", "funny"),
    ("signal", "comedy"),
    ("signal", "slowed"),
    ("signal", "edit"),
    ("signal", "saved"),
    ("signal", "reveal"),
    ("signal", "surprise"),
    ("signal", "defying"),
    ("signal", "wild"),
    ("signal", "prank"),
    ("signal", "humor"),
    ("signal", "music"),
    ("signal", "trend"),
    ("signal", "tutorial"),
    ("signal", "backstage"),
    ("signal", "baile"),
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
    bullet_points = unique_texts([bulletize_text(point) for point in points])
    return "\n".join(f"<li>{highlight_text(point)}</li>" for point in bullet_points)


def source_label(item: dict[str, Any]) -> str:
    label = clean_text(normalize_country_labels(item.get("sourceName") or "ranking source"))
    window = clean_text(str(item.get("sourceWindow") or ""))
    rank = item.get("sourceRank")
    if window:
        label += f" {window}"
    if rank:
        label += f" rank {rank}"
    return normalize_country_labels(label)


def render_mega_case_card(item: dict[str, Any]) -> str:
    source_url = str(item.get("sourceUrl") or item.get("shortsUrl") or "#")
    return f"""
        <article class="mega-case-card">
          <a class="mega-case-thumb" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener">
            <img src="{escape(item.get('thumbnail') or thumbnail_url(item['id']))}" alt="{escape(str(item.get('title', 'YouTube Shorts thumbnail')))}">
            <span class="duration-badge">{fmt_duration(item.get('duration'))}</span>
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
    unique_items = unique_content_items(items)
    mega_items = viral_view_items(unique_items)
    near_items = [
        item
        for item in sorted(unique_items, key=lambda row: parse_int(row.get("viewsGained")), reverse=True)
        if 30_000_000 <= parse_int(item.get("viewsGained")) < VIRAL_VIEW_THRESHOLD
    ][:6]
    recent_mega_items = sorted(
        mega_items,
        key=lambda row: (parse_date(row.get("publishedAt")) or datetime.min.date(), parse_int(row.get("viewsGained"))),
        reverse=True,
    )
    analysis_items = unique_content_items(recent_mega_items + near_items)
    if not analysis_items:
        analysis_items = sorted(unique_items, key=lambda row: parse_int(row.get("viewsGained")), reverse=True)[:6]
    analysis_items = analysis_items[:6]
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

    case_cards = "\n".join(render_mega_case_card(item) for item in analysis_items)
    case_section = (
        f"""
      <div class="mega-case-section">
        <div class="mega-section-heading">
          <h3>1억뷰·근접 사례 분석</h3>
        </div>
        <div class="mega-case-list">{case_cards}</div>
      </div>"""
        if case_cards
        else ""
    )
    viral_cards = "\n".join(render_mega_case_card(item) for item in mega_items[:VIRAL_DISPLAY_LIMIT])
    viral_section = (
        f"""
      <div class="mega-case-section">
        <div class="mega-section-heading">
          <h3>1억뷰 이상 Shorts</h3>
          <span>{highlight_text(f'{len(mega_items)}개 수집 / 조회순 상위 {min(len(mega_items), VIRAL_DISPLAY_LIMIT)}개 표시')}</span>
        </div>
        <div class="mega-case-list">{viral_cards}</div>
      </div>"""
        if viral_cards
        else ""
    )

    return f"""
    <section id="panel-mega" class="region-panel mega-panel" data-region-panel="mega" role="tabpanel" aria-labelledby="tab-mega" aria-label="1억뷰 이상 Shorts">
{viral_section}
{case_section}
      <div class="mega-hero">
        <div>
          <h2>1억뷰 이상 Shorts</h2>
          <ul class="mega-hero-points">{hero_point_items}</ul>
        </div>
        <strong>{len(mega_items)}</strong>
      </div>
      <div class="mega-grid">
        <div class="mega-block">
          <h3>왜 1억뷰가 나오는가</h3>
          <ul>{principle_items}</ul>
        </div>
      </div>
    </section>"""


def render_global_source_insights(items: list[dict[str, Any]], analysis_base: list[dict[str, Any]]) -> str:
    visible_items = unique_content_items([item for item in items if is_displayable(item)])
    if not visible_items:
        return ""

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in visible_items:
        family = source_family(item)
        groups.setdefault(family, []).append(item)

    notes: list[str] = []

    source_rows = sorted(
        ((family, rows) for family, rows in groups.items()),
        key=lambda pair: (source_priority(pair[1][0]), -len(pair[1]), -max(parse_int(item.get("viewsGained")) for item in pair[1])),
    )
    for family, rows in source_rows[:5]:
        top_item = max(rows, key=lambda item: parse_int(item.get("viewsGained")))
        cluster_text = cluster_mix_text(rows, 2)
        windows = sorted({clean_text(str(item.get("sourceWindow") or "")) for item in rows if item.get("sourceWindow")})
        window_text = "/".join(windows[:3]) if windows else "라이브"
        regions: dict[str, int] = {}
        for item in rows:
            label = item_region_label(item)
            regions[label] = regions.get(label, 0) + 1
        region_text = ", ".join(
            f"{label} {count}개"
            for label, count in sorted(regions.items(), key=lambda pair: pair[1], reverse=True)[:3]
        )
        avg_views = average_int([parse_int(item.get("viewsGained")) for item in rows])
        notes.append(
            f"{source_family_label(family)} / {window_text} / {len(rows)}개 / 주요 지역 {region_text or '여러 지역'} / 평균 {fmt_int(avg_views)} views / 대표 {compact_title(str(top_item.get('title', '')), 42)} ({fmt_int(top_item.get('viewsGained'))} views) / 포맷 {cluster_text}"
        )

    source_counts = cluster_counts(analysis_base)
    leading = [
        f"{cluster_label(key)} {count}개"
        for key, count in sorted(source_counts.items(), key=lambda pair: pair[1], reverse=True)
        if count and key != "other"
    ][:3]
    if leading:
        notes.append(f"소스 통합 핵심 / {', '.join(leading)} / 오늘 글로벌 탭에서 우선 확인할 포맷")
    return f"""
      <div class="trend-source-insights">
        <strong>글로벌 크롤링 인사이트</strong>
        <ul>{render_points(notes)}</ul>
      </div>"""


def view_tier_label(views: int) -> str:
    if views >= VIRAL_VIEW_THRESHOLD:
        return "1억뷰 이상"
    if views >= 30_000_000:
        return "3천만뷰 이상 1억뷰 근접"
    if views >= 10_000_000:
        return "1천만뷰 이상 급상승"
    if views >= 1_000_000:
        return "100만뷰 이상 검증권"
    return "저성과 위험 구간"


def creator_action_for_cluster(key: str) -> str:
    return {
        "situation": "첫 1초에 갈등·반전·결과 질문을 먼저 보여 주고, 마지막 컷에서 보상을 회수합니다.",
        "dance": "음악 훅과 따라 하기 쉬운 동작을 초반에 배치하고, 루프가 자연스럽게 이어지게 만듭니다.",
        "edit": "슬로우드 사운드나 빠른 컷 편집을 쓰되, 첫 장면의 상황 이해를 희생하지 않습니다.",
        "performance": "성공·실패가 궁금한 순간을 먼저 제시하고, 결과 공개를 너무 늦추지 않습니다.",
        "kpop": "팬덤이 바로 알아볼 수 있는 안무·의상·곡 신호를 첫 프레임에 배치합니다.",
    }.get(key, "제목보다 장면 자체가 먼저 이해되도록 피사체와 행동을 화면 중앙에 둡니다.")


def top_cluster_sentence(items: list[dict[str, Any]]) -> tuple[str, str]:
    if not items:
        return "상위 조회수 급상승", "첫 화면에서 피사체·행동·결과 기대가 한 번에 읽히도록 구성합니다."
    key, _ = top_cluster(items)
    return cluster_label(key), creator_action_for_cluster(key)


def render_creator_strategy_insights(items: list[dict[str, Any]], analysis_base: list[dict[str, Any]]) -> str:
    visible_items = unique_content_items([item for item in items if is_displayable(item)])
    if not visible_items:
        return ""

    sorted_by_views = sorted(visible_items, key=lambda item: parse_int(item.get("viewsGained")), reverse=True)
    mega_items = [item for item in sorted_by_views if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD]
    near_items = [item for item in sorted_by_views if 30_000_000 <= parse_int(item.get("viewsGained")) < VIRAL_VIEW_THRESHOLD]
    high_signal_items = mega_items or near_items or sorted_by_views[:8]
    top_label, top_action = top_cluster_sentence(high_signal_items)
    top_sources = sorted(
        {source_family_label(source_family(item)) for item in high_signal_items[:8]}
    )
    top_source_text = ", ".join(top_sources[:4]) if top_sources else "공개 랭킹 소스"
    highest = sorted_by_views[0]
    high_avg_views = average_int([parse_int(item.get("viewsGained")) for item in high_signal_items[:8]])
    high_avg_duration = average_int([parse_int(item.get("duration")) for item in high_signal_items[:8]])
    high_signal_terms = top_signal_text(high_signal_items, 4)

    common_points = [
        f"상위권 기준 / {len(high_signal_items[:8])}개 / 평균 {fmt_int(high_avg_views)} views / 평균 {high_avg_duration}초 / 대표 {compact_title(str(highest.get('title', '')), 44)} ({fmt_int(highest.get('viewsGained'))} views)",
        f"오늘 강한 신호 / {top_label} / 제목 키워드 {high_signal_terms} / 출처 {top_source_text}",
        f"제작 우선순위 / {top_action}",
        "확산 포인트 / 대사보다 표정·동작·결과가 먼저 읽히고, 마지막 컷이 첫 컷으로 자연스럽게 이어지는 루프 구조",
    ]

    region_points: list[str] = []
    grouped_by_region: dict[str, list[dict[str, Any]]] = {}
    for item in visible_items:
        grouped_by_region.setdefault(str(item.get("region") or "global"), []).append(item)
    for region_key, rows in sorted(grouped_by_region.items(), key=lambda pair: (-len(pair[1]), region_label_for_key(pair[0])))[:8]:
        region_label = region_label_for_key(region_key)
        cluster_name, action = top_cluster_sentence(rows)
        top_item = max(rows, key=lambda item: parse_int(item.get("viewsGained")))
        family_text = source_family_label(source_family(top_item))
        region_avg_views = average_int([parse_int(item.get("viewsGained")) for item in rows])
        region_terms = top_signal_text(rows, 3)
        region_points.append(
            f"{region_label} / {len(rows)}개 / 평균 {fmt_int(region_avg_views)} views / 핵심 {cluster_name} / 제목 신호 {region_terms} / 대표 {compact_title(str(top_item.get('title', '')), 38)} ({fmt_int(top_item.get('viewsGained'))} views) / 제작 포인트 {action} / 근거 {family_text}"
        )

    low_items = [item for item in visible_items if parse_int(item.get("viewsGained")) < 1_000_000]
    bottom_items = sorted(visible_items, key=lambda item: parse_int(item.get("viewsGained")))[:8]
    generic_titles = [
        item for item in visible_items
        if len(re.findall(r"#", str(item.get("title") or ""))) >= 4
        or len(term_hits(item_text(item), {"trend", "viral", "fyp", "shorts"})) >= 3
    ]
    weak_label, weak_action = top_cluster_sentence(low_items or bottom_items)
    weakest = bottom_items[0]
    weakest_views = parse_int(weakest.get("viewsGained"))
    low_ceiling = max(parse_int(item.get("viewsGained")) for item in bottom_items)
    bottom_terms = top_signal_text(bottom_items, 4)
    failure_points = [
        f"하위권 구간 / {len(bottom_items)}개 / {fmt_int(weakest_views)}~{fmt_int(low_ceiling)} views / 대표 {compact_title(str(weakest.get('title', '')), 40)}",
        f"약한 신호 / {weak_label}처럼 보여도 첫 장면 보상·결과 회수 약하면 확산 정체 / 하위 제목 신호 {bottom_terms}",
        f"주의 패턴 / 해시태그·trend·viral 과밀 후보 {len(generic_titles)}개 / 키워드 나열보다 실제 행동·상황·결과 질문 우선",
        f"개선 포인트 / {weak_action}",
    ]

    return f"""
      <div class="creator-insights">
        <strong>영상 제작자 인사이트</strong>
        <div class="creator-insight-grid">
          <div class="creator-insight-card">
            <h3>1억뷰 공통 패턴</h3>
            <ul>{render_points(common_points)}</ul>
          </div>
          <div class="creator-insight-card">
            <h3>국가별 콘텐츠 차별점</h3>
            <ul>{render_points(region_points)}</ul>
          </div>
          <div class="creator-insight-card">
            <h3>실패 패턴</h3>
            <ul>{render_points(failure_points)}</ul>
          </div>
        </div>
      </div>"""


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
            if key == "other":
                continue
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
    top_view_clusters = ", ".join(cluster_label(key) for key in item_cluster_keys(top_view_item)[:2] if key != "other")
    if not top_view_clusters:
        top_view_clusters = "제목·조회수 기반 급상승"

    if rising_delta >= 0.08:
        shift_sentence = f"변화 / {cluster_label(rising_key)} 비중 +{round(rising_delta * 100)}%p / 이전 누적 대비 가장 빠르게 확대"
    elif rising_delta <= -0.08:
        shift_sentence = f"변화 / {cluster_label(rising_key)} 비중 {round(rising_delta * 100)}%p / 관심이 다른 포맷으로 분산"
    else:
        shift_sentence = "변화 / 급격한 쏠림보다 기존 강세 포맷 유지 / 상위 사례 중심으로 세부 훅 확인 필요"

    recent_range = f"{cutoff.month}/{cutoff.day} ~ {latest_date.month}/{latest_date.day}"
    recent_mix = cluster_mix_text(analysis_base, 3)
    recent_terms = top_signal_text(analysis_base, 5)
    recent_avg_views = average_int([parse_int(item.get("viewsGained")) for item in analysis_base])
    recent_avg_duration = average_int([parse_int(item.get("duration")) for item in analysis_base])
    notes = [
        f"분석 기간 / {recent_range} / 최근 게시 {len(analysis_base)}개 / 평균 {fmt_int(recent_avg_views)} views / 평균 {recent_avg_duration}초",
        f"포맷 분포 / {recent_mix}",
        shift_sentence,
        f"지역 확산 / {region_text or '여러 지역'} / 제목 신호 {recent_terms}",
        f"상위 최근 사례 / {compact_title(str(top_view_item.get('title', '')))} / {fmt_int(top_view_item.get('viewsGained'))} views / {top_view_clusters}",
    ]

    note_items = render_points(notes)
    source_insights = render_global_source_insights(items, analysis_base)
    creator_insights = render_creator_strategy_insights(items, analysis_base)
    top_badges = "\n".join(
        f"<li>{highlight_text(f'{cluster_label(key)} {count}')}</li>"
        for key, count in sorted(recent_counts.items(), key=lambda pair: pair[1], reverse=True)[:4]
        if count and key != "other"
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
{source_insights}
{creator_insights}
    </section>"""


def render_youtube_api_analysis(items: list[dict[str, Any]]) -> str:
    api_items = unique_content_items([item for item in items if is_displayable(item)])
    if not api_items:
        return f"""
    <section class="trend-brief youtube-api-brief" aria-label="YouTube API analysis">
      <div class="trend-heading">
        <strong>YouTube API 인사이트</strong>
        <ul class="trend-meta">
          <li>{highlight_text("API 표시 영상 0개")}</li>
          <li>{highlight_text(f"{YOUTUBE_API_MIN_DISPLAY_VIEWS:,}뷰 이상")}</li>
        </ul>
      </div>
      <ul class="trend-notes">{render_points(["YouTube Data API 수집 결과가 아직 없어 다음 실행에서 다시 확인 필요"])}</ul>
    </section>"""

    dated_items = [(item, parse_date(item.get("publishedAt"))) for item in api_items]
    dated_items = [(item, published) for item, published in dated_items if published]
    latest_date = max((published for _, published in dated_items), default=None)
    cutoff = latest_date - timedelta(days=6) if latest_date else None
    recent_items = [item for item, published in dated_items if cutoff and published >= cutoff]
    analysis_base = recent_items or api_items
    counts = cluster_counts(api_items)
    top_key, _ = top_cluster(api_items)
    top_item = max(api_items, key=lambda item: parse_int(item.get("viewsGained")))
    top_cluster_text = ", ".join(cluster_label(key) for key in item_cluster_keys(top_item)[:2] if key != "other") or cluster_label(top_key)
    top_action = creator_action_for_cluster(top_key)

    region_counts: dict[str, int] = {}
    for item in api_items:
        label = item_region_label(item)
        region_counts[label] = region_counts.get(label, 0) + 1
    region_text = ", ".join(
        f"{label} {count}개"
        for label, count in sorted(region_counts.items(), key=lambda pair: pair[1], reverse=True)[:5]
    )

    api_windows = sorted({clean_text(str(item.get("sourceWindow") or "")) for item in api_items if item.get("sourceWindow")})
    window_text = ", ".join(api_windows) if api_windows else "api-viewCount"
    recent_range = f"{cutoff.month}/{cutoff.day} ~ {latest_date.month}/{latest_date.day}" if cutoff and latest_date else "게시일 확인 구간"
    like_text = fmt_count(top_item.get("likeCount"))
    duration_values = [parse_int(item.get("duration")) for item in api_items if parse_int(item.get("duration"))]
    avg_duration = round(sum(duration_values) / len(duration_values)) if duration_values else 0
    signal_term_text = top_signal_text(api_items, 5)
    api_avg_views = average_int([parse_int(item.get("viewsGained")) for item in api_items])
    api_recent_mix = cluster_mix_text(analysis_base, 3)

    summary_points = [
        f"API 기준 / search/videos / {len(api_items)}개 / {YOUTUBE_API_MIN_DISPLAY_VIEWS:,}뷰 이상 / 평균 {fmt_int(api_avg_views)} views / {duration_limit_text()}",
        f"조회수 1위 / {compact_title(str(top_item.get('title', '')), 48)} / {fmt_int(top_item.get('viewsGained'))} views / 좋아요 {like_text} / 정렬 {window_text}",
        f"지역 분포 / {region_text or '여러 지역'} / 제목 신호 {signal_term_text}",
        f"최근 API 표본 / {recent_range} / {len(analysis_base)}개 / 포맷 {api_recent_mix}",
    ]

    pattern_points = [
        f"상위 포맷 / {top_cluster_text} / 제작 포인트 {top_action}",
        f"길이 패턴 / 평균 {avg_duration}초 / {duration_limit_text()} 안에 훅과 결과를 회수하는 짧은 구조 우세",
        f"제목 패턴 / {signal_term_text} / 음악·동작·상황 훅이 검색 발견성 주도",
        "검수 포인트 / 공식 조회수·좋아요·게시일 확인 가능 / 랭킹 사이트 후보와 초기 반응 비교",
    ]

    region_points: list[str] = []
    grouped_by_region: dict[str, list[dict[str, Any]]] = {}
    for item in api_items:
        grouped_by_region.setdefault(str(item.get("region") or "global"), []).append(item)
    for region_key, rows in sorted(grouped_by_region.items(), key=lambda pair: (-len(pair[1]), region_label_for_key(pair[0])))[:6]:
        region_top = max(rows, key=lambda item: parse_int(item.get("viewsGained")))
        region_cluster, region_action = top_cluster_sentence(rows)
        region_avg = average_int([parse_int(item.get("viewsGained")) for item in rows])
        region_terms = top_signal_text(rows, 3)
        region_points.append(
            f"{region_label_for_key(region_key)} / API {len(rows)}개 / 평균 {fmt_int(region_avg)} views / 대표 {compact_title(str(region_top.get('title', '')), 42)} ({fmt_int(region_top.get('viewsGained'))} views) / 신호 {region_cluster} / 제목 {region_terms} / 제작 {region_action}"
        )

    top_badges = "\n".join(
        f"<li>{highlight_text(f'{cluster_label(key)} {count}')}</li>"
        for key, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:4]
        if count and key != "other"
    )

    return f"""
    <section class="trend-brief youtube-api-brief" aria-label="YouTube API analysis">
      <div class="trend-heading">
        <strong>YouTube API 인사이트</strong>
        <ul class="trend-meta">
          <li>{highlight_text(f'API 표시 영상 {len(api_items)}개')}</li>
          <li>{highlight_text(f'{YOUTUBE_API_MIN_DISPLAY_VIEWS:,}뷰 이상')}</li>
        </ul>
      </div>
      <ul class="trend-badges">{top_badges}</ul>
      <ul class="trend-notes">{render_points(summary_points)}</ul>
      <div class="trend-source-insights">
        <strong>API 수집 요약</strong>
        <ul>{render_points(pattern_points)}</ul>
      </div>
      <div class="creator-insights">
        <strong>API 기반 지역 인사이트</strong>
        <div class="creator-insight-grid">
          <div class="creator-insight-card">
            <h3>지역별 API 신호</h3>
            <ul>{render_points(region_points)}</ul>
          </div>
        </div>
      </div>
    </section>"""


def render_card(item: dict[str, Any], index: int) -> str:
    reason_items = render_points(card_popularity_points(item))
    return f"""
      <article class="short-card">
        <a class="thumb-link" href="{escape(item['shortsUrl'])}" target="_blank" rel="noopener" aria-label="Open {escape(item['title'])} on YouTube Shorts">
          <img src="{escape(item['thumbnail'])}" alt="{escape(item['title'])} thumbnail" loading="lazy">
          <span class="rank">#{index}</span>
          <span class="duration-badge">{fmt_duration(item.get('duration'))}</span>
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


def high_view_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        unique_content_items([item for item in items if is_displayable(item)]),
        key=lambda item: (parse_int(item.get("viewsGained")), parse_int(item.get("likeCount")), popularity_score(item)),
        reverse=True,
    )


def viral_view_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in high_view_items(items)
        if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD
    ]


def popular_view_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            popularity_score(item),
            parse_int(item.get("viewsGained")),
            parse_int(item.get("likeCount")),
            parse_collected_at(item.get("collectedAt")).timestamp(),
            -parse_int(item.get("sourceRank") or 9999),
        ),
        reverse=True,
    )


def render_youtube_api_showcase(api_items: list[dict[str, Any]]) -> str:
    ranked = high_view_items(api_items)
    if not ranked:
        return """
      <div class="grid">
        <div class="empty-state">공식 API 후보는 다음 업데이트에서 다시 확인됩니다.</div>
      </div>"""

    top_item = ranked[0]
    top_cards = "\n".join(render_mega_case_card(item) for item in ranked[:3])
    grid_cards = "".join(render_card(item, index) for index, item in enumerate(ranked, start=1))
    return f"""
      <div class="mega-case-section">
        <div class="mega-section-heading">
          <h3>YouTube API 조회수 상위 Shorts</h3>
        </div>
        <div class="mega-case-list">{top_cards}</div>
      </div>
      <div class="trend-brief youtube-api-brief" aria-label="YouTube API top video">
        <div class="trend-heading">
          <strong>NOW TRENDING #1</strong>
          <ul class="trend-meta">
            <li>{highlight_text(f'{fmt_int(top_item.get("viewsGained"))} views')}</li>
            <li>{highlight_text(f'{fmt_count(top_item.get("likeCount"))} 좋아요')}</li>
            <li>{highlight_text(str(top_item.get("publishedAt") or "게시일 확인"))}</li>
          </ul>
        </div>
        <ul class="trend-notes">{render_points(card_popularity_points(top_item))}</ul>
      </div>
      <div class="grid">{grid_cards}
      </div>"""


def group_items_by_region(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {region["key"]: [] for region in REGIONS}
    seen: set[str] = set()
    seen_signatures: set[str] = set()
    for item in order_items_newest_first(items):
        video_id = item.get("id")
        signature = content_signature(item)
        if not video_id or video_id in seen or signature in seen_signatures or not is_displayable(item):
            continue
        seen.add(video_id)
        seen_signatures.add(signature)
        grouped[item["region"]].append(item)
    for region_key, region_items in grouped.items():
        grouped[region_key] = popular_view_items(region_items)
    return grouped


def build_display_context(items: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    items = order_items_newest_first(items)
    api_pool = [item for item in items if source_family(item) == "YouTubeDataAPI"]
    grouped = group_items_by_region(items)
    api_items = unique_content_items([item for item in order_items_newest_first(api_pool) if is_displayable(item)])
    display_items = [item for region_items in grouped.values() for item in region_items]
    return grouped, api_items, display_items


def local_date_key(value: Any) -> str:
    return parse_collected_at(value).astimezone(KST).date().isoformat()


def format_date_key(date_key: str) -> str:
    try:
        parsed = datetime.fromisoformat(date_key).date()
    except ValueError:
        return date_key
    return f"{parsed.month}/{parsed.day}"


def item_seen_on_date(item: dict[str, Any], date_key: str) -> bool:
    return any(
        value and local_date_key(value) == date_key
        for value in (item.get("collectedAt"), item.get("lastSeenAt"))
    )


def item_collected_on_date(item: dict[str, Any], date_key: str) -> bool:
    return bool(item.get("collectedAt")) and local_date_key(item.get("collectedAt")) == date_key


def latest_observed_date_key(items: list[dict[str, Any]]) -> str:
    keys = [
        local_date_key(value)
        for item in items
        for value in (item.get("collectedAt"), item.get("lastSeenAt"))
        if value
    ]
    return max(keys) if keys else datetime.now(KST).date().isoformat()


def latest_observed_at_iso(items: list[dict[str, Any]]) -> str:
    observed = [
        parse_collected_at(value)
        for item in items
        for value in (item.get("collectedAt"), item.get("lastSeenAt"))
        if value
    ]
    if not observed:
        return datetime.now(KST).replace(microsecond=0).isoformat()
    return max(observed).astimezone(KST).replace(microsecond=0).isoformat()


def active_items_for_date(items: list[dict[str, Any]], date_key: str) -> tuple[list[dict[str, Any]], str]:
    displayable = unique_content_items([item for item in items if is_displayable(item)])
    active = [item for item in displayable if item_seen_on_date(item, date_key)]
    if active:
        return active, date_key
    fallback_key = latest_observed_date_key(displayable)
    fallback = [item for item in displayable if item_seen_on_date(item, fallback_key)]
    return fallback or displayable, fallback_key


def date_range_text(items: list[dict[str, Any]]) -> str:
    dates = sorted({published for item in items if (published := parse_date(item.get("publishedAt")))})
    if not dates:
        return "게시일 혼합"
    first = dates[0]
    last = dates[-1]
    if first == last:
        return f"{first.month}/{first.day}"
    return f"{first.month}/{first.day} ~ {last.month}/{last.day}"


def top_region_summary(items: list[dict[str, Any]], limit: int = 3) -> str:
    counts: dict[str, int] = {}
    for item in items:
        label = item_region_label(item)
        counts[label] = counts.get(label, 0) + 1
    return ", ".join(
        f"{label} {count}개"
        for label, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    )


def top_source_summary(items: list[dict[str, Any]], limit: int = 3) -> str:
    counts: dict[str, int] = {}
    for item in items:
        label = source_family_label(source_family(item))
        counts[label] = counts.get(label, 0) + 1
    return ", ".join(
        f"{label} {count}개"
        for label, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    )


def source_takeaway(family: str, rows: list[dict[str, Any]]) -> str:
    key, _ = top_cluster(rows)
    label = cluster_label(key)
    if family in {"Vidirun", "TubeTrending"}:
        return f"단기 급상승 확인용 / {label} 포맷이 빠르게 조회를 모으는지 우선 확인"
    if family == "Playboard":
        return f"지역별 실사용 반응 확인용 / {label} 포맷이 여러 국가 탭으로 번지는지 관찰"
    if family == "YTTrack":
        return f"카테고리 반응 확인용 / 코미디·엔터테인먼트 안에서 {label} 훅 검증"
    if family == "YouTubeDataAPI":
        return f"공식 조회수·좋아요 검수용 / 검색 발견성은 {label} 쪽이 강함"
    return f"보조 랭킹 신호 / {label} 후보를 다른 소스와 교차 확인"


def shift_text(active_items: list[dict[str, Any]], previous_items: list[dict[str, Any]], fallback_key: str) -> str:
    active_key, _ = top_cluster(active_items)
    if not previous_items:
        return f"{cluster_label(active_key)} 중심으로 오늘 표본 형성 / 이전 비교 표본 부족"
    active_counts = cluster_counts(active_items)
    previous_counts = cluster_counts(previous_items)
    comparison: list[tuple[float, str]] = []
    for key in active_counts:
        if key == "other":
            continue
        delta = trend_ratio(active_counts, key, len(active_items)) - trend_ratio(previous_counts, key, len(previous_items))
        comparison.append((delta, key))
    comparison.sort(reverse=True)
    delta, key = comparison[0] if comparison else (0.0, active_key)
    if delta >= 0.08:
        return f"{cluster_label(key)} 비중 +{round(delta * 100)}%p / 오늘 랭킹에서 가장 빠르게 확대"
    if delta <= -0.08:
        return f"{cluster_label(key)} 비중 {round(delta * 100)}%p / 관심이 다른 포맷으로 분산"
    return f"{cluster_label(active_key)} 강세 유지 / {format_date_key(fallback_key)} 재감지 표본 기준"


def insight_metric(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value}


def insight_line(label: str, text: str) -> dict[str, str]:
    return {"label": label, "text": bulletize_text(text)}


def video_metric_summary(item: dict[str, Any]) -> str:
    duration = parse_int(item.get("duration"))
    duration_text = f"{duration}초" if duration else "길이 확인"
    cluster = cluster_label(item_cluster_keys(item)[0])
    return (
        f"{compact_title(str(item.get('title', '')), 42)} · "
        f"조회 {fmt_count(item.get('viewsGained'))} · "
        f"좋아요 {fmt_count(item.get('likeCount'))} · "
        f"{duration_text} · {cluster}"
    )


def top_video_insight_lines(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, str]]:
    ranked = sorted(
        unique_content_items(items),
        key=lambda item: (popularity_score(item), parse_int(item.get("viewsGained")), parse_int(item.get("likeCount"))),
        reverse=True,
    )
    return [insight_line(f"#{index}", video_metric_summary(item)) for index, item in enumerate(ranked[:limit], start=1)]


def top_like_summary(items: list[dict[str, Any]]) -> str:
    liked_items = [item for item in items if parse_int(item.get("likeCount")) > 0]
    if not liked_items:
        return "좋아요 공개 데이터가 있는 영상부터 다음 업데이트에서 우선 비교"
    top_item = max(liked_items, key=lambda item: (parse_int(item.get("likeCount")), popularity_score(item)))
    views = parse_int(top_item.get("viewsGained"))
    likes = parse_int(top_item.get("likeCount"))
    rate = (likes / views * 100) if views else 0
    return f"{compact_title(str(top_item.get('title', '')), 42)} · 좋아요 {fmt_count(likes)} · 조회 대비 {rate:.1f}%"


def duration_mix_summary(items: list[dict[str, Any]], avg_duration: int) -> str:
    durations = [parse_int(item.get("duration")) for item in items if parse_int(item.get("duration"))]
    if not durations:
        return f"{duration_limit_text()} 후보만 표시"
    near_limit_count = sum(1 for duration in durations if duration >= max(1, SHORTS_MAX_DURATION_SECONDS - 4))
    return f"{duration_limit_text()} {len(durations)}개 / 제한 근접 {near_limit_count}개 / 평균 {avg_duration}초"


def build_source_cards(items: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(source_family(item), []).append(item)
    cards: list[dict[str, Any]] = []
    source_rows = sorted(
        groups.items(),
        key=lambda pair: (source_priority(pair[1][0]), -len(pair[1]), -max(parse_int(item.get("viewsGained")) for item in pair[1])),
    )
    for family, rows in source_rows[:limit]:
        top_item = max(rows, key=lambda item: parse_int(item.get("viewsGained")))
        windows = sorted({clean_text(str(item.get("sourceWindow") or "")) for item in rows if item.get("sourceWindow")})
        avg_views = average_int([parse_int(item.get("viewsGained")) for item in rows])
        cards.append(
            {
                "title": source_family_label(family),
                "metrics": [
                    insight_metric("감지", f"{len(rows)}개"),
                    insight_metric("평균 조회", f"{fmt_int(avg_views)} views"),
                    insight_metric("구간", "/".join(windows[:3]) if windows else "라이브"),
                ],
                "items": [
                    insight_line("주요 지역", top_region_summary(rows, 3) or "여러 지역"),
                    insight_line("대표", f"{compact_title(str(top_item.get('title', '')), 42)} / {fmt_int(top_item.get('viewsGained'))} views"),
                    insight_line("포맷", cluster_mix_text(rows, 2) or "분산"),
                    insight_line("읽을 점", source_takeaway(family, rows)),
                ],
            }
        )
    return cards


def build_creator_cards(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible_items = unique_content_items([item for item in items if is_displayable(item)])
    if not visible_items:
        return []
    sorted_by_views = sorted(visible_items, key=lambda item: parse_int(item.get("viewsGained")), reverse=True)
    mega_items = [item for item in sorted_by_views if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD]
    near_items = [item for item in sorted_by_views if 30_000_000 <= parse_int(item.get("viewsGained")) < VIRAL_VIEW_THRESHOLD]
    high_signal_items = (mega_items or near_items or sorted_by_views)[:8]
    top_label, top_action = top_cluster_sentence(high_signal_items)
    highest = sorted_by_views[0]
    high_avg_views = average_int([parse_int(item.get("viewsGained")) for item in high_signal_items])
    high_avg_duration = average_int([parse_int(item.get("duration")) for item in high_signal_items])

    grouped_by_region: dict[str, list[dict[str, Any]]] = {}
    for item in visible_items:
        grouped_by_region.setdefault(str(item.get("region") or "global"), []).append(item)
    region_lines: list[dict[str, str]] = []
    for region_key, rows in sorted(grouped_by_region.items(), key=lambda pair: (-len(pair[1]), region_label_for_key(pair[0])))[:5]:
        cluster_name, action = top_cluster_sentence(rows)
        top_item = max(rows, key=lambda item: parse_int(item.get("viewsGained")))
        region_avg_views = average_int([parse_int(item.get("viewsGained")) for item in rows])
        region_lines.append(
            insight_line(
                region_label_for_key(region_key),
                f"{cluster_name} 중심 / 평균 {fmt_int(region_avg_views)} views / 제목 {top_signal_text(rows, 3)} / 대표 {compact_title(str(top_item.get('title', '')), 34)} / 액션 {action}",
            )
        )

    bottom_items = sorted(visible_items, key=lambda item: parse_int(item.get("viewsGained")))[:8]
    weakest = bottom_items[0]
    low_ceiling = max(parse_int(item.get("viewsGained")) for item in bottom_items)
    generic_titles = [
        item
        for item in visible_items
        if len(re.findall(r"#", str(item.get("title") or ""))) >= 4
        or len(term_hits(item_text(item), {"trend", "viral", "fyp", "shorts"})) >= 3
    ]
    weak_label, weak_action = top_cluster_sentence(bottom_items)

    return [
        {
            "title": "1억뷰 공통 패턴",
            "items": [
                insight_line("상위권", f"{len(high_signal_items)}개 평균 {fmt_int(high_avg_views)} views / 평균 {high_avg_duration}초"),
                insight_line("대표", f"{compact_title(str(highest.get('title', '')), 44)} / {fmt_int(highest.get('viewsGained'))} views"),
                insight_line("강한 신호", f"{top_label} / 제목 {top_signal_text(high_signal_items, 4)}"),
                insight_line("제작 우선순위", top_action),
            ],
        },
        {
            "title": "국가별 콘텐츠 차이",
            "items": region_lines,
        },
        {
            "title": "실패 패턴",
            "items": [
                insight_line("하위 구간", f"{len(bottom_items)}개 / {fmt_int(parse_int(weakest.get('viewsGained')))}~{fmt_int(low_ceiling)} views"),
                insight_line("약한 신호", f"{weak_label}처럼 보여도 첫 장면 보상·결과 회수 약하면 확산 정체"),
                insight_line("주의", f"해시태그·trend·viral 과밀 후보 {len(generic_titles)}개 / 키워드보다 행동·상황·결과 우선"),
                insight_line("개선", weak_action),
            ],
        },
    ]


def build_trend_model(items: list[dict[str, Any]], generated_at: str, title: str, min_views: int) -> dict[str, Any]:
    visible_items = unique_content_items([item for item in items if is_displayable(item)])
    date_key = local_date_key(generated_at)
    today_items = [item for item in visible_items if item_seen_on_date(item, date_key)]
    active_items, active_key = active_items_for_date(visible_items, date_key)
    active_ids = {item.get("id") for item in active_items}
    previous_items = [item for item in visible_items if item.get("id") not in active_ids]
    new_items = [item for item in today_items if item_collected_on_date(item, date_key)]
    refreshed_items = [item for item in today_items if item.get("id") not in {row.get("id") for row in new_items}]
    active_ranked = sorted(
        active_items,
        key=lambda item: (popularity_score(item), parse_int(item.get("viewsGained")), parse_int(item.get("likeCount"))),
        reverse=True,
    )

    counts = cluster_counts(active_items)
    top_key, top_count = top_cluster(active_items)
    top_pct = pct_text(top_count, len(active_items))
    top_item = active_ranked[0] if active_ranked else {}
    top_label, top_action = top_cluster_sentence(active_items)
    avg_views = average_int([parse_int(item.get("viewsGained")) for item in active_items])
    avg_duration = average_int([parse_int(item.get("duration")) for item in active_items])
    key_video_lines = top_video_insight_lines(active_items)

    badges = [
        f"{cluster_label(key)} {count}개"
        for key, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
        if count and key != "other"
    ][:4]
    if active_key == date_key:
        detection_text = f"{format_date_key(active_key)} 랭킹·API 재감지 {len(today_items)}개 / 신규 편입 {len(new_items)}개 / 기존 재확인 {len(refreshed_items)}개"
    else:
        detection_text = f"{format_date_key(date_key)} 신규 감지 없음 / 최신 보유 데이터 {format_date_key(active_key)} 기준 재분석"

    cards = [
        {
            "title": "핵심 영상",
            "items": key_video_lines or [insight_line("대기", "표시 가능한 영상이 부족해 다음 수집에서 재분석")],
        },
        {
            "title": "오늘 신호",
            "items": [
                insight_line("강한 포맷", f"{top_label} {top_count}개 / {top_pct}"),
                insight_line("감지 기준", detection_text),
                insight_line("반응 밀도", top_like_summary(active_items)),
            ],
        },
        {
            "title": "제작 액션",
            "items": [
                insight_line("우선 적용", top_action),
                insight_line("참고 영상", f"{compact_title(str(top_item.get('title', '')), 46)} · 조회 {fmt_count(top_item.get('viewsGained'))} · 좋아요 {fmt_count(top_item.get('likeCount'))}"),
                insight_line("길이", duration_mix_summary(active_items, avg_duration)),
                insight_line("변화", shift_text(active_items, previous_items, active_key)),
                insight_line("검토 포인트", "첫 프레임에서 결과 질문을 만들고 마지막 컷에서 보상 회수"),
            ],
        },
    ]

    return {
        "title": title,
        "metrics": [
            insight_metric("전체 표시", f"{len(visible_items)}개"),
            insight_metric("오늘 감지", f"{len(today_items)}개"),
            insight_metric("신규 편입", f"{len(new_items)}개"),
            insight_metric("분석 표본", f"{len(active_items)}개"),
            insight_metric("기준", f"{min_views:,}뷰 이상"),
        ],
        "badges": badges,
        "cards": cards,
        "sources": [],
        "creatorCards": [],
    }


def build_api_insight_model(api_items: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    model = build_trend_model(api_items, generated_at, "YouTube API 인사이트", YOUTUBE_API_MIN_DISPLAY_VIEWS)
    model["sources"] = []
    for card in model.get("cards", []):
        if card.get("title") == "오늘 신호":
            card["items"].append(insight_line("API 조건", f"search/videos / {YOUTUBE_API_MIN_DISPLAY_VIEWS:,}뷰 이상 / {duration_limit_text()}"))
    return model


def build_insight_snapshot(items: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    _, api_items, display_items = build_display_context(items)
    date_key = local_date_key(generated_at)
    return {
        "dateKey": date_key,
        "updatedAt": generated_at,
        "updatedLabel": fmt_footer_update(generated_at),
        "global": build_trend_model(display_items, generated_at, "트렌드 분석", MIN_DISPLAY_VIEWS),
        "api": build_api_insight_model(api_items, generated_at),
    }


def upsert_insight_snapshot(history: list[dict[str, Any]], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    date_key = snapshot.get("dateKey")
    kept = [item for item in history if item.get("dateKey") != date_key]
    return [snapshot] + kept[: max(INSIGHT_HISTORY_LIMIT - 1, 0)]


def refresh_insight_history_models(items: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for snapshot in history[:INSIGHT_HISTORY_LIMIT]:
        generated_at = snapshot.get("updatedAt") or snapshot.get("dateKey") or latest_observed_at_iso(items)
        rebuilt = build_insight_snapshot(items, str(generated_at))
        date_key = str(rebuilt.get("dateKey") or "")
        if not date_key or date_key in seen_dates:
            continue
        refreshed.append(rebuilt)
        seen_dates.add(date_key)
    return refreshed


def render_metric_pills(metrics: list[dict[str, str]]) -> str:
    return "".join(
        f"""<span class="insight-metric"><b>{escape(metric.get('label', ''))}</b><strong>{highlight_text(metric.get('value', ''))}</strong></span>"""
        for metric in metrics
    )


def render_labeled_items(items: list[dict[str, str]]) -> str:
    rows = []
    for item in items:
        label = escape(item.get("label", ""))
        text = highlight_text(item.get("text", ""))
        rows.append(f"""<li><b>{label}</b><span>{text}</span></li>""")
    return "\n".join(rows)


def render_insight_cards(cards: list[dict[str, Any]], class_name: str = "insight-card") -> str:
    return "\n".join(
        f"""
          <article class="{class_name}">
            <h3>{escape(card.get('title', ''))}</h3>
            <div class="mini-metrics">{render_metric_pills(card.get('metrics') or [])}</div>
            <ul>{render_labeled_items(card.get('items') or [])}</ul>
          </article>"""
        for card in cards
    )


def render_source_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    return f"""
        <div class="insight-subsection">
          <h3>소스별 관찰</h3>
          <div class="source-card-grid">
{render_insight_cards(cards, "source-card")}
          </div>
        </div>"""


def render_creator_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    return f"""
        <div class="insight-subsection">
          <h3>영상 제작자 인사이트</h3>
          <div class="creator-insight-grid">
{render_insight_cards(cards, "creator-insight-card")}
          </div>
        </div>"""


def render_snapshot_model(snapshot: dict[str, Any], key: str, is_latest: bool) -> str:
    model = snapshot.get(key) or {}
    if not model:
        return ""
    badges = "".join(f"<li>{highlight_text(badge)}</li>" for badge in model.get("badges", []))
    latest_label = '<span class="insight-live">최신</span>' if is_latest else ""
    return f"""
      <section class="daily-insight{' daily-insight--latest' if is_latest else ''}">
        <div class="daily-insight-head">
          <div>
            <span class="insight-date">{escape(snapshot.get('updatedLabel') or format_date_key(str(snapshot.get('dateKey') or '')))}</span>
            <h2>{escape(model.get('title', '인사이트'))}{latest_label}</h2>
          </div>
          <div class="insight-metrics">{render_metric_pills(model.get('metrics') or [])}</div>
        </div>
        <ul class="insight-badges">{badges}</ul>
        <div class="insight-grid">
{render_insight_cards(model.get('cards') or [])}
        </div>
{render_source_cards(model.get('sources') or [])}
{render_creator_cards(model.get('creatorCards') or [])}
      </section>"""


def render_insight_history(history: list[dict[str, Any]], key: str, fallback_items: list[dict[str, Any]], title: str, min_views: int) -> str:
    if not history:
        generated_at = (os.environ.get("SITE_UPDATED_AT") or datetime.now(KST).replace(microsecond=0).isoformat())
        model = build_trend_model(fallback_items, generated_at, title, min_views)
        history = [{"dateKey": local_date_key(generated_at), "updatedAt": generated_at, "updatedLabel": fmt_footer_update(generated_at), key: model}]
    rendered = "\n".join(
        render_snapshot_model(snapshot, key, index == 0)
        for index, snapshot in enumerate(history[:INSIGHT_HISTORY_LIMIT])
        if snapshot.get(key)
    )
    return f"""
    <section class="insight-stack" aria-label="{escape(title)}">
{rendered}
    </section>"""


def render_index(items: list[dict[str, Any]], insight_history: list[dict[str, Any]] | None = None) -> str:
    items = order_items_newest_first(items)
    grouped, api_items, display_items = build_display_context(items)
    insight_history = insight_history or read_insights()
    trend_analysis = render_insight_history(insight_history, "global", display_items, "트렌드 분석", MIN_DISPLAY_VIEWS)
    api_analysis = render_insight_history(insight_history, "api", api_items, "YouTube API 인사이트", YOUTUBE_API_MIN_DISPLAY_VIEWS)
    mega_count = sum(1 for item in display_items if parse_int(item.get("viewsGained")) >= VIRAL_VIEW_THRESHOLD)

    tab_parts = []
    for region in REGIONS:
        is_active = region["key"] == "global"
        tab_parts.append(
            f"""<button id="tab-{region['key']}" class="tab-button{' active' if is_active else ''}" type="button" role="tab" aria-selected="{'true' if is_active else 'false'}" aria-controls="panel-{region['key']}" data-region-tab="{region['key']}"><span class="tab-label">{escape(region['label'])}</span><span class="tab-count">{len(grouped[region['key']])}</span></button>"""
        )
        if region["key"] == "global":
            tab_parts.append(
                f"""<button id="tab-mega" class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="panel-mega" data-region-tab="mega"><span class="tab-label">1억뷰 이상</span><span class="tab-count">{mega_count}</span></button>"""
            )
            tab_parts.append(
                f"""<button id="tab-youtube-api" class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="panel-youtube-api" data-region-tab="youtube_api"><span class="tab-label">YouTube API</span><span class="tab-count">{len(api_items)}</span></button>"""
            )
    tab_buttons = "\n".join(tab_parts)

    panels = [
        render_mega_view_analysis(display_items),
        f"""
    <section id="panel-youtube-api" class="region-panel" data-region-panel="youtube_api" role="tabpanel" aria-labelledby="tab-youtube-api" aria-label="YouTube Data API Shorts">
{api_analysis}
{render_youtube_api_showcase(api_items)}
    </section>""",
    ]
    for region in REGIONS:
        region_cards = "".join(render_card(item, index) for index, item in enumerate(grouped[region["key"]], start=1))
        if not region_cards:
            region_cards = '<div class="empty-state">No matching Shorts collected for this region yet.</div>'
        panel_intro = trend_analysis if region["key"] == "global" else ""
        panels.append(
            f"""
    <section id="panel-{region['key']}" class="region-panel{' active' if region['key'] == 'global' else ''}" data-region-panel="{region['key']}" role="tabpanel" aria-labelledby="tab-{region['key']}" aria-label="{escape(region['label'])} trending shorts">
{panel_intro}
      <div class="grid">{region_cards}
      </div>
    </section>"""
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
      border: 1px solid transparent;
      font-weight: 900;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .text-mark--metric {{
      background: #ffe4e6;
      border-color: #fecdd3;
      color: #9f1239;
    }}
    .text-mark--region {{
      background: #ccfbf1;
      border-color: #99f6e4;
      color: #0f766e;
    }}
    .text-mark--source {{
      background: #dbeafe;
      border-color: #bfdbfe;
      color: #1d4ed8;
    }}
    .text-mark--signal {{
      background: #fef3c7;
      border-color: #fde68a;
      color: #854d0e;
    }}
    .shell {{
      width: calc(100% - 28px);
      max-width: 100%;
      margin: 0 auto;
    }}
    header {{
      border-bottom: 1px solid rgba(220, 38, 38, 0.18);
      background: linear-gradient(180deg, rgba(255, 245, 245, 0.98) 0%, rgba(255, 255, 255, 0.94) 100%);
      position: sticky;
      top: 0;
      z-index: 10;
      box-shadow: 0 10px 30px rgba(127, 29, 29, 0.08);
      backdrop-filter: blur(14px);
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      overflow: visible;
      padding: 12px 0;
      position: relative;
    }}
    .tab-button {{
      position: relative;
      isolation: isolate;
      overflow: hidden;
      border: 1px solid rgba(220, 38, 38, 0.26);
      border-radius: 14px;
      background: linear-gradient(180deg, #ffffff 0%, #fff7f7 100%);
      color: #7f1d1d;
      padding: 8px 9px 8px 12px;
      font: inherit;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 38px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86), 0 1px 2px rgba(127, 29, 29, 0.08);
      transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    }}
    .tab-button::before {{
      content: "";
      position: absolute;
      inset: -2px;
      z-index: -1;
      background: linear-gradient(110deg, transparent 0%, rgba(255, 255, 255, 0.72) 42%, rgba(254, 202, 202, 0.5) 54%, transparent 72%);
      transform: translateX(-115%);
      transition: transform 0.42s ease;
    }}
    .tab-button::after {{
      content: "";
      position: absolute;
      left: 12px;
      right: 12px;
      bottom: 5px;
      height: 2px;
      border-radius: 999px;
      background: transparent;
      opacity: 0;
      transform: scaleX(0.42);
      transform-origin: center;
      transition: background 0.2s ease, opacity 0.2s ease, transform 0.2s ease;
    }}
    .tab-label {{
      position: relative;
      z-index: 1;
      line-height: 1;
    }}
    .tab-count {{
      position: relative;
      z-index: 1;
      min-width: 24px;
      padding: 3px 7px;
      border-radius: 999px;
      background: #ffe4e6;
      color: #9f1239;
      font-size: 12px;
      line-height: 1;
      text-align: center;
      box-shadow: inset 0 0 0 1px rgba(220, 38, 38, 0.16);
      transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
    }}
    .tab-button:hover {{
      background: linear-gradient(180deg, #fffafa 0%, #ffe4e6 100%);
      border-color: rgba(220, 38, 38, 0.58);
      color: #7f1d1d;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.94), 0 8px 22px rgba(220, 38, 38, 0.16);
      transform: translateY(-2px);
    }}
    .tab-button:hover::before {{
      transform: translateX(115%);
    }}
    .tab-button:hover::after {{
      background: #ef4444;
      opacity: 1;
      transform: scaleX(1);
    }}
    .tab-button:hover .tab-count {{
      background: white;
      color: #991b1b;
      box-shadow: inset 0 0 0 1px rgba(220, 38, 38, 0.22);
    }}
    .tab-button:focus-visible {{
      outline: 3px solid rgba(239, 68, 68, 0.28);
      outline-offset: 3px;
    }}
    .tab-button:active {{
      transform: translateY(0) scale(0.98);
    }}
    .tab-button.active {{
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 44%, #991b1b 100%);
      border-color: #7f1d1d;
      color: white;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 10px 24px rgba(220, 38, 38, 0.28);
    }}
    .tab-button.active:hover {{
      background: linear-gradient(135deg, #f87171 0%, #dc2626 42%, #7f1d1d 100%);
      border-color: #7f1d1d;
    }}
    .tab-button.active::after {{
      background: rgba(255, 255, 255, 0.88);
      opacity: 1;
      transform: scaleX(1);
    }}
    .tab-button.active .tab-count {{
      background: rgba(255, 255, 255, 0.18);
      color: white;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.22);
    }}
    .tab-button.active:hover .tab-count {{
      background: white;
      color: var(--tab-red-dark);
    }}
    main {{
      padding: 14px 0 44px;
    }}
    .insight-stack {{
      order: 2;
      display: grid;
      gap: 18px;
      margin: 22px 0 0;
    }}
    .daily-insight {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
      padding: 18px;
    }}
    .daily-insight--latest {{
      border-color: rgba(220, 38, 38, 0.28);
      box-shadow: 0 10px 26px rgba(24, 33, 47, 0.06);
    }}
    .daily-insight-head {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      margin-bottom: 14px;
    }}
    .insight-date {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      line-height: 1.2;
      margin-bottom: 3px;
    }}
    .daily-insight h2 {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: var(--ink);
      font-size: 19px;
      line-height: 1.25;
    }}
    .insight-live {{
      border-radius: 999px;
      background: #fee2e2;
      color: #991b1b;
      padding: 3px 7px;
      font-size: 11px;
      font-weight: 900;
    }}
    .insight-metrics,
    .mini-metrics {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }}
    .mini-metrics {{
      justify-content: flex-start;
      margin-bottom: 8px;
    }}
    .insight-metric {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid rgba(13, 148, 136, 0.18);
      border-radius: 999px;
      background: #ffffff;
      color: #344054;
      padding: 6px 9px;
      font-size: 11.5px;
      line-height: 1.25;
      white-space: nowrap;
    }}
    .insight-metric b {{
      color: var(--muted);
      font-weight: 800;
    }}
    .insight-metric strong {{
      font-weight: 900;
    }}
    .insight-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 14px;
      padding: 0;
      list-style: none;
    }}
    .insight-badges li {{
      border: 1px solid rgba(220, 38, 38, 0.18);
      border-radius: 999px;
      background: #fff7f7;
      color: #7f1d1d;
      padding: 6px 9px;
      font-size: 11.5px;
      font-weight: 900;
    }}
    .insight-grid,
    .source-card-grid,
    .creator-insight-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
    }}
    .source-card-grid {{
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .insight-card,
    .source-card,
    .creator-insight-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 15px;
    }}
    .source-card {{
      background: #fffafa;
    }}
    .creator-insight-card {{
      background: #f8fbfd;
    }}
    .insight-card h3,
    .source-card h3,
    .creator-insight-card h3,
    .insight-subsection > h3 {{
      margin: 0 0 10px;
      color: #344054;
      font-size: 14px;
      line-height: 1.35;
      font-weight: 900;
    }}
    .insight-subsection {{
      margin-top: 14px;
    }}
    .insight-card ul,
    .source-card ul,
    .creator-insight-card ul {{
      display: grid;
      gap: 9px;
      margin: 0;
      padding: 0;
      list-style: none;
      color: #344054;
      font-size: 13px;
      line-height: 1.65;
    }}
    .insight-card li,
    .source-card li,
    .creator-insight-card li {{
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr);
      gap: 11px;
      align-items: start;
      border-top: 1px solid #edf2f7;
      padding-top: 9px;
    }}
    .insight-card li:first-child,
    .source-card li:first-child,
    .creator-insight-card li:first-child {{
      border-top: 0;
      padding-top: 0;
    }}
    .insight-card li b,
    .source-card li b,
    .creator-insight-card li b {{
      color: #991b1b;
      font-size: 11.5px;
      font-weight: 900;
      line-height: 1.35;
    }}
    .creator-insight-card li b {{
      color: #0f766e;
    }}
    .insight-card li span,
    .source-card li span,
    .creator-insight-card li span {{
      min-width: 0;
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
    .trend-source-insights {{
      margin-top: 14px;
      padding: 14px;
      border: 1px solid rgba(220, 38, 38, 0.16);
      border-radius: 8px;
      background: linear-gradient(180deg, #ffffff 0%, #fff7f7 100%);
    }}
    .trend-source-insights > strong {{
      display: block;
      margin-bottom: 8px;
      color: #7f1d1d;
      font-size: 14px;
      line-height: 1.3;
      font-weight: 900;
    }}
    .trend-source-insights ul {{
      margin: 0;
      padding-left: 18px;
      color: #344054;
      font-size: 12.5px;
      line-height: 1.6;
    }}
    .trend-source-insights li + li {{
      margin-top: 6px;
    }}
    .creator-insights {{
      margin-top: 14px;
      padding: 14px;
      border: 1px solid rgba(13, 148, 136, 0.18);
      border-radius: 8px;
      background: #ffffff;
    }}
    .creator-insights > strong {{
      display: block;
      margin-bottom: 10px;
      color: #0f766e;
      font-size: 14px;
      line-height: 1.3;
      font-weight: 900;
    }}
    .creator-insight-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
    }}
    .creator-insight-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fbfd;
      padding: 12px;
    }}
    .creator-insight-card h3 {{
      margin: 0 0 8px;
      color: #344054;
      font-size: 13px;
      line-height: 1.3;
      font-weight: 900;
    }}
    .creator-insight-card ul {{
      margin: 0;
      padding-left: 18px;
      color: #344054;
      font-size: 12px;
      line-height: 1.58;
    }}
    .creator-insight-card li + li {{
      margin-top: 6px;
    }}
    .daily-insight .creator-insight-grid {{
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    .daily-insight .creator-insight-card ul {{
      display: grid;
      gap: 7px;
      padding: 0;
      list-style: none;
      font-size: 12.5px;
      line-height: 1.55;
    }}
    .daily-insight .creator-insight-card li + li {{
      margin-top: 0;
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
      position: relative;
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
      grid-template-columns: 1fr;
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
      order: 1;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
      gap: 18px;
      align-items: stretch;
    }}
    .region-panel {{
      display: none;
    }}
    .region-panel.active {{
      display: flex;
      flex-direction: column;
      gap: 0;
    }}
    .region-panel > .grid,
    .region-panel > .mega-case-section {{
      order: 1;
    }}
    .region-panel > .mega-hero {{
      order: 2;
    }}
    .region-panel > .mega-grid {{
      order: 3;
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
      transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, background 0.2s ease;
    }}
    .short-card:hover {{
      background: #fff1f2;
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
    .thumb-link::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: rgba(220, 38, 38, 0);
      transition: background 0.2s ease;
      pointer-events: none;
    }}
    .short-card:hover .thumb-link::after {{
      background: rgba(220, 38, 38, 0.16);
    }}
    .thumb-link img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform 0.25s ease, filter 0.25s ease;
    }}
    .short-card:hover .thumb-link img {{
      transform: scale(1.025);
      filter: saturate(1.08) contrast(1.04);
    }}
    .rank {{
      position: absolute;
      top: 8px;
      left: 8px;
      z-index: 2;
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
    .duration-badge {{
      position: absolute;
      right: 8px;
      bottom: 8px;
      z-index: 2;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      min-height: 24px;
      border-radius: 6px;
      background: rgba(0, 0, 0, 0.82);
      color: white;
      padding: 4px 7px;
      font-family: "JetBrains Mono", "Noto Sans KR", monospace;
      font-size: 11px;
      font-weight: 800;
      line-height: 1;
      letter-spacing: 0;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.24);
    }}
    .short-body {{
      min-width: 0;
      padding: 10px 11px 12px;
      display: flex;
      flex-direction: column;
      gap: 7px;
      background: var(--surface);
      transition: background 0.2s ease, color 0.2s ease;
    }}
    .short-card:hover .short-body {{
      background: #fff1f2;
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
      transition: color 0.2s ease;
    }}
    .short-card:hover h2 {{
      color: var(--tab-red-dark);
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
      transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
    }}
    .short-card:hover .popularity {{
      background: #ffe4e6;
      border-left-color: var(--tab-red);
      color: #7f1d1d;
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
      .tabs {{ gap: 6px; padding: 9px 0; }}
      .tab-button {{ min-height: 34px; padding: 7px 7px 7px 9px; border-radius: 12px; font-size: 11px; gap: 6px; }}
      .tab-count {{ min-width: 20px; padding: 2px 6px; font-size: 10px; }}
      .tab-button::after {{ left: 9px; right: 9px; bottom: 4px; }}
      .daily-insight-head {{ flex-direction: column; }}
      .insight-metrics {{ justify-content: flex-start; }}
      .insight-card li,
      .source-card li,
      .creator-insight-card li {{ grid-template-columns: 1fr; gap: 3px; }}
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
      <nav class="tabs" role="tablist" aria-label="지역별 쇼츠 탭">
        {tab_buttons}
      </nav>
    </div>
  </header>
  <main class="shell">
{''.join(panels)}
    <div class="footer-update">업데이트 {escape(fmt_footer_update(os.environ.get("SITE_UPDATED_AT")))}</div>
  </main>
  <script type="application/json" id="shorts-data">{data_json}</script>
  <script>
    const buttons = Array.from(document.querySelectorAll("[data-region-tab]"));
    const panelsByRegion = new Map(Array.from(document.querySelectorAll("[data-region-panel]")).map((panel) => [panel.dataset.regionPanel, panel]));

    const activateTab = (button) => {{
      const region = button.dataset.regionTab;
      buttons.forEach((item) => {{
        const isActive = item === button;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-selected", String(isActive));
      }});
      panelsByRegion.forEach((panel, key) => panel.classList.toggle("active", key === region));
    }};

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        activateTab(button);
      }});
      button.addEventListener("keydown", (event) => {{
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const currentIndex = buttons.indexOf(button);
        const lastIndex = buttons.length - 1;
        const nextIndex = event.key === "Home"
          ? 0
          : event.key === "End"
            ? lastIndex
            : event.key === "ArrowRight"
              ? (currentIndex + 1) % buttons.length
              : (currentIndex - 1 + buttons.length) % buttons.length;
        buttons[nextIndex].focus();
        activateTab(buttons[nextIndex]);
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true", help="Render index.html from existing shorts-data.json")
    parser.add_argument("--max-new", type=int, default=int(os.environ.get("MAX_NEW_SHORTS_PER_REGION", "18")))
    args = parser.parse_args()

    existing = read_data()
    insight_history = read_insights()
    if args.render_only:
        merged = prune_shortform_items(existing)
        if len(merged) != len(existing):
            write_data(merged)
        generated_at = latest_observed_at_iso(merged)
        insight_history = upsert_insight_snapshot(insight_history, build_insight_snapshot(merged, generated_at))
        insight_history = refresh_insight_history_models(merged, insight_history)
        write_insights(insight_history)
    else:
        collected_at = datetime.now(KST).replace(microsecond=0).isoformat()
        candidates = collect_vidirun(collected_at)
        candidates.extend(collect_html_sources(collected_at))
        candidates.extend(collect_youtube_api(collected_at))
        enrich_candidates_with_youtube_api_metadata(candidates)
        if SKIP_YT_DLP_METADATA:
            print("warning: SKIP_YT_DLP_METADATA is set; using source/API metadata only", file=sys.stderr)
            candidates = filter_shortform_items(candidates)
        else:
            try:
                import yt_dlp  # noqa: F401
            except Exception:
                print("warning: yt-dlp is not installed; skipping YouTube metadata/search; keeping verified 9:16 history only", file=sys.stderr)
                candidates = filter_shortform_items(candidates)
            else:
                enrich_video_metadata(candidates)
                candidates = filter_shortform_items(candidates)
                needed_regions = regions_needing_search(candidates, args.max_new)
                if needed_regions:
                    print(
                        "ranking sources need YouTube search fallback for: "
                        + ", ".join(region["label"] for region in REGIONS if region["key"] in needed_regions),
                        file=sys.stderr,
                    )
                    search_candidates = collect_youtube_search(collected_at, needed_regions)
                    enrich_video_metadata(search_candidates)
                    candidates.extend(filter_shortform_items(search_candidates))
                else:
                    print("ranking sources filled every region; skipping YouTube search fallback", file=sys.stderr)
        merged = merge_items(existing, candidates, args.max_new)
        if SKIP_YT_DLP_METADATA:
            print("warning: SKIP_YT_DLP_METADATA is set; skipping publish-date enrichment", file=sys.stderr)
        else:
            try:
                import yt_dlp  # noqa: F401
            except Exception:
                print("warning: yt-dlp is not installed; skipping publish-date enrichment", file=sys.stderr)
            else:
                enrich_video_metadata(merged)
        merged = prune_shortform_items(merged)
        write_data(merged)
        insight_history = upsert_insight_snapshot(insight_history, build_insight_snapshot(merged, collected_at))
        insight_history = refresh_insight_history_models(merged, insight_history)
        write_insights(insight_history)

    INDEX_PATH.write_text(render_index(merged, insight_history), encoding="utf-8")
    print(f"rendered {INDEX_PATH} with {len(merged)} shorts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
