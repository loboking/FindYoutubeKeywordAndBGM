"""파이프라인 orchestrator. 순차 실행, 한 단계 실패해도 다음 단계 시도."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import config as C

KST = timezone(timedelta(hours=9))


def run_step(name: str, script: str) -> int:
    print(f"\n{'='*60}\n=== {name} ===\n{'='*60}")
    proc = subprocess.run(
        [sys.executable, os.path.join(C.ROOT, script)],
        cwd=C.ROOT,
    )
    if proc.returncode != 0:
        print(f"⚠ {name} 실패 (exit {proc.returncode}) — 다음 단계로 진행")
    return proc.returncode


def update_manifest(slug: str, name: str, mode: str, last_updated: str) -> None:
    """output/index.json 매니페스트 갱신. index.html 드롭다운 소스."""
    manifest_path = os.path.join(C.OUTPUT_ROOT, "index.json")
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception:
        manifest = {"niches": [], "default": C.DEFAULT_SLUG}
    manifest.setdefault("niches", [])
    manifest["niches"] = [n for n in manifest["niches"] if n.get("slug") != slug]
    manifest["niches"].append({
        "slug": slug, "name": name, "mode": mode, "last_updated": last_updated,
    })
    if not any(n.get("slug") == manifest.get("default") for n in manifest["niches"]):
        manifest["default"] = slug
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"매니페스트 갱신: {manifest_path} (slug={slug}, mode={mode})")


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    run_step("1. 수집 (yt-dlp)", "collect.py")
    run_step("2. 전사 (faster-whisper)", "transcribe.py")
    run_step("3. BGM 식별 (ACRCloud)", "identify_bgm.py")
    run_step("4. 추천 (Claude)", "recommend.py")

    # 갱신 시각 기록 (index.html 상단 표시용)
    last_updated = datetime.now(KST).strftime("%Y-%m-%d %H:%M (KST)")
    with open(os.path.join(C.OUTPUT_DIR, "last_updated.txt"), "w") as f:
        f.write(last_updated)
    print(f"갱신 시각 기록: {last_updated}")

    # 매니페스트 갱신 (니치 드롭다운용)
    update_manifest(C.NICHE_SLUG, C.NICHE, C.SOURCE_MODE, last_updated)

    # 텔레그램 알림 (토큰/chat_id 있을 때만)
    try:
        import notify
        shorts = json.load(open(os.path.join(C.OUTPUT_DIR, "shorts.json")))
        n = len(shorts.get("videos", []))
        notify.send(
            f"*{C.NICHE}* 트렌드 갱신\n"
            f"영상 {n}개 · {last_updated}\n"
            f"https://loboking.github.io/FindYoutubeKeywordAndBGM/"
        )
    except Exception as e:
        print(f"텔레그램 알림 스킵: {e}")

    print(f"\n파이프라인 완료. 산출물: {C.OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
