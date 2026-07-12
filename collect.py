""" 채널 기반 Shorts 수집 (CI 호환).
채널 /shorts 탭의 flat-playlist에서 id/제목/조회수를 한 번에 가져온다.
영상별 --dump-json은 CI IP에서 YouTube에 막혀 0건이 되므로 사용하지 않는다.
최근성: /shorts 탭은 기본 최신순 → 상위 N개를 '최근 영상'으로 간주."""
import json
import os
import subprocess

import config as C


def get_channel_shorts(cid: str, limit: int = 15) -> list[dict]:
    """채널 /shorts에서 최근 shorts (id, title, view_count) limit개."""
    url = f"https://www.youtube.com/channel/{cid}/shorts"
    proc = subprocess.run(
        [C.YT_DLP, "--flat-playlist", "--playlist-items", f"1-{limit}",
         "--print", "%(id)s\t%(title)s\t%(view_count)s", "--no-warnings", url],
        capture_output=True, text=True, timeout=180,
    )
    out = []
    for ln in proc.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = ln.split("\t")
        if len(parts) < 3:
            continue
        vid, title, vc = parts[0], parts[1], parts[2]
        try:
            views = int(vc) if vc and vc != "NA" else 0
        except ValueError:
            views = 0
        if vid and vid != "NA":
            out.append({"id": vid, "title": title, "view_count": views})
    return out


def passes_niche(v: dict) -> bool:
    """제목/채널에 BLOCK_KEYWORDS가 있으면 False. 채널 기반이라 거의 안 걸림."""
    hay = ((v.get("title") or "") + " " + (v.get("source_channel") or "")).lower()
    return not any(kw.lower() in hay for kw in C.BLOCK_KEYWORDS)


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    # 캐시: filter_version=5(flat-playlist) + 대상수 충족 시 스킵
    if os.path.exists(out_path):
        try:
            cached = json.load(open(out_path))
            if (cached.get("filter_version") == 5
                    and len(cached.get("videos", [])) >= C.TARGET_COUNT):
                print(f"shorts.json 캐시 사용 ({len(cached['videos'])}개, filter_version=5)")
                return
        except Exception:
            pass

    per_channel: dict = {}
    all_items: list[dict] = []
    seen: set[str] = set()
    for name, cid in C.CHANNELS:
        print(f"채널 /shorts 수집: {name}")
        items = get_channel_shorts(cid, limit=15)
        per_channel[name] = {"raw": len(items), "passed": 0}
        for it in items:
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            it["source_channel"] = name
            it["channel"] = name
            all_items.append(it)
        print(f"  → {len(items)}개")

    print(f"\n총 {len(all_items)}개 고유. 필터링(조회수≥{C.MIN_VIEW_COUNT} + 오토픽 제외)...")
    passed: list[dict] = []
    excl = {"offtopic": 0, "low_views": 0}
    for it in all_items:
        if (it.get("view_count") or 0) < C.MIN_VIEW_COUNT:
            excl["low_views"] += 1
            continue
        if not passes_niche(it):
            excl["offtopic"] += 1
            continue
        passed.append(it)
        if it["source_channel"] in per_channel:
            per_channel[it["source_channel"]]["passed"] += 1

    # 조회수 내림차순(=최근 영상들 중 인기순) 후 상위 TARGET_COUNT
    passed.sort(key=lambda x: -(x.get("view_count") or 0))
    shorts = passed[: C.TARGET_COUNT]

    videos = [
        {
            "id": s["id"],
            "title": s["title"],
            "view_count": s["view_count"],
            "duration": None,            # flat-playlist 미지원 (모두 shorts)
            "upload_date": None,         # flat-playlist 미지원 (/shorts 최신순 상위 = 최근)
            "channel": s["channel"],
            "source_channel": s["source_channel"],
            "url": f"https://www.youtube.com/watch?v={s['id']}",
        }
        for s in shorts
    ]

    result = {
        "niche": C.NICHE,
        "source": "channel_shorts_flat",
        "channels": [n for n, _ in C.CHANNELS],
        "per_channel": per_channel,
        "raw_ids": len(all_items),
        "shorts_found": len(shorts),
        "target": C.TARGET_COUNT,
        "min_view_count": C.MIN_VIEW_COUNT,
        "filter_version": 5,
        "excluded_low_views": excl["low_views"],
        "excluded_offtopic": excl["offtopic"],
        "recency_note": "/shorts는 최신순 → 상위 15개를 최근 영상으로 간주 (정확한 날짜는 flat-playlist 미지원)",
        "videos": videos,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 (채널 {len(C.CHANNELS)}개)")
    print(f"제외 - 저조회수(<{C.MIN_VIEW_COUNT}): {excl['low_views']}, "
          f"오프토픽: {excl['offtopic']}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
