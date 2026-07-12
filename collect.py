""" 채널 기반 Shorts 수집.
큐레이션된 온니치 채널들의 /shorts 탭에서 최근 shorts ID를 가져오고,
메타데이터(duration/view_count/upload_date)를 배치 수집한 뒤 필터 → output/shorts.json.
키워드 검색은 이 니치에선 오프토픽 투성이(웹툰요약/음악MV)라 사용하지 않는다."""
import datetime
import json
import os
import subprocess

import config as C


def get_recent_short_ids(cid: str, limit: int = 15) -> list[str]:
    """채널 /shorts 탭에서 최근 shorts 영상 ID limit개 (/shorts는 기본 최신순)."""
    url = f"https://www.youtube.com/channel/{cid}/shorts"
    proc = subprocess.run(
        [C.YT_DLP, "--flat-playlist", "--playlist-items", f"1-{limit}",
         "--print", "%(id)s", "--no-warnings", url],
        capture_output=True, text=True, timeout=180,
    )
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def fetch_metadata(ids: list[str], chunk: int = 20) -> list[dict]:
    """영상 ID들로부터 전체 메타데이터 배치 수집 (duration/view_count/upload_date/title/channel)."""
    metas = []
    for i in range(0, len(ids), chunk):
        batch = ids[i:i + chunk]
        urls = [f"https://www.youtube.com/watch?v={v}" for v in batch]
        proc = subprocess.run(
            [C.YT_DLP, "--dump-json", "--skip-download", "--no-warnings", *urls],
            capture_output=True, text=True, timeout=600,
        )
        for line in proc.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                metas.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return metas


def is_recent(upload_date_str, max_age_days: int) -> bool:
    """upload_date("YYYYMMDD")가 오늘 기준 max_age_days 이내면 True. 파싱 실패/None이면 False."""
    if not upload_date_str or len(str(upload_date_str)) != 8:
        return False
    try:
        s = str(upload_date_str)
        d = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return False
    return (datetime.date.today() - d).days <= max_age_days


def passes_niche(v: dict) -> tuple[bool, str]:
    """제목/채널에 BLOCK_KEYWORDS 중 하나라도 있으면 (False, 'block:<kw>'). 채널 기반이라 거의 안 걸리지만 안전장치."""
    hay = " ".join([
        v.get("title", "") or "",
        v.get("channel", "") or "",
        v.get("uploader", "") or "",
    ]).lower()
    for kw in C.BLOCK_KEYWORDS:
        if kw.lower() in hay:
            return False, f"block:{kw.strip()}"
    return True, "ok"


def apply_filters(videos: list[dict]) -> tuple[list[dict], dict]:
    """duration + 최근성 + 조회수 + 니치 적합도."""
    out = []
    counts = {"excluded_offtopic": 0, "excluded_too_old": 0,
              "excluded_low_views": 0, "excluded_too_long": 0}
    for v in videos:
        dur = v.get("duration")
        if dur is None or dur > C.MAX_DURATION:
            counts["excluded_too_long"] += 1
            continue
        if not is_recent(v.get("upload_date"), C.MAX_AGE_DAYS):
            counts["excluded_too_old"] += 1
            continue
        views = v.get("view_count") or 0
        if views < C.MIN_VIEW_COUNT:
            counts["excluded_low_views"] += 1
            continue
        ok, _ = passes_niche(v)
        if not ok:
            counts["excluded_offtopic"] += 1
            continue
        out.append(v)
    return out, counts


def slim(v: dict, source_channel: str) -> dict:
    vid = v.get("id") or v.get("display_id")
    return {
        "id": vid,
        "title": v.get("title", ""),
        "duration": v.get("duration"),
        "view_count": v.get("view_count"),
        "upload_date": v.get("upload_date"),
        "channel": v.get("channel") or v.get("uploader") or source_channel,
        "source_channel": source_channel,
        "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
    }


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    # 캐시: filter_version=4(채널기반) + 대상수 충족 시 스킵
    if os.path.exists(out_path):
        try:
            cached = json.load(open(out_path))
            if (cached.get("filter_version") == 4
                    and len(cached.get("videos", [])) >= C.TARGET_COUNT):
                print(f"shorts.json 캐시 사용 ({len(cached['videos'])}개, filter_version=4)")
                return
        except Exception:
            pass

    # 1) 각 채널 /shorts에서 최근 ID 수집 + 중복 제거
    per_channel = {}
    id_to_src: dict[str, str] = {}
    all_ids: list[str] = []
    for name, cid in C.CHANNELS:
        print(f"채널 /shorts 수집: {name}")
        ids = get_recent_short_ids(cid, limit=15)
        per_channel[name] = {"raw": len(ids), "passed": 0}
        for vid in ids:
            if vid and vid not in id_to_src:
                id_to_src[vid] = name
                all_ids.append(vid)
        print(f"  → {len(ids)}개 ID")

    print(f"\n총 {len(all_ids)}개 고유 ID. 메타데이터 배치 수집 중...")
    metas = fetch_metadata(all_ids)
    print(f"메타데이터 확보: {len(metas)}/{len(all_ids)}")

    # 2) 필터 적용
    shorts, excl = apply_filters(metas)

    # 3) 출처 채널 태깅 + 채널별 통과 수
    for v in shorts:
        vid = v.get("id") or v.get("display_id")
        src = id_to_src.get(vid, "?")
        v["_source_channel"] = src
        if src in per_channel:
            per_channel[src]["passed"] += 1

    shorts = shorts[: C.TARGET_COUNT]

    result = {
        "niche": C.NICHE,
        "source": "channel_shorts",
        "channels": [n for n, _ in C.CHANNELS],
        "per_channel": per_channel,
        "raw_ids": len(all_ids),
        "meta_fetched": len(metas),
        "shorts_found": len(shorts),
        "target": C.TARGET_COUNT,
        "max_duration_s": C.MAX_DURATION,
        "max_age_days": C.MAX_AGE_DAYS,
        "min_view_count": C.MIN_VIEW_COUNT,
        "filter_version": 4,
        "excluded_offtopic": excl["excluded_offtopic"],
        "excluded_too_old": excl["excluded_too_old"],
        "excluded_low_views": excl["excluded_low_views"],
        "excluded_too_long": excl["excluded_too_long"],
        "videos": [slim(v, v.get("_source_channel", "?")) for v in shorts],
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 (채널 {len(C.CHANNELS)}개)")
    print(f"제외 - 너무 김(>{C.MAX_DURATION}s): {excl['excluded_too_long']}, "
          f"오래됨(>{C.MAX_AGE_DAYS}일): {excl['excluded_too_old']}, "
          f"저조회수(<{C.MIN_VIEW_COUNT}): {excl['excluded_low_views']}, "
          f"오프토픽: {excl['excluded_offtopic']}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
