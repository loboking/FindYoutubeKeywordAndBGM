"""faster-whisper 전사. 오프닝 멘트 = 앞 5초 오디오 세그먼트의 전사 (설계 79행).
캐시: output/transcripts.json 이 있으면 완료된 영상은 건너뜀 (whisper 재실행 절감).
환경변수 TRANSCRIBE_LIMIT=N 으로 앞 N개만 전사 (샘플 검증용)."""
import json
import os
import subprocess
import sys
import time

import config as C


def download_audio(video_id: str) -> str | None:
    """yt-dlp로 오디오 다운로드 (m4a/webm). 경로 반환 or None."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_tmpl = os.path.join(C.AUDIO_DIR, f"{video_id}.%(ext)s")
    proc = subprocess.run(
        [C.YT_DLP, "-f", "bestaudio/best", "-o", out_tmpl,
         "--no-warnings", "--no-playlist", url],
        capture_output=True, text=True, timeout=120,
    )
    # 실제 저장된 파일 찾기
    for ext in ("m4a", "webm", "opus", "mp3", "mp4"):
        p = os.path.join(C.AUDIO_DIR, f"{video_id}.{ext}")
        if os.path.exists(p):
            return p
    return None


def to_wav(audio_path: str, wav_path: str) -> bool:
    """ffmpeg로 16kHz mono wav 변환."""
    proc = subprocess.run(
        [C.FFMPEG, "-y", "-i", audio_path,
         "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode == 0


def transcribe(wav_path: str, model) -> dict:
    """faster-whisper 전사. 전체 텍스트 + 세그먼트 + 오프닝 멘트(앞 5초).
    full_text가 빈 경우 transcribe_status='empty'로 마킹 (무음/BGM-only 가능성)."""
    segments, info = model.transcribe(
        wav_path, language="ko", vad_filter=True,
        beam_size=5,
    )
    seg_list = []
    opening_parts = []
    full_parts = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        entry = {"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text}
        seg_list.append(entry)
        full_parts.append(text)
        # 오프닝 멘트 = end <= OPENING_SECONDS 인 세그먼트 (앞 5초)
        if seg.end <= C.OPENING_SECONDS:
            opening_parts.append(text)
    full_text = " ".join(full_parts).strip()
    return {
        "full_text": full_text,
        "segments": seg_list,
        "opening_mention": " ".join(opening_parts).strip(),
        "language": info.language,
        "transcribe_status": "empty" if not full_text else "ok",
    }


def save(transcripts: dict, path: str):
    with open(path, "w") as f:
        json.dump(transcripts, f, ensure_ascii=False, indent=2)


def main():
    from faster_whisper import WhisperModel

    os.makedirs(C.AUDIO_DIR, exist_ok=True)
    shorts_path = os.path.join(C.OUTPUT_DIR, "shorts.json")
    out_path = os.path.join(C.OUTPUT_DIR, "transcripts.json")

    with open(shorts_path) as f:
        shorts = json.load(f)
    videos = shorts["videos"]

    # 샘플링 (검증용)
    limit = int(os.environ.get("TRANSCRIBE_LIMIT", "0"))
    if limit:
        videos = videos[:limit]
        print(f"[샘플 모드] 앞 {limit}개만 전사")

    # 캐시 로드
    transcripts = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            transcripts = json.load(f)

    # 잔류 정리: 현재 shorts에 없는 이전 실행분은 삭제 (누적 방지 — insights 왜곡 원인)
    current_ids = {v["id"] for v in videos}
    stale = [k for k in list(transcripts) if k not in current_ids]
    for k in stale:
        del transcripts[k]
    if stale:
        print(f"이전 잔류 정리: {len(stale)}개 삭제 (현재 shorts에 없는 영상)")

    print(f'faster-whisper 모델 로드: {C.WHISPER_MODEL} (device=cpu, compute=int8)')
    model = WhisperModel(C.WHISPER_MODEL, device="cpu", compute_type="int8")

    start = time.time()
    success, failed, empty = 0, 0, 0
    total = len(videos)

    for i, v in enumerate(videos):
        vid = v["id"]
        # 캐시 스킵 (transcribe_version==2 + opening_mention 키 있으면 완료)
        if (vid in transcripts
                and transcripts[vid].get("transcribe_version") == 2
                and "opening_mention" in transcripts[vid]):
            print(f"[{i+1}/{total}] {vid} 캐시 스킵")
            success += 1
            if transcripts[vid].get("transcribe_status") == "empty":
                empty += 1
            continue

        print(f"[{i+1}/{total}] {vid} ({v.get('title','')[:30]}) 전사 중...")
        t0 = time.time()
        try:
            audio = download_audio(vid)
            if not audio:
                raise RuntimeError("audio_download_failed")
            wav_path = os.path.join(C.AUDIO_DIR, f"{vid}.wav")
            if not to_wav(audio, wav_path):
                raise RuntimeError("ffmpeg_failed")
            result = transcribe(wav_path, model)
            transcripts[vid] = {**v, **result, "transcribe_version": 2}
            elapsed_v = time.time() - t0
            opening = result["opening_mention"][:40] or "(없음)"
            status_tag = " [empty]" if result["transcribe_status"] == "empty" else ""
            print(f"  → {elapsed_v:.1f}초 | 오프닝: {opening}{status_tag}")
            success += 1
            if result["transcribe_status"] == "empty":
                empty += 1
        except Exception as e:
            print(f"  ✗ 실패: {e}")
            transcripts[vid] = {**v, "error": str(e), "transcribe_version": 2}
            failed += 1

        # 5개마다 저장 (크래시 대비)
        if (i + 1) % 5 == 0:
            save(transcripts, out_path)

    elapsed = time.time() - start
    save(transcripts, out_path)

    print(f"\n전사 완료: 성공 {success}, 실패 {failed}, 총 소요 {elapsed:.1f}초 "
          f"(영상당 {elapsed/max(success,1):.1f}초)")
    print(f"전사 비어있음(empty): {empty}개")
    print(f"모델: faster-whisper {C.WHISPER_MODEL} | 오프닝 기준: 앞 {C.OPENING_SECONDS}초")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
