"""0차 스파이크 설정. 니치는 프리셋(NICHES) 또는 환경변수(온디맨드)로 교체됨.

두 가지 니치 소스:
- 프리셋 (NICHES[slug]): 사전 큐레이션. schedule 자동 갱신 대상.
- 온디맨드 (env NICHE_NAME + CHANNELS_RAW/SEARCH_KEYWORD): Actions workflow_dispatch로 1회 수집.
"""
import json
import os
import re
import shutil


def _slugify(name: str) -> str:
    """니치명 → URL 경로용 slug. 공백→-, 소문자, 한글 허용."""
    s = re.sub(r"\s+", "-", (name or "").strip().lower())
    s = re.sub(r"[^a-z0-9가-힣\-]", "", s)
    return s or "niche"


# === 니치 프리셋 (사전 큐레이션) ===
# slug → {name, channels, desc}. 채널: (표시명, channel_id|URL|@handle)
NICHES = {
    "emotional-vlog": {
        "name": "감성 일상 브이로그",
        "channels": [
            ("문나잇 moonnight", "UCi8PdYP_xCA4LJS2ByLhvlA"),
            ("히두부 Hiddubu", "UCziJ1h6M8hsVgze5iwnwmsg"),
            ("소이그린 SOIGREEN", "UCFlcRgtH2ERskVq5SiUPYHw"),
            ("오담필름 odamfilm", "UCmTBT0Y8mRpevqfaBR9uJMQ"),
            ("냥숲 nyangsoop", "UCrailkufB1aKrKc6l1osRgw"),
            ("백미 Backme", "UC1DG571k9MJQAIQD1EECeaA"),
            ("이욜 eyol", "UCUeVdhdq6tF4wIojud9PMdw"),
            ("현애 hyunnae", "UCdZ_qCiZG1JbjK3eFGMPrsg"),
            ("소람 soram", "UCiQv5x4DcBRvqTGAcDGt8gQ"),
            ("니지 niji", "UCaf77QdDa7onqPTl0fhSjcw"),
            ("아린 wested_arin", "UCoqkR26bl8dc7C19psm6whg"),
        ],
        "desc": (
            "저는 잔잔하고 감성적인 일상을 기록하는 브이로그 채널을 운영합니다. "
            "도시의 새벽, 카페 창밖의 비, 늦은 밤 귀갓길처럼 평범한 순간을 몽환적으로 담아요. "
            "화려한 연출보다는 잔잔한 색감과 느린 템포, 위로가 되는 한 문장을 선호합니다."
        ),
    },
}
DEFAULT_SLUG = "emotional-vlog"

# === 온디맨드 니치 (환경변수 — Actions workflow_dispatch inputs → env) ===
_env_niche_name = os.environ.get("NICHE_NAME") or None
_env_slug = os.environ.get("NICHE_SLUG") or None
_env_channels_raw = os.environ.get("CHANNELS_RAW") or None
_env_search = os.environ.get("SEARCH_KEYWORD") or None
_env_desc = os.environ.get("CHANNEL_DESC") or None

if _env_niche_name and (_env_channels_raw or _env_search):
    # 온디맨드: 채널 URL 또는 검색어로 새 니치 수집
    NICHE = _env_niche_name
    NICHE_SLUG = _slugify(_env_slug or _env_niche_name)
    CHANNEL_DESC = _env_desc or NICHE
    if _env_search:
        SEARCH_KEYWORDS = [_env_search]
        CHANNELS = []
        SOURCE_MODE = "search"
    else:
        _lines = [l.strip() for l in _env_channels_raw.splitlines() if l.strip()]
        CHANNELS = []
        for i, ln in enumerate(_lines, 1):
            if ln.startswith("@"):
                nm = ln
            else:
                nm = ln.rstrip("/").split("/")[-1] or f"채널{i}"
            CHANNELS.append((nm, ln))
        SEARCH_KEYWORDS = []
        SOURCE_MODE = "channel"
else:
    # 프리셋 (schedule 자동 갱신 + 기본)
    NICHE_SLUG = _env_slug or DEFAULT_SLUG
    _preset = NICHES.get(NICHE_SLUG, NICHES[DEFAULT_SLUG])
    NICHE = _preset["name"]
    CHANNELS = _preset["channels"]
    CHANNEL_DESC = _preset["desc"]
    SEARCH_KEYWORDS = []
    SOURCE_MODE = "channel"

# === API 키 (환경변수에서 로드, 없으면 None → 해당 단계 스킵) ===
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
ACR_ACCESS_KEY = os.environ.get("ACR_ACCESS_KEY") or None
ACR_ACCESS_SECRET = os.environ.get("ACR_ACCESS_SECRET") or None
ACR_HOST = os.environ.get("ACR_HOST") or "ap-sea-1.api.acrcloud.com"
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY") or None

# === 파이프라인 설정 ===
TARGET_COUNT = 30        # 목표 숏츠 개수
INITIAL_SEARCH = 100     # 초기 ytsearch 개수 (필터로 줄어드는 만큼 폭 넓힘)
FALLBACK_SEARCH = 200    # 미달 시 늘릴 개수
MAX_DURATION = 180       # 현대 Shorts는 최대 3분(180s)
OPENING_SECONDS = 5      # 오프닝 멘트 기준(초) — 설계 79행
WHISPER_MODEL = "small"  # faster-whisper 모델 (한국어+속도 균형)

# === 데이터 품질 필터 (filter_version=4 — 채널 기반) ===
MAX_AGE_DAYS = 180         # 업로드일이 이 일수 이내만
MIN_VIEW_COUNT = 50        # 채널 기반이라 낮게 (온니치는 채널 큐레이션으로 보장)
OUTLIER_VIEW_SHARE = 0.50  # 한 영상이 전체 조회수의 이 비율 이상 차지하면 아웃라이어
BLOCK_KEYWORDS = [
    # 음악/채널
    "Official", "Album", "Cover", "커버", "Theme", " OST", "MV", "연주곡",
    "발라드", "가요",
    # 광고/제품
    "WINIX", "위닉스", "삼성", "LG", "리뷰", "광고", "AD", "협찬", "방향제",
    "가습기", "무드등", "제품",
    # 먹방/육아/동물
    "Cat", "Kitten", "고양이", "강아지", "먹방", "맛집", "냉면", "육아", "아이",
    # 회고/나열
    "10년", "회고", "돌아가", "연도",
]

# === 경로 ===
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT = os.path.join(ROOT, "output")              # output/ (매니페스트 index.json)
OUTPUT_DIR = os.path.join(OUTPUT_ROOT, NICHE_SLUG)      # output/{slug}/ (니치별 산출물)
AUDIO_DIR = os.path.join(OUTPUT_ROOT, "audio")          # output/audio (공유, gitignore)

# === 외부 바이너리 (PATH에서 조회 — macOS homebrew / CI Ubuntu 모두 대응) ===
YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
