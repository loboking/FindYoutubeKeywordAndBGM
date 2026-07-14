""" Shorts 수집 + API 정제.
- channel 모드: 채널 /shorts 탭 flat-playlist.
- search 모드: ytsearch(키워드) flat-playlist → 넓은 트렌드 풀.
공통: YouTube Data API videos.list로 (date, duration, categoryId) 보강한 뒤
  shorts(duration≤MAX_SHORT_DURATION) + 최근(MAX_AGE_DAYS) + 오토픽(BLOCKED_CATEGORIES) 필터.
flat-playlist는 upload_date/duration을 안 주므로 API 보강이 필수. 키 없으면 폴백(필터 생략)."""
import datetime
import json
import os
import re
import subprocess

import config as C


def _channel_shorts_url(cid_or_url: str) -> str:
    """channel_id / URL / @handle → /shorts 플레이리스트 URL."""
    x = cid_or_url.strip()
    if x.startswith("http"):
        return x.rstrip("/") + "/shorts"
    if x.startswith("@"):
        return f"https://www.youtube.com/{x}/shorts"
    if x.startswith("UC"):
        return f"https://www.youtube.com/channel/{x}/shorts"
    return f"https://www.youtube.com/{x}/shorts"


def _flat_print(url: str, extra_fields: str = "", limit_arg: str = None) -> list[dict]:
    """공통 flat-playlist 호출. 탭 구분 출력 파싱."""
    fmt = "%(id)s\t%(title)s\t%(view_count)s" + (f"\t{extra_fields}" if extra_fields else "")
    cmd = [C.YT_DLP, "--flat-playlist", "--print", fmt, "--no-warnings"]
    if limit_arg:
        cmd += ["--playlist-items", limit_arg]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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
            item = {"id": vid, "title": title, "view_count": views}
            if len(parts) >= 4:
                item["channel"] = parts[3]
            out.append(item)
    return out


def get_channel_shorts(cid_or_url, limit: int = 30) -> list[dict]:
    """채널 /shorts에서 최근 shorts limit개."""
    return _flat_print(_channel_shorts_url(cid_or_url), extra_fields="%(channel)s",
                       limit_arg=f"1-{limit}")


def get_search_shorts(keyword: str, limit: int = 100) -> list[dict]:
    """ytsearch에서 영상 limit개. shorts/일반 섞임 → API로 duration 정제 필요."""
    return _flat_print(f"ytsearch{limit}:{keyword}", extra_fields="%(channel)s")


def _parse_duration(iso: str) -> int | None:
    """ISO 8601 duration(PT1M30S) → 초. 실패 시 None."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def bulk_video_meta(ids: list[str]) -> dict:
    """영상 ID들 → {id: {date, duration, category}}. YouTube Data API videos.list.
    part=snippet(contentDetails 포함은 별도). 한 번에 50개. 키/오류 시 빈 dict → 폴백."""
    if not ids or not C.YOUTUBE_API_KEY:
        if ids:
            print("  ⚠ YOUTUBE_API_KEY 미설정 → 메타 보강 불가 (필터 생략)")
        return {}
    import requests
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"key": C.YOUTUBE_API_KEY, "part": "snippet,contentDetails",
                        "id": ",".join(chunk)},
                timeout=30,
            )
            data = r.json()
        except Exception as e:
            print(f"  ⚠ YouTube API 요청 실패: {e} → 필터 생략")
            return {}
        if "error" in data:
            print(f"  ⚠ YouTube API 오류: {data['error'].get('message', '')[:80]} → 필터 생략")
            return {}
        for item in data.get("items", []):
            snip = item.get("snippet", {})
            cd = item.get("contentDetails", {})
            d = (snip.get("publishedAt") or "")[:10].replace("-", "")
            out[item["id"]] = {
                "date": d if re.match(r"^\d{8}$", d) else None,
                "duration": _parse_duration(cd.get("duration") or ""),
                "category": snip.get("categoryId"),
            }
    return out


def passes_niche(v: dict) -> bool:
    """제목/채널에 BLOCK_KEYWORDS가 있으면 False."""
    hay = ((v.get("title") or "") + " " + (v.get("source_channel") or v.get("channel") or "")).lower()
    return not any(kw.lower() in hay for kw in C.BLOCK_KEYWORDS)


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    is_ondemand = bool(os.environ.get("NICHE_NAME"))
    if not is_ondemand and os.path.exists(out_path):
        try:
            cached = json.load(open(out_path))
            if (cached.get("filter_version") == 7
                    and len(cached.get("videos", [])) >= 1):
                print(f"shorts.json 캐시 사용 ({len(cached['videos'])}개, filter_version=7)")
                return
        except Exception:
            pass

    per_channel: dict = {}
    all_items: list[dict] = []
    seen: set[str] = set()

    if C.SOURCE_MODE == "search":
        for kw in C.SEARCH_KEYWORDS:
            print(f"ytsearch 수집: {kw}")
            items = get_search_shorts(kw, limit=C.INITIAL_SEARCH)
            for it in items:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                ch = it.pop("channel", None) or "(검색)"
                it["source_channel"] = ch
                it["channel"] = ch
                all_items.append(it)
                per_channel.setdefault(kw, {"raw": 0, "passed": 0})["raw"] += 1
            print(f"  → {len(items)}개 (고유 누적 {len(all_items)})")
        source_tag = "search_api_refined"
    else:
        for name, cid in C.CHANNELS:
            print(f"채널 /shorts 수집: {name}")
            items = get_channel_shorts(cid, limit=30)
            per_channel[name] = {"raw": len(items), "passed": 0}
            for it in items:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                ch = it.pop("channel", None) or name
                it["source_channel"] = name
                it["channel"] = ch
                all_items.append(it)
            print(f"  → {len(items)}개")
        source_tag = "channel_api_refined"

    print(f"\n총 {len(all_items)}개 고유. 1차 필터(조회수≥{C.MIN_VIEW_COUNT} + 오토픽 키워드)...")
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
        key = it["source_channel"] if C.SOURCE_MODE != "search" else next(iter(per_channel))
        if key in per_channel:
            per_channel[key]["passed"] += 1

    # 2차: API 보강(duration/date/category) 후 shorts+최근+카테고리 필터
    passed.sort(key=lambda x: -(x.get("view_count") or 0))
    candidates = passed[:150]
    meta = bulk_video_meta([c["id"] for c in candidates])
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=C.MAX_AGE_DAYS)

    if meta and len(meta) >= max(1, len(candidates) // 2):
        recent = []
        drop_dur = drop_cat = drop_old = 0
        for c in candidates:
            m = meta.get(c["id"], {})
            dur = m.get("duration")
            # shorts 필터 (duration 알면 ≤61s만; 모르면 통과 — /shorts 탭은 이미 shorts)
            if dur is not None and dur > C.MAX_SHORT_DURATION:
                drop_dur += 1
                continue
            if m.get("category") in C.BLOCKED_CATEGORIES:
                drop_cat += 1
                continue
            d = m.get("date")
            if not d:
                recent.append(c)
                continue
            try:
                ud = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
                if ud >= cutoff:
                    c["_date"] = d
                    recent.append(c)
                else:
                    drop_old += 1
            except ValueError:
                recent.append(c)
        print(f"API 정제: 후보 {len(candidates)} → {len(recent)} "
              f"(duration>61s 제거 {drop_dur}, 카테고리 제거 {drop_cat}, "
              f"오래된(>{C.MAX_AGE_DAYS}일) 제거 {drop_old})")
        shorts = recent[: C.TARGET_COUNT]
    else:
        if candidates:
            print(f"API 보강 부족({len(meta)}/{len(candidates)}) → 정제 필터 생략 (주의: 잡음 가능)")
        shorts = candidates[: C.TARGET_COUNT]

    videos = [
        {
            "id": s["id"],
            "title": s["title"],
            "view_count": s["view_count"],
            "duration": meta.get(s["id"], {}).get("duration"),
            "upload_date": s.get("_date") or meta.get(s["id"], {}).get("date"),
            "category": meta.get(s["id"], {}).get("category"),
            "channel": s["channel"],
            "source_channel": s["source_channel"],
            "url": f"https://www.youtube.com/watch?v={s['id']}",
        }
        for s in shorts
    ]

    result = {
        "niche": C.NICHE,
        "slug": C.NICHE_SLUG,
        "source": source_tag,
        "channels": [n for n, _ in C.CHANNELS] if C.SOURCE_MODE != "search" else list(per_channel.keys()),
        "per_channel": per_channel,
        "raw_ids": len(all_items),
        "shorts_found": len(shorts),
        "target": C.TARGET_COUNT,
        "min_view_count": C.MIN_VIEW_COUNT,
        "max_age_days": C.MAX_AGE_DAYS,
        "max_short_duration": C.MAX_SHORT_DURATION,
        "blocked_categories": sorted(C.BLOCKED_CATEGORIES),
        "filter_version": 7,
        "excluded_low_views": excl["low_views"],
        "excluded_offtopic": excl["offtopic"],
        "recency_note": f"최근 {C.MAX_AGE_DAYS}일 + duration≤{C.MAX_SHORT_DURATION}s + 카테고리 필터 (API 정제)",
        "videos": videos,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 "
          f"({'검색 ' + str(len(C.SEARCH_KEYWORDS)) + '키워드' if C.SOURCE_MODE == 'search' else '채널 ' + str(len(C.CHANNELS))})")
    print(f"1차 제외 - 저조회수(<{C.MIN_VIEW_COUNT}): {excl['low_views']}, 오토픽 키워드: {excl['offtopic']}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
