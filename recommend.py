"""insights 생성. 카테고리/search 모드는 메타 통계 중심.
channel 모드(전사 있을 때)는 voice_pattern/plans 보강 가능."""
import json
import os
import re
from collections import Counter

import config as C

INSIGHTS_PATH = os.path.join(C.OUTPUT_DIR, "insights.json")


def _extract_keywords(videos: list[dict]) -> list[str]:
    """제목에서 해시태그 + 의미 토큰 빈도 추출 (빈도 기반)."""
    stop = {"오늘", "하루", "나", "내", "우리", "때", "것", "더", "shorts", "쇼츠", "영상", "편집"}
    tokens = []
    for v in videos:
        t = v.get("title", "") or ""
        for tag in re.findall(r"#([0-9A-Za-z가-힣_]+)", t):
            tokens.append("#" + tag)
        for w in re.split(r"[\s\U0001f000-\U000effff\-_/,.!?~()|:+\"]+", t):
            w = w.strip()
            if not w or w.startswith("#") or w.lower() in stop:
                continue
            if not re.search(r"[0-9A-Za-z가-힣]", w):
                continue
            if len(w) >= 2:
                tokens.append(w)
    return [k for k, _ in Counter(tokens).most_common(20) if k]


def build_insights(shorts: dict, transcripts: dict | None = None, bgm: dict | None = None) -> dict:
    videos = shorts.get("videos", [])
    n = len(videos)
    sorted_vids = sorted(videos, key=lambda x: -(x.get("view_count") or 0))

    # 상위 5
    top5 = [
        {"views": v.get("view_count"), "title": v.get("title", ""),
         "upload_year": (v.get("upload_date") or "")[:4] or None,
         "channel": v.get("channel", ""), "duration": v.get("duration")}
        for v in sorted_vids[:5]
    ]

    # 아웃라이어 (1위 과점)
    total_views = sum((v.get("view_count") or 0) for v in videos)
    has_outlier = False
    top1_share = None
    avg_excl = None
    note = ""
    if total_views > 0 and sorted_vids:
        top1_views = sorted_vids[0].get("view_count") or 0
        top1_share = round(top1_views / total_views, 2)
        if top1_share >= C.OUTLIER_VIEW_SHARE:
            has_outlier = True
            remaining = [v.get("view_count") or 0 for v in sorted_vids[1:]]
            avg_excl = round(sum(remaining) / len(remaining)) if remaining else 0
            note = f"1위가 전체 조회수의 {top1_share*100:.0f}% 차지 — 평균 왜곡."
    outlier_adjusted = {
        "has_outlier": has_outlier, "top1_share": top1_share,
        "avg_views_excluding_top1": avg_excl, "note": note,
    }

    # 채널 분포 (카테고리 트렌드에서 유용)
    channel_dist = Counter(v.get("channel", "?") for v in videos).most_common(10)

    # formula
    trend_keywords = _extract_keywords(videos)
    if trend_keywords:
        formula = f"카테고리 인기 shorts(n={n})에서 두드러진 소재/키워드: {', '.join(trend_keywords[:6])}"
    else:
        formula = f"카테고리 인기 shorts(n={n}). 상위 채널: {', '.join(c for c, _ in channel_dist[:3])}"

    insights = {
        "generated_by": "meta_stats",
        "niche": C.NICHE,
        "slug": C.NICHE_SLUG,
        "source_mode": C.SOURCE_MODE,
        "formula": formula,
        "top_videos_summary": top5,
        "outlier_adjusted": outlier_adjusted,
        "trend_keywords": trend_keywords,
        "channel_distribution": [{"channel": c, "count": cnt} for c, cnt in channel_dist],
        "voice_pattern": None,   # channel 모드(전사 있을 때)만
        "bgm_trends": [],
        "plans": [],
    }

    # channel 모드 + 전사 데이터 있으면 voice_pattern 보강
    if transcripts and C.SOURCE_MODE == "channel":
        transcribed = [t for t in transcripts.values() if isinstance(t, dict) and t.get("full_text")]
        denom = len(transcribed)
        opening = sum(1 for t in transcribed if t.get("opening_mention"))
        if denom > 0:
            pct = round(opening / denom * 100)
            insights["voice_pattern"] = {
                "speech_in_first_5s_percent": pct, "n": denom,
                "summary": f"전사 확보 {denom}개 중 앞5초 말 {opening}개({pct}%)",
                "patterns": [],
            }

    return insights


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    shorts_path = os.path.join(C.OUTPUT_DIR, "shorts.json")
    transcripts_path = os.path.join(C.OUTPUT_DIR, "transcripts.json")
    bgm_path = os.path.join(C.OUTPUT_DIR, "bgm.json")

    with open(shorts_path) as f:
        shorts = json.load(f)

    transcripts = None
    bgm = None
    if os.path.exists(transcripts_path):
        with open(transcripts_path) as f:
            transcripts = json.load(f)
    if os.path.exists(bgm_path):
        with open(bgm_path) as f:
            bgm = json.load(f)

    insights = build_insights(shorts, transcripts, bgm)
    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    print(f"insights.json 저장: {INSIGHTS_PATH} (source={C.SOURCE_MODE}, n={len(shorts.get('videos',[]))})")


if __name__ == "__main__":
    main()
