"""0차 스파이크 설정. 카테고리별 트렌드(mostPopular) + 검색(search.list).

모드:
- category (프리셋): mostPopular per videoCategoryId + duration≤180s(shorts). 자동 수집.
- search (온디맨드): search.list videoDuration=short, 사용자 키워드.
- channel (온디맨드): 특정 채널 /shorts (필요 시).
"""
import os
import re
import shutil


def _slugify(name: str) -> str:
    """이름 → URL slug. 공백→-, 소문자, 한글 허용."""
    s = re.sub(r"\s+", "-", (name or "").strip().lower())
    s = re.sub(r"[^a-z0-9가-힣\-]", "", s)
    return s or "niche"


# === 카테고리 프리셋 (mostPopular + shorts) ===
# categoryId: 24=엔터, 26=Howto/스타일, 23=코미디, 28=과학/기술, 1=영화/애니, 10=음악
# (게임 20 / People 22 은 shorts 0개라 제외)
NICHES = {
    "entertainment": {"name": "엔터테인먼트", "mode": "category", "category_id": "24"},
    "howto-style": {"name": "일상/스타일", "mode": "category", "category_id": "26"},
    "comedy": {"name": "코미디", "mode": "category", "category_id": "23"},
    "tech-science": {"name": "과학/기술", "mode": "category", "category_id": "28"},
    "film": {"name": "영화/애니", "mode": "category", "category_id": "1"},
    "music": {"name": "음악", "mode": "category", "category_id": "10"},
}
DEFAULT_SLUG = "entertainment"

# === 온디맨드 (환경변수 — Actions workflow_dispatch) ===
_env_niche_name = os.environ.get("NICHE_NAME") or None
_env_slug = os.environ.get("NICHE_SLUG") or None
_env_channels_raw = os.environ.get("CHANNELS_RAW") or None
_env_search = os.environ.get("SEARCH_KEYWORD") or None

if _env_niche_name and _env_search:
    NICHE = _env_niche_name
    NICHE_SLUG = _slugify(_env_slug or _env_niche_name)
    SOURCE_MODE = "search"
    SEARCH_KEYWORDS = [_env_search]
    CHANNELS = []
    CATEGORY_ID = None
elif _env_niche_name and _env_channels_raw:
    NICHE = _env_niche_name
    NICHE_SLUG = _slugify(_env_slug or _env_niche_name)
    SOURCE_MODE = "channel"
    SEARCH_KEYWORDS = []
    CATEGORY_ID = None
    _lines = [l.strip() for l in _env_channels_raw.splitlines() if l.strip()]
    CHANNELS = []
    for i, ln in enumerate(_lines, 1):
        nm = ln if ln.startswith("@") else (ln.rstrip("/").split("/")[-1] or f"채널{i}")
        CHANNELS.append((nm, ln))
else:
    # 프리셋 카테고리 (schedule 자동 갱신)
    NICHE_SLUG = _env_slug or DEFAULT_SLUG
    _preset = NICHES.get(NICHE_SLUG, NICHES[DEFAULT_SLUG])
    NICHE = _preset["name"]
    SOURCE_MODE = _preset.get("mode", "category")
    CATEGORY_ID = _preset.get("category_id")
    CHANNELS = []
    SEARCH_KEYWORDS = []

# === API 키 ===
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") or None
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
ACR_ACCESS_KEY = os.environ.get("ACR_ACCESS_KEY") or None
ACR_ACCESS_SECRET = os.environ.get("ACR_ACCESS_SECRET") or None
ACR_HOST = os.environ.get("ACR_HOST") or "ap-sea-1.api.acrcloud.com"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or None
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or None

# === 파이프라인 설정 ===
TARGET_COUNT = 30         # 카테고리당 목표 영상 수
MAX_VIDEO_DURATION = 180  # 초. shorts 기준 (YouTube Shorts 최대 3분)
OPENING_SECONDS = 5
WHISPER_MODEL = "small"

# === 필터 ===
MIN_VIEW_COUNT = 0        # mostPopular는 이미 인기 → 조회수 컷 불필요
OUTLIER_VIEW_SHARE = 0.50
BLOCK_KEYWORDS = []       # 카테고리 트렌드는 제목 필터 안 함 (자동 분류)

# === 경로 ===
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT = os.path.join(ROOT, "output")
OUTPUT_DIR = os.path.join(OUTPUT_ROOT, NICHE_SLUG)
AUDIO_DIR = os.path.join(OUTPUT_ROOT, "audio")

# === 외부 바이너리 ===
YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
