"""output/index.json 매니페스트 생성. output/ 디렉토리 스캔.
matrix 각 job이 index.json을 따로 수정하면 충돌 → CI 마지막에 이 스크립트로 한 번 생성."""
import json
import os

import config as C


def main():
    niches = []
    seen = set()
    # config NICHES 순서 먼저 (프리셋 카테고리)
    for slug, info in C.NICHES.items():
        shorts_p = os.path.join(C.OUTPUT_ROOT, slug, "shorts.json")
        if not os.path.isfile(shorts_p):
            continue
        try:
            lu = open(os.path.join(C.OUTPUT_ROOT, slug, "last_updated.txt")).read().strip()
        except Exception:
            lu = ""
        niches.append({
            "slug": slug, "name": info["name"],
            "mode": info.get("mode", "category"), "last_updated": lu,
        })
        seen.add(slug)
    # 온디맨드 니치 (검색/채널 — config에 없는 output 디렉토리)
    for slug in sorted(os.listdir(C.OUTPUT_ROOT)):
        if slug in seen or slug == "audio":
            continue
        shorts_p = os.path.join(C.OUTPUT_ROOT, slug, "shorts.json")
        if not os.path.isfile(shorts_p):
            continue
        try:
            d = json.load(open(shorts_p))
            lu = open(os.path.join(C.OUTPUT_ROOT, slug, "last_updated.txt")).read().strip()
        except Exception:
            d, lu = {}, ""
        niches.append({
            "slug": slug, "name": d.get("niche", slug),
            "mode": "search" if "search" in (d.get("source") or "") else "channel",
            "last_updated": lu,
        })
    manifest = {"niches": niches, "default": C.DEFAULT_SLUG}
    out = os.path.join(C.OUTPUT_ROOT, "index.json")
    with open(out, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"index.json 생성: {len(niches)}개 니치 → {out}")


if __name__ == "__main__":
    main()
