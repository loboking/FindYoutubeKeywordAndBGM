"""0차 스파이크 설정. 니치는 이 파일 변수 하나만 바꾸면 교체됨."""
import os
import shutil

# === 니치 (이 한 줄만 바꾸면 전체 파이프라인에 교체됨) ===
NICHE = "감성 일상 브이로그"

# yt-dlp 검색 키워드. 니치에서 파생하되 Shorts 발견율을 높이기 위해 조정.
# (니치 "감성 일상 브이로그" 그대로는 긴 영상만 나와 Shorts 0개 — 측정 기록 참고)
# 다각화: 단일 키워드로는 수집 폭이 좁아 여러 변주로 확장.
SEARCH_KEYWORDS = [
    "감성 쇼츠",
    "감성 일상 shorts",
    "힐링 일상 쇼츠",
    "감성 브이로그 shorts",
    "잔잔한 일상 shorts",
]

# === 채널 기반 수집 (이 니치의 정석) ===
# 큐레이션된 온니치 채널들의 /shorts 탭에서 수집.
# 키워드 검색은 이 니치에선 오프토픽(웹툰요약/음악MV) 투성이라 사용 안 함.
# 형식: (표시명, channel_id)
CHANNELS = [
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
]

# 내 채널 3문장 설명 (니치에 맞춰 수정 — 추천 프롬프트에 들어감)
CHANNEL_DESC = (
    "저는 잔잔하고 감성적인 일상을 기록하는 브이로그 채널을 운영합니다. "
    "도시의 새벽, 카페 창밖의 비, 늦은 밤 귀갓길처럼 평범한 순간을 몽환적으로 담아요. "
    "화려한 연출보다는 잔잔한 색감과 느린 템포, 위로가 되는 한 문장을 선호합니다."
)

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
# 채널 기반은 온니치가 이미 보장되므로 조회수 컷은 낮게(테스트 업로드만 컷).
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
OUTPUT_DIR = os.path.join(ROOT, "output")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")

# === 외부 바이너리 (PATH에서 조회 — macOS homebrew / CI Ubuntu 모두 대응) ===
YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
