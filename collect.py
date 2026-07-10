""" yt-dlp ytsearchN:{키워드} → duration<=61s 필터 → output/shorts.json
측정: 발견 성공률, yt-dlp 실패율."""
import json
import os
import subprocess
import sys

import config as C


def run_ytsearch(count: int) -> tuple[list[dict], int]:
    """yt-dlp ytsearchN 실행. (수집된 전체 영상 메타데이터, 시도-수집 차이) 반환."""
    query = f"ytsearch{count}:{C.SEARCH_KEYWORD}"
    proc = subprocess.run(
        [C.YT_DLP, "--dump-json", "--no-warnings", "--no-playlist", query],
        capture_output=True, text=True, timeout=600,
    )
    videos = []
    for line in proc.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            videos.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    failed = count - len(videos)  # ytsearch는 count개를 시도, 일부 실패 가능
    return videos, failed


def filter_shorts(videos: list[dict]) -> list[dict]:
    """duration <= MAX_DURATION 인 것만 Shorts로 간주 (설계 76행)."""
    out = []
    for v in videos:
        dur = v.get("duration")
        if dur is not None and dur <= C.MAX_DURATION:
            out.append(v)
    return out


def slim(v: dict) -> dict:
    """전사 단계로 넘길 최소 메타데이터만 추출."""
    vid = v.get("id") or v.get("display_id")
    return {
        "id": vid,
        "title": v.get("title", ""),
        "duration": v.get("duration"),
        "view_count": v.get("view_count"),
        "upload_date": v.get("upload_date"),
        "channel": v.get("channel") or v.get("uploader"),
        "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
    }


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    # 캐시 확인
    if os.path.exists(out_path):
        with open(out_path) as f:
            cached = json.load(f)
        if len(cached.get("videos", [])) >= C.TARGET_COUNT:
            print(f"shorts.json 캐시 사용 ({len(cached['videos'])}개)")
            return

    # 1차 검색
    print(f'ytsearch{C.INITIAL_SEARCH}:"{C.SEARCH_KEYWORD}" 실행 중...')
    videos, failed = run_ytsearch(C.INITIAL_SEARCH)
    shorts = filter_shorts(videos)
    search_used = C.INITIAL_SEARCH
    raw_count = len(videos)
    print(f"  → 수집 {raw_count}개, duration<={C.MAX_DURATION}s {len(shorts)}개, 실패 {failed}개")

    # 미달이면 2차 검색 (search 개수 확대)
    if len(shorts) < C.TARGET_COUNT:
        print(f"목표({C.TARGET_COUNT}) 미달 → ytsearch{C.FALLBACK_SEARCH}로 확대")
        videos2, failed2 = run_ytsearch(C.FALLBACK_SEARCH)
        shorts2 = filter_shorts(videos2)
        print(f"  → 수집 {len(videos2)}개, duration<={C.MAX_DURATION}s {len(shorts2)}개, 실패 {failed2}개")
        if len(shorts2) > len(shorts):
            shorts = shorts2
            search_used = C.FALLBACK_SEARCH
            raw_count = len(videos2)
            failed = failed2

    shorts = shorts[: C.TARGET_COUNT]
    result = {
        "niche": C.NICHE,
        "search_keyword": C.SEARCH_KEYWORD,
        "search_count": search_used,
        "raw_collected": raw_count,
        "shorts_found": len(shorts),
        "target": C.TARGET_COUNT,
        "ytsearch_failed": failed,
        "max_duration_s": C.MAX_DURATION,
        "videos": [slim(v) for v in shorts],
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 (ytsearch{search_used})")
    print(f"발견 성공률: {raw_count}개 중 {len(shorts)}개 Shorts "
          f"({len(shorts)/max(raw_count,1)*100:.0f}%)")
    print(f"yt-dlp 실패: {failed}개")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
