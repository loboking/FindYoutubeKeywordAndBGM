"""Claude API 추천. ANTHROPIC_API_KEY 없으면 조립된 프롬프트를 output/prompt.txt로 덤프."""
import json
import os
import re
from collections import Counter

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


def _extract_keywords(videos: list[dict]) -> list[str]:
    """제목에서 해시태그 + 의미 토큰 빈도 추출. 추정이 아니라 실제 등장 단어.
    (한글 형태소 분석은 안 함 — 빈도 기반 rough 추출, 데이터 근거.)"""
    stop = {
        "오늘", "하루", "나", "내", "우리", "때", "것", "이", "그", "저", "더",
        "정말", "진짜", "일상", "브이로그", "vlog", "shorts", "쇼츠", "영상",
        "편집", "촬영", "그냥", "조금",
    }
    tokens = []
    for v in videos:
        t = v.get("title", "") or ""
        for tag in re.findall(r"#([0-9A-Za-z가-힣_]+)", t):
            tokens.append("#" + tag)
        for w in re.split(r"[\s\U0001f000-\U000effff\-_/,.!?~()|:+\']+", t):
            w = w.strip()
            if not w or w.startswith("#"):
                continue
            if w.lower() in stop:
                continue
            if not re.search(r"[0-9A-Za-z가-힣]", w):  # 기호만(이모지 잔류 등) 제외
                continue
            if re.fullmatch(r"[A-Za-z]+", w) and len(w) < 4:  # 짧은 영어 토큰(My 등) 제외
                continue
            if len(w) >= 2:
                tokens.append(w)
    return [k for k, _ in Counter(tokens).most_common(20) if k]


def build_insights(transcripts: dict, shorts: dict, bgm: dict) -> dict:
    """실제 데이터에서 정직한 insights 계산.
    노이즈를 신호로 포장하지 않는다:
    - 전사 결측(full_text 빈)은 분모에서 제외하고 그 사실을 명시.
    - 1위 영상이 조회수 독점이면 아웃라이어로 분리 (formula/평균 왜곡 경고).
    - BGM 식별 안 됐으면 bgm_trends=[] (추정으로 채우지 않음).
    - formula는 자동 분석이 아니면 '샘플 기반 초안'으로 솔직하게.
    """
    videos = shorts.get("videos", [])

    # --- 전사 분류 ---
    # 전사 확보 = full_text 비어있지 않고 error 없음
    transcribed = []  # 전사 확보된 항목들 (transcripts dict의 values)
    empty_count = 0
    for vid, t in transcripts.items():
        if t.get("error"):
            continue
        if t.get("full_text"):
            transcribed.append(t)
        elif t.get("full_text") == "":
            empty_count += 1
    # transcripts에 error 있는 것도 결측
    error_count = sum(1 for t in transcripts.values() if t.get("error"))

    # --- voice_pattern ---
    denom = len(transcribed)
    opening_present = sum(1 for t in transcribed if t.get("opening_mention"))
    if denom > 0:
        speech_pct = round(opening_present / denom * 100)
        voice_summary = (
            f"전사 확보 {denom}개 중 앞 5초에 말이 나오는 영상 {opening_present}개 "
            f"({speech_pct}%). 결측 {empty_count}개는 전사 비출력으로 제외"
            + (f", 오류 {error_count}개" if error_count else "") + "."
        )
    else:
        speech_pct = None
        voice_summary = (
            f"전사 확보된 영상 없음 (결측 {empty_count}개 전사 비출력"
            + (f", 오류 {error_count}개" if error_count else "") + "). "
            "음성 패턴 분산을 계산할 수 없음."
        )
    voice_pattern = {
        "speech_in_first_5s_percent": speech_pct,
        "n": denom,
        "summary": voice_summary,
        "patterns": [],  # 자연어 클러스터링은 이번 범위 밖 — 비움
    }

    # --- 아웃라이어 분리 ---
    total_views = sum((v.get("view_count") or 0) for v in videos)
    sorted_vids = sorted(videos, key=lambda x: -(x.get("view_count") or 0))
    top5 = [
        {
            "views": v.get("view_count"),
            "title": v.get("title", ""),
            "key": "",  # 키워드 자동 추출은 범위 밖
            "upload_year": (v.get("upload_date") or "")[:4] or None,
        }
        for v in sorted_vids[:5]
    ]
    has_outlier = False
    top1_views = None
    top1_share = None
    avg_excl_top1 = None
    outlier_note = ""
    if total_views > 0 and sorted_vids:
        top1_views = sorted_vids[0].get("view_count") or 0
        top1_share = round(top1_views / total_views, 2)
        if top1_share >= C.OUTLIER_VIEW_SHARE:
            has_outlier = True
            remaining = [v.get("view_count") or 0 for v in sorted_vids[1:]]
            avg_excl_top1 = round(sum(remaining) / len(remaining)) if remaining else 0
            outlier_note = (
                f"1위 영상이 전체 조회수의 {top1_share*100:.0f}%를 차지해 "
                "평균이 왜곡됨. 평균은 1위 제외 기준으로 볼 것."
            )
    outlier_adjusted = {
        "has_outlier": has_outlier,
        "top1_views": top1_views,
        "top1_share": top1_share,
        "avg_views_excluding_top1": avg_excl_top1,
        "note": outlier_note,
    }

    # --- bgm_trends ---
    if bgm.get("status") == "skipped_no_key":
        bgm_trends = []  # 식별 결과 없음 — 추정으로 채우지 않음
    else:
        identified = [
            r.get("bgm") for r in bgm.get("results", {}).values()
            if r.get("status") == "identified" and r.get("bgm")
        ]
        bgm_trends = identified  # 실제 식별된 것만 (현재 0건)

    # --- formula ---
    sample_n = len(videos)
    if has_outlier:
        formula = (
            f"샘플(n={sample_n}) 기반 임시 공식 — 자동 분석 미사용. "
            f"주의: 1위가 조회수 {top1_share*100:.0f}% 독점, 공식 신뢰도 낮음."
        )
    else:
        formula = f"샘플(n={sample_n}) 기반 임시 공식 — 자동 분석 미사용."

    # --- trend_keywords: 제목에서 실제 빈도 추출 ---
    trend_keywords = _extract_keywords(videos)
    if trend_keywords and not has_outlier:
        formula = (f"최근 니치 채널 shorts(n={sample_n})에서 두드러진 소재: "
                   f"{', '.join(trend_keywords[:6])}. (관찰 기반, AI 자동 분석 아님)")

    # --- plans: INSIGHTS_FALLBACK 초안에서 1위 64만 회 언급 제거/수정 ---
    plans = []
    for plan in INSIGHTS_FALLBACK.get("plans", []):
        plan = dict(plan)
        bo = plan.get("based_on", "")
        if "64만" in bo or "1위" in bo:
            plan["based_on"] = f"니치 적합 상위 영상 + 위로 내레이션 패턴 (샘플 n={sample_n}, 1회 스냅샷)"
        plans.append(plan)

    return {
        "generated_by": "manual_fallback",  # 자동 분석 아님 — 계산된 통계 + 수동 plans 초안
        "niche": C.NICHE,
        "formula": formula,
        "top_videos_summary": top5,
        "outlier_adjusted": outlier_adjusted,
        "bgm_trends": bgm_trends,
        "voice_pattern": voice_pattern,
        "trend_keywords": trend_keywords,
        "plans": plans,
    }


def main():
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    transcripts_path = os.path.join(C.OUTPUT_DIR, "transcripts.json")
    bgm_path = os.path.join(C.OUTPUT_DIR, "bgm.json")
    shorts_path = os.path.join(C.OUTPUT_DIR, "shorts.json")

    # 데이터 파일이 있으면 실제 데이터 기반 insights, 없으면 폴백
    if (os.path.exists(transcripts_path) and os.path.exists(bgm_path)
            and os.path.exists(shorts_path)):
        with open(transcripts_path) as f:
            transcripts = json.load(f)
        with open(bgm_path) as f:
            bgm = json.load(f)
        with open(shorts_path) as f:
            shorts = json.load(f)
        insights = build_insights(transcripts, shorts, bgm)
    else:
        print("데이터 파일(transcripts/bgm/shorts) 누락 → INSIGHTS_FALLBACK 사용")
        transcripts, bgm = {}, {}
        insights = dict(INSIGHTS_FALLBACK)

    prompt = build_prompt(transcripts, bgm)

    # 항상 프롬프트 덤프
    prompt_path = os.path.join(C.OUTPUT_DIR, "prompt.txt")
    with open(prompt_path, "w") as f:
        f.write(prompt)
    print(f"프롬프트 저장: {prompt_path} ({len(prompt)}자)")

    # 키 없으면 여기서 종료 (insights.json은 위에서 계산된 것 사용)
    if not C.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY 미제공 → prompt.txt만 덤프 (this_week.md 생성 안 함)")
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

    # Claude 응답 파싱은 이번 범위 밖 — insights는 계산된 통계 유지,
    # generated_by만 마킹
    insights["generated_by"] = "claude_pending" if claude_ok else "manual_fallback"
    _dump_insights(insights)


def _dump_insights(insights: dict) -> None:
    """insights.json을 항상 쓴다. index.html 렌더 소스."""
    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    print(f"insights.json 저장: {INSIGHTS_PATH} (generated_by={insights.get('generated_by')})")


if __name__ == "__main__":
    main()
