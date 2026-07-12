"""0차 스파이크 설정. 니치는 이 파일 변수 하나만 바꾸면 교체됨."""
import os
import shutil

# === 니치 (이 한 줄만 바꾸면 전체 파이프라인에 교체됨) ===
NICHE = "감성 일상 브이로그"

# yt-dlp 검색 키워드. 니치에서 파생하되 Shorts 발견율을 높이기 위해 조정.
# (니치 "감성 일상 브이로그" 그대로는 긴 영상만 나와 Shorts 0개 — 측정 기록 참고)
SEARCH_KEYWORD = "감성 일상 shorts"

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
INITIAL_SEARCH = 50      # 초기 ytsearch 개수
FALLBACK_SEARCH = 100    # 미달 시 늘릴 개수
MAX_DURATION = 61        # Shorts 간주 기준(초) — 설계 76행
OPENING_SECONDS = 5      # 오프닝 멘트 기준(초) — 설계 79행
WHISPER_MODEL = "small"  # faster-whisper 모델 (한국어+속도 균형)

# === 경로 ===
ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "output")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")

# === 외부 바이너리 (PATH에서 조회 — macOS homebrew / CI Ubuntu 모두 대응) ===
YT_DLP = shutil.which("yt-dlp") or "yt-dlp"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
