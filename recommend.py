"""Claude API 추천. ANTHROPIC_API_KEY 없으면 조립된 프롬프트를 output/prompt.txt로 덤프."""
import json
import os

import config as C

INSIGHTS_PATH = os.path.join(C.OUTPUT_DIR, "insights.json")

# 키 없을 때 / Claude 응답 파싱 전 초안. index.html이 이걸 렌더한다.
# (Claude 응답을 JSON으로 파싱하는 건 이번 범위 밖 — 초안이 우선 렌더됨)
INSIGHTS_FALLBACK = {
    "generated_by": "manual_fallback",
    "niche": C.NICHE,
    "formula": "감성 풍경/다꾸 영상 + 잔잔한 lofi·연주곡 BGM + 위로 자막(또는 내레이션) 한 문장",
    "top_videos_summary": [
        {"views": 646832, "title": "딱 1분만 집중해서 들어봐…", "key": "시간/위로 내레이션"},
        {"views": 14790, "title": "수채화 1분 다꾸", "key": "aesthetic"},
        {"views": 5220, "title": "힐링 감성 색감 인트로", "key": "색감"},
        {"views": 4972, "title": "감성 연주곡 앨범 트레일러", "key": "음악"},
        {"views": 1155, "title": "빈티지 감성 룩북", "key": "aesthetic"},
    ],
    "bgm_trends": ["lofi", "잔잔한 피아노/연주곡", "슬픈/시린 발라드"],
    "voice_pattern": {
        "speech_in_first_5s_percent": 27,
        "summary": "앞 5초에 말이 나오는 영상 27%, 73%는 무음·BGM·자막",
        "patterns": [
            "위로 한 문장 (예: '넌 이미 잘하고 있어')",
            "친근한 일상 멘트 (예: '덕담 한 마디씩 하자')",
        ],
    },
    "trend_keywords": [
        "위로·힐링", "다꾸", "수채화", "1분다꾸", "빈티지룩북", "무드등",
        "한강", "노을", "비", "꽃", "도시의밤", "전시회", "보라빛", "새벽",
    ],
    "plans": [
        {
            "title": "새벽 1분, 위로의 한 문장",
            "based_on": "1위 64만 회 패턴 변주",
            "video_title": "바빠서 놓친 하루, 1분만",
            "bgm": "잔잔한 피아노 연주곡 / 새벽 lofi",
            "first_3s": '(무음 시작 → 부드러운 내레이션) "잠깐만… 숨 좀 돌려도 돼."',
            "hook": '새벽 도시·비 오는 창밖·귀갓길 풍경이 느리게 흐르고, 위로 문장 자막이 하나씩 뜸. 마지막 자막 "오늘도 무사히 버텨냈어."',
            "keywords": ["#감성브이로그", "#힐링", "#위로", "#새벽", "#1분명상"],
        },
        {
            "title": "오늘의 색, 1분 다꾸",
            "based_on": "1.4만 회 수채화 다꾸 패턴",
            "video_title": "오늘의 색, 1분 다꾸",
            "bgm": "빈티지 몽환 연주곡",
            "first_3s": '(무음 + 자막) "오늘의 무드 🌙 보라빛 저녁"',
            "hook": "수채화/다꾸 과정을 빠른 컷으로, 색이 채워지는 시각적 만족감 + 펜·종이 ASMR",
            "keywords": ["#다꾸", "#수채화", "#감성", "#빈티지", "#1분다꾸"],
        },
        {
            "title": "퇴근길 노을, 혼자만의 시간",
            "based_on": "노을·한강 + 위로 패턴",
            "video_title": "퇴근길 노을이 이렇게 예뻤다고",
            "bgm": "감성 발라드 / 노을 연주곡",
            "first_3s": '(무음 + 노을 화면 + 자막) "오늘 하루, 잘 버텨냈어."',
            "hook": '노을 지는 하늘 타임랩스 + 발소리·바람소리 ASMR, 끝 자막 "내일도 잘 부탁해."',
            "keywords": ["#노을", "#퇴근길", "#감성", "#혼자놀기", "#힐링"],
        },
    ],
}

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

    # 키 없으면 여기서 종료 (insights.json 초안은 아래 공통 분기에서 항상 씀)
    if not C.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 미제공 → prompt.txt만 덤프 (this_week.md 생성 안 함)")
        insights = dict(INSIGHTS_FALLBACK)  # generated_by == "manual_fallback" 그대로
        _dump_insights(insights)
        return

    # 키 있음 → Claude 호출
    print("Claude API 호출 중...")
    claude_ok = False
    try:
        md = call_claude(prompt)
        out_path = os.path.join(C.OUTPUT_DIR, "this_week.md")
        with open(out_path, "w") as f:
            f.write(md or "(빈 응답)")
        print(f"this_week.md 저장: {out_path}")
        claude_ok = True
    except Exception as e:
        print(f"Claude 호출 실패: {e}")
        print("prompt.txt는 저장됨 — 수동으로 Claude에 넣어보세요.")

    # insights.json: Claude 응답 파싱은 이번 범위 밖.
    # 응답 마크다운은 this_week.md에 있으니, 초안의 generated_by만 마킹.
    insights = dict(INSIGHTS_FALLBACK)
    insights["generated_by"] = "claude_pending" if claude_ok else "manual_fallback"
    _dump_insights(insights)


def _dump_insights(insights: dict) -> None:
    """insights.json을 항상 쓴다. index.html 렌더 소스."""
    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    print(f"insights.json 저장: {INSIGHTS_PATH} (generated_by={insights.get('generated_by')})")


if __name__ == "__main__":
    main()
