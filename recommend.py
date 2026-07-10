"""Claude API 추천. ANTHROPIC_API_KEY 없으면 조립된 프롬프트를 output/prompt.txt로 덤프."""
import json
import os

import config as C

PROMPT_TEMPLATE = """당신은 유튜브 숏츠 콘텐츠 기획 전문가입니다.

아래 데이터를 바탕으로, 내 채널 니치에 딱 맞는 구체적인 숏츠 기획안 3개를 만들어주세요.

## 내 채널 니치
{niche}

## 내 채널 3문장 설명
{channel_desc}

## 이번 주 수집된 니치 숏츠 전사 (오프닝 멘트 포함)
{transcripts}

## 이번 주 감지된 BGM 리스트
{bgm_list}

## 요구사항
각 기획안마다 아래 5가지를 구체적으로 적어주세요:
1. **제목** (클릭을 끄는, 15자 이내)
2. **BGM 픽** (위 리스트에서 골라도 되고 새로 추천해도 됨)
3. **첫 3초 오프닝 멘트** (시청자를 멈추게 하는 한 문장)
4. **훅** (무엇이 이 영상을 끝까지 보게 만드는가)
5. **타겟 키워드** (3~5개, 검색/해시태그용)

기획안은 "당장 만들어보고 싶다"는 느낌이 들어야 합니다.
내 채널 톤(잔잔, 감성, 위로)에서 벗어나지 않되, 트렌드를 써야 합니다.
"""


def build_prompt(transcripts: dict, bgm: dict) -> str:
    # 전사 요약 (오프닝 멘트 중심)
    t_lines = []
    for vid, t in transcripts.items():
        if t.get("error"):
            continue
        opening = t.get("opening_mention", "") or "(오프닝 음성 없음)"
        title = t.get("title", "")
        views = t.get("view_count")
        view_str = f" 조회수 {views:,}" if views else ""
        t_lines.append(f'- [{title}]{view_str} 오프닝: "{opening}"')

    # BGM 리스트
    if bgm.get("status") == "skipped_no_key":
        bgm_text = "(BGM 식별 스킵 — ACRCloud 키 미제공. 트렌드 BGM을 임의로 추천해 주세요.)"
    else:
        items = []
        for vid, r in bgm.get("results", {}).items():
            if r.get("status") == "identified":
                items.append(f'- {r.get("bgm","?")} - {r.get("artist","?")}')
        bgm_text = "\n".join(items) if items else "(식별된 BGM 없음)"

    return PROMPT_TEMPLATE.format(
        niche=C.NICHE,
        channel_desc=C.CHANNEL_DESC,
        transcripts="\n".join(t_lines),
        bgm_list=bgm_text,
    )


def call_claude(prompt: str) -> str | None:
    """Claude API 호출. 응답 텍스트 or None."""
    import requests
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": C.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    parts = data.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    transcripts_path = os.path.join(C.OUTPUT_DIR, "transcripts.json")
    bgm_path = os.path.join(C.OUTPUT_DIR, "bgm.json")

    with open(transcripts_path) as f:
        transcripts = json.load(f)
    with open(bgm_path) as f:
        bgm = json.load(f)

    prompt = build_prompt(transcripts, bgm)

    # 항상 프롬프트 덤프
    prompt_path = os.path.join(C.OUTPUT_DIR, "prompt.txt")
    with open(prompt_path, "w") as f:
        f.write(prompt)
    print(f"프롬프트 저장: {prompt_path} ({len(prompt)}자)")

    # 키 없으면 여기서 종료
    if not C.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 미제공 → prompt.txt만 덤프 (this_week.md 생성 안 함)")
        return

    # 키 있음 → Claude 호출
    print("Claude API 호출 중...")
    try:
        md = call_claude(prompt)
        out_path = os.path.join(C.OUTPUT_DIR, "this_week.md")
        with open(out_path, "w") as f:
            f.write(md or "(빈 응답)")
        print(f"this_week.md 저장: {out_path}")
    except Exception as e:
        print(f"Claude 호출 실패: {e}")
        print("prompt.txt는 저장됨 — 수동으로 Claude에 넣어보세요.")


if __name__ == "__main__":
    main()
