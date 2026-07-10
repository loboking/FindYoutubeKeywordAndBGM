"""ACRCloud BGM 식별. 0차에서는 demucs 분리 생략, 원본 오디오 그대로 지문 시도 (설계 80행).
키 없으면 스킵 + 플레이스홀더. 키가 있으면 식별 시도."""
import json
import os

import config as C


def identify(audio_path: str) -> dict | None:
    """ACRCloud에 오디오 지문 식별 요청. 결과 dict or None."""
    import requests
    import base64
    import hmac
    import hashlib
    import time as _time

    if not (C.ACR_ACCESS_KEY and C.ACR_ACCESS_SECRET):
        return None

    with open(audio_path, "rb") as f:
        sample = f.read()
    # ACRCloud 권장: 앞 10초 분량만 전송. 16kHz mono 16bit → 10초 = 320,000 bytes
    sample = sample[:320000]

    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(_time.time()))

    string_to_sign = "\n".join([
        http_method, http_uri, C.ACR_ACCESS_KEY,
        data_type, signature_version, timestamp,
    ])
    sign = base64.b64encode(hmac.new(
        C.ACR_ACCESS_SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()).decode("utf-8")

    files = {"sample": sample}
    data = {
        "access_key": C.ACR_ACCESS_KEY,
        "sample_bytes": str(len(sample)),
        "timestamp": timestamp,
        "signature": sign,
        "data_type": data_type,
        "signature_version": signature_version,
    }
    resp = requests.post(f"https://{C.ACR_HOST}{http_uri}", files=files, data=data, timeout=30)
    return resp.json()


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(C.OUTPUT_DIR, "bgm.json")

    # 키 없으면 스킵
    if not (C.ACR_ACCESS_KEY and C.ACR_ACCESS_SECRET):
        print("ACRCloud 키 미제공 → BGM 식별 스킵 (플레이스홀더)")
        result = {
            "status": "skipped_no_key",
            "reason": "ACR_ACCESS_KEY/ACR_ACCESS_SECRET 환경변수 미설정",
            "results": {},
        }
        with open(out_path, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"저장: {out_path}")
        return

    # 키 있음 → 실제 식별
    transcripts_path = os.path.join(C.OUTPUT_DIR, "transcripts.json")
    with open(transcripts_path) as f:
        transcripts = json.load(f)

    results = {}
    identified, unidentified = 0, 0
    for vid, t in transcripts.items():
        if t.get("error"):
            continue
        wav_path = os.path.join(C.AUDIO_DIR, f"{vid}.wav")
        if not os.path.exists(wav_path):
            results[vid] = {"status": "no_audio"}
            continue
        try:
            res = identify(wav_path)
            status = res.get("status", {})
            if status.get("code") == 0:
                music = res.get("metadata", {}).get("music", [])
                if music:
                    m = music[0]
                    artists = ", ".join(a.get("name", "") for a in m.get("artists", []))
                    results[vid] = {
                        "status": "identified",
                        "bgm": m.get("title", ""),
                        "artist": artists,
                    }
                    identified += 1
                else:
                    results[vid] = {"status": "no_match"}
                    unidentified += 1
            else:
                results[vid] = {"status": "no_match", "msg": status.get("msg", "")}
                unidentified += 1
        except Exception as e:
            results[vid] = {"status": "error", "msg": str(e)}
            unidentified += 1

    result = {
        "status": "done",
        "demucs_separated": False,  # 0차는 분리 생략
        "identified": identified,
        "unidentified": unidentified,
        "results": results,
    }
    with open(out_path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"BGM 식별 완료: 성공 {identified}, 미식별 {unidentified}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
