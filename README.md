# 유튜브 숏츠 트렌드 리서치 + 니치 맞춤 추천 (0차 스파이크)

위자드오브오즈 스파이크: yt-dlp 수집 → faster-whisper 전사 → ACRCloud BGM 식별 → Claude 추천.

## 실행

```bash
# 전체 파이프라인 (순차)
python3 run.py

# 또는 단계별
python3 collect.py          # output/shorts.json
python3 transcribe.py       # output/transcripts.json (오래 걸림)
python3 identify_bgm.py     # output/bgm.json (키 없으면 스킵)
python3 recommend.py        # output/prompt.txt + output/this_week.md
```

전사 샘플링(검증용): `TRANSCRIBE_LIMIT=10 python3 transcribe.py`

## 니치 변경 (한 줄)

`config.py`의 `NICHE`, `SEARCH_KEYWORD`, `CHANNEL_DESC` 세 변수만 바꾸면 전체 파이프라인에 교체됨.

```python
NICHE = "IT 리뷰 숏츠"
SEARCH_KEYWORD = NICHE
CHANNEL_DESC = "..."  # 3문장
```

## API 키 설정 (환경변수)

키가 없어도 키 불필요 단계(수집/전사)는 실행됨. 키가 필요한 단계는 스킵 + 플레이스홀더 산출.

```bash
# Claude 추천 (없으면 output/prompt.txt만 덤프)
export ANTHROPIC_API_KEY=sk-ant-...

# ACRCloud BGM 식별 (없으면 스킵)
export ACR_ACCESS_KEY=...
export ACR_ACCESS_SECRET=...
export ACR_HOST=ap-sea-1.api.acrcloud.com
```

## 측정 기록

`output/measurements.md`에 발견 성공률, yt-dlp 실패율, 전사 성공률/소요시간, BGM 식별률 기록.

## 의존성

```bash
pip install -r requirements.txt
```

외부 바이너리: `yt-dlp`, `ffmpeg` (Homebrew).
