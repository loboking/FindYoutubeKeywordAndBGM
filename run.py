"""파이프라인 orchestrator. 순차 실행, 한 단계 실패해도 다음 단계 시도."""
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

    print(f"\n파이프라인 완료. 산출물: {C.OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
