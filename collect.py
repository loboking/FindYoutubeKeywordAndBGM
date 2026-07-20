""" 카테고리 트렌드 수집 (YouTube Data API 중심).
- category: videos?chart=mostPopular&videoCategoryId=X → duration≤180s(shorts). 자동.
- search: search.list videoDuration=short → 사용자 키워드.
- channel: yt-dlp flat-playlist /shorts (온디맨드 채널 지정).
키 없으면 스킵 불가(category/search는 API 필수)."""
import datetime
import json
import os
import re
import subprocess

import config as C


def _parse_duration(iso: str) -> int | None:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def _api_get(params: dict) -> dict:
    """YouTube Data API GET. 키 필수."""
    import requests
    params = {"key": C.YOUTUBE_API_KEY, **params}
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=30)
    return r.json()


def _api_search(params: dict) -> dict:
    import requests
    params = {"key": C.YOUTUBE_API_KEY, **params}
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=30)
    return r.json()


def collect_category() -> list[dict]:
    """mostPopular(category_id) → shorts(duration≤MAX_VIDEO_DURATION). 한 번에 메타."""
    out = []
    data = _api_get({
        "chart": "mostPopular", "regionCode": "KR",
        "videoCategoryId": C.CATEGORY_ID,
        "part": "snippet,statistics,contentDetails",
        "maxResults": 50,
    })
    if "error" in data:
        print(f"  ⚠ API 오류: {data['error'].get('message', '')[:80]}")
        return out
    for i in data.get("items", []):
        dur = _parse_duration((i.get("contentDetails") or {}).get("duration") or "")
        if dur is None or dur > C.MAX_VIDEO_DURATION:
            continue
        snip = i.get("snippet", {})
        stats = i.get("statistics", {})
        ch = snip.get("channelTitle", "")
        out.append({
            "id": i["id"],
            "title": snip.get("title", ""),
            "view_count": int(stats.get("viewCount", 0) or 0),
            "duration": dur,
            "upload_date": (snip.get("publishedAt") or "")[:10].replace("-", ""),
            "category": snip.get("categoryId"),
            "channel": ch,
            "source_channel": ch,
            "url": f"https://www.youtube.com/watch?v={i['id']}",
        })
    return out


def collect_search(keyword: str) -> list[dict]:
    """search.list videoDuration=short → IDs → videos.list로 메타 보강."""
    ids = []
    data = _api_search({
        "part": "snippet", "q": keyword, "type": "video",
        "videoDuration": "short", "order": "viewCount",
        "regionCode": "KR", "relevanceLanguage": "ko", "maxResults": 50,
    })
    if "error" in data:
        print(f"  ⚠ search 오류: {data['error'].get('message', '')[:80]}")
        return []
    for i in data.get("items", []):
        vid = (i.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)
    if not ids:
        return []
    # videos.list로 duration/date/view 보강
    out = []
    for j in range(0, len(ids), 50):
        chunk = ids[j:j + 50]
        vdata = _api_get({"part": "snippet,statistics,contentDetails", "id": ",".join(chunk)})
        for i in vdata.get("items", []):
            dur = _parse_duration((i.get("contentDetails") or {}).get("duration") or "")
            snip = i.get("snippet", {})
            stats = i.get("statistics", {})
            ch = snip.get("channelTitle", "")
            out.append({
                "id": i["id"],
                "title": snip.get("title", ""),
                "view_count": int(stats.get("viewCount", 0) or 0),
                "duration": dur,
                "upload_date": (snip.get("publishedAt") or "")[:10].replace("-", ""),
                "category": snip.get("categoryId"),
                "channel": ch,
                "source_channel": ch,
                "url": f"https://www.youtube.com/watch?v={i['id']}",
            })
    return out


def get_channel_shorts(cid_or_url, limit=30):
    x = cid_or_url.strip()
    if x.startswith("http"):
        url = x.rstrip("/") + "/shorts"
    elif x.startswith("@"):
        url = f"https://www.youtube.com/{x}/shorts"
    elif x.startswith("UC"):
        url = f"https://www.youtube.com/channel/{x}/shorts"
    else:
        url = f"https://www.youtube.com/{x}/shorts"
    proc = subprocess.run(
        [C.YT_DLP, "--flat-playlist", "--playlist-items", f"1-{limit}",
         "--print", "%(id)s\t%(title)s\t%(view_count)s", "--no-warnings", url],
        capture_output=True, text=True, timeout=180,
    )
    out = []
    for ln in proc.stdout.splitlines():
        parts = ln.strip().split("\t")
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


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    if not C.YOUTUBE_API_KEY and C.SOURCE_MODE in ("category", "search"):
        print("⚠ YOUTUBE_API_KEY 미설정 — category/search 모드 불가")
        return

    if C.SOURCE_MODE == "category":
        print(f"mostPopular 수집: 카테고리 {C.CATEGORY_ID} ({C.NICHE})")
        items = collect_category()
        source_tag = "mostpopular_category"
    elif C.SOURCE_MODE == "search":
        print(f"search.list 수집: {C.SEARCH_KEYWORDS[0]}")
        items = collect_search(C.SEARCH_KEYWORDS[0])
        source_tag = "search_list_short"
    else:  # channel 온디맨드
        items = []
        seen = set()
        for name, cid in C.CHANNELS:
            print(f"채널 /shorts 수집: {name}")
            raw = get_channel_shorts(cid, limit=30)
            for it in raw:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                it["source_channel"] = name
                it["channel"] = name
                it["url"] = f"https://www.youtube.com/watch?v={it['id']}"
                items.append(it)
        source_tag = "channel_flat"

    print(f"수집: {len(items)}개")

    # 정렬 + 상위 TARGET_COUNT
    items.sort(key=lambda x: -(x.get("view_count") or 0))
    shorts = items[: C.TARGET_COUNT]

    result = {
        "niche": C.NICHE,
        "slug": C.NICHE_SLUG,
        "source": source_tag,
        "category_id": C.CATEGORY_ID,
        "shorts_found": len(shorts),
        "target": C.TARGET_COUNT,
        "max_video_duration": C.MAX_VIDEO_DURATION,
        "filter_version": 8,
        "videos": shorts,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"수집 완료: {len(shorts)}/{C.TARGET_COUNT}개 | 저장: {out_path}")


if __name__ == "__main__":
    main()
