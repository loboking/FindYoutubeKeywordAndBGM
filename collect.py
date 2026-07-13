""" Shorts 수집 (CI 호환).
- channel 모드: 채널 /shorts 탭 flat-playlist에서 id/제목/조회수를 한 번에 가져온다.
  channel_id / 채널 URL / @handle 모두 허용.
- search 모드: ytsearch flat-playlist (오토픽 혼입 가능 — 페이지에 경고 표시).
flat-playlist는 upload_date를 안 주므로, 후보 상위 N개에 대해 개별 메타 조회로
업로드 날짜를 보강한 뒤 MAX_AGE_DAYS 필터를 적용한다. CI에서 보강이 차단되면
폴백(필터 생략). 영상별 --dump-json(무거운 전사용)은 CI IP에서 막혀 사용 안 함."""
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
    # fallback: 그대로 경로로 간주
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


def get_channel_shorts(cid_or_url, limit: int = 15) -> list[dict]:
    """채널 /shorts에서 최근 shorts (id, title, view_count[, channel]) limit개."""
    return _flat_print(_channel_shorts_url(cid_or_url), extra_fields="%(channel)s",
                       limit_arg=f"1-{limit}")


def get_search_shorts(keyword: str, limit: int = 100) -> list[dict]:
    """ytsearch에서 shorts (id, title, view_count, channel) limit개.
    오토픽 혼입 가능 — 검색어 모드는 품질이 낮을 수 있음."""
    return _flat_print(f"ytsearch{limit}:{keyword}", extra_fields="%(channel)s")


def bulk_upload_dates(ids: list[str]) -> dict:
    """영상 ID들 → {id: YYYYMMDD}. yt-dlp로 한 번에 배치 조회 (개별 영상 --print).
    CI IP 차단 시 빈 dict 반환 → 호출측에서 폴백."""
    if not ids:
        return {}
    urls = [f"https://www.youtube.com/watch?v={i}" for i in ids]
    try:
        proc = subprocess.run(
            [C.YT_DLP, "--print", "%(id)s\t%(upload_date)s",
             "--skip-download", "--no-warnings", *urls],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        print("  ⚠ 업로드 날짜 보강 타임아웃 (CI 차단 가능) → 필터 생략")
        return {}
    out = {}
    for ln in proc.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) == 2 and re.match(r"^\d{8}$", parts[1].strip()):
            out[parts[0].strip()] = parts[1].strip()
    return out


def passes_niche(v: dict) -> bool:
    """제목/채널에 BLOCK_KEYWORDS가 있으면 False. 채널 기반이라 거의 안 걸림."""
    hay = ((v.get("title") or "") + " " + (v.get("source_channel") or v.get("channel") or "")).lower()
    return not any(kw.lower() in hay for kw in C.BLOCK_KEYWORDS)


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    # 캐시: 프리셋(filter_version=5 + 대상수 충족)일 때만 스킵.
    # 온디맨드(NICHE_NAME env)는 항상 재수집.
    is_ondemand = bool(os.environ.get("NICHE_NAME"))
    if not is_ondemand and os.path.exists(out_path):
        try:
            cached = json.load(open(out_path))
            if (cached.get("filter_version") == 6
                    and len(cached.get("videos", [])) >= C.TARGET_COUNT):
                print(f"shorts.json 캐시 사용 ({len(cached['videos'])}개, filter_version=6)")
                return
        except Exception:
            pass

    per_channel: dict = {}
    all_items: list[dict] = []
    seen: set[str] = set()

    if C.SOURCE_MODE == "search":
        kw = C.SEARCH_KEYWORDS[0]
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
            per_channel.setdefault(ch, {"raw": 0, "passed": 0})["raw"] += 1
        print(f"  → {len(items)}개")
        source_tag = "search_flat"
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
        source_tag = "channel_shorts_flat"

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
        ch = it["source_channel"]
        if ch in per_channel:
            per_channel[ch]["passed"] += 1

    # 조회수 내림차순 후 상위 후보 업로드 날짜 보강 + 최근성 필터
    passed.sort(key=lambda x: -(x.get("view_count") or 0))
    candidates = passed[:120]
    dates = bulk_upload_dates([c["id"] for c in candidates])
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=C.MAX_AGE_DAYS)
    if dates and len(dates) >= max(1, len(candidates) // 2):
        # 보강 충분 → 최근성 필터 적용 (오래된 영상은 개수 부족해도 제거)
        recent = []
        for c in candidates:
            d = dates.get(c["id"])
            if not d:
                recent.append(c)
                continue
            try:
                ud = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
                if ud >= cutoff:
                    recent.append(c)
            except ValueError:
                recent.append(c)
        before, after = len(candidates), len(recent)
        print(f"최근성 필터(최근 {C.MAX_AGE_DAYS}일, 컷오프 {cutoff}): {before}→{after}개 "
              f"(오래된 영상 {before - after}개 제거)")
        shorts = recent[: C.TARGET_COUNT]
    else:
        if candidates:
            print(f"업로드 날짜 보강 부족({len(dates)}/{len(candidates)}) → 최근성 필터 생략")
        shorts = candidates[: C.TARGET_COUNT]

    videos = [
        {
            "id": s["id"],
            "title": s["title"],
            "view_count": s["view_count"],
            "duration": None,            # flat-playlist 미지원 (모두 shorts)
            "upload_date": dates.get(s["id"]),  # 보강 (YYYYMMDD) or None
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
        "filter_version": 6,
        "excluded_low_views": excl["low_views"],
        "excluded_offtopic": excl["offtopic"],
        "recency_note": "/shorts는 최신순 → 상위 15개를 최근 영상으로 간주 (정확한 날짜는 flat-playlist 미지원)",
        "videos": videos,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 "
          f"({'채널' if C.SOURCE_MODE != 'search' else '검색'} "
          f"{len(C.CHANNELS) if C.SOURCE_MODE != 'search' else 1}소스)")
    print(f"제외 - 저조회수(<{C.MIN_VIEW_COUNT}): {excl['low_views']}, "
          f"오토픽: {excl['offtopic']}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
