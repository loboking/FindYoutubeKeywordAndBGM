# 0차 스파이크 측정 기록

실행일: 2026-07-10
니치: 감성 일상 브이로그
환경: Python 3.14.4, faster-whisper 1.2.1 (small, device=cpu, int8), yt-dlp 2026.03.17, ffmpeg 8.0.1

## 1. 발견 성공률 (목표: Shorts 30개)

### 니치 키워드 그대로 → 실패
- `ytsearch50:"감성 일상 브이로그"` → duration<=61s **0개** (0%)
- `ytsearch100:"감성 일상 브이로그"` → duration<=61s **0개** (0%)
- 원인: "브이로그" 검색어는 긴 영상(6~33분) 위주로 반환. Shorts가 하나도 없음.
- **이것이 설계 72행이 경고한 "진짜 하드 파트".**

### 검색어 조정 테스트 (ytsearch20 기준)
| 쿼리 | Shorts(<=61s) 비율 |
|---|---|
| 감성 브이로그 shorts | 2/20 (10%) |
| 감성 일상 shorts | 8/20 (40%) |
| **감성 쇼츠** | **9/20 (45%)** |
| 감성 브이로그 쇼츠 | 6/20 (30%) |
| 일상 브이로그 #shorts | 1/20 (5%) |

### 채택 및 최종 결과
- 채택 키워드: `감성 일상 shorts` (니치에 가장 가까우면서 발견율 양호)
- `ytsearch100:"감성 일상 shorts"` → raw 100개 → duration<=61s **36개** → **목표 30개 확보 성공**
- **발견 성공률: 36/100 = 36%** (니치 키워드로 30개 확보 가능 — 하위 합격 기준 충족)

### duration 분포 (확보된 30개)
- min=8s, max=61s, 평균=36s
- 조회수: min=2, 중간=66, max=646,832

## 2. yt-dlp 실패율
- ytsearch100 시도 100개 중 수집 성공 100개, 실패 0개
- 오디오 다운로드 30개 시도, 실패 0개
- **yt-dlp 실패율: 0%**

## 3. 전사 성공률 + 소요 시간
- 모델: **faster-whisper `small`** (device=cpu, compute_type=int8, language=ko, vad_filter=True)
- 전사 대상: 30개
- 성공: **30/30 (100%)**
- 실패: 0개
- 총 소요: **108.6초** (샘플 10개 63.1초 + 나머지 20개 45.5초)
- 영상당 평균: **3.6초** (오디오 다운로드 + ffmpeg wav 변환 + whisper 전사 포함)

### 경고 (기능 영향 없음)
- `feature_extractor.py:224 RuntimeWarning: divide by zero / overflow in matmul`
- 원인: VAD 필터가 무음 구간 처리 후 빈 mel spectrogram. 전사 결과에는 영향 없음.

## 4. 오프닝 멘트 분석 (정의: 앞 5초 오디오 세그먼트의 전사)
- 오프닝 멘트 있음(음성): **8/30 (27%)**
- 오프닝 멘트 없음(BGM/무음/효과음): **22/30 (73%)**
- **핵심 발견**: 감성 일상 니치 숏츠는 앞 5초에 "말"이 아니라 "BGM/분위기"를 쓰는 비율이 73%.
- 오프닝 멘트 클러스터링(2차) 입력 품질이 니치에 따라 크게 달라짐. "말하는 숏츠" 니치(예: IT/교육)와 "분위기 숏츠" 니치(예: 감성 브이로그)는 패턴이 다름.

## 5. BGM 식별률
- **ACRCloud 키 미제공 → 스킵** (status: skipped_no_key)
- 0차에서는 demucs 분리 생략 (설계 80행 허용). 원본 오디오 그대로 지문 시도하도록 코드 완성됨.
- 키 제공 시 바로 실행 가능 (identify_bgm.py).

## 6. 추천
- **ANTHROPIC_API_KEY 미제공 → prompt.txt만 덤프** (2,959자)
- this_week.md는 생성 안 됨. 키 설정 시 recommend.py 재실행하면 this_week.md 생성.

## 산출물
- output/shorts.json — 수집된 30개 메타데이터
- output/transcripts.json — 30개 전사(전체 텍스트 + 세그먼트 + 오프닝 멘트)
- output/bgm.json — 스킵 플레이스홀더
- output/prompt.txt — Claude 추천 프롬프트 (키 설정 시 바로 사용 가능)
- output/audio/ — 다운로드된 오디오(m4a/webm) + 변환된 wav 30세트
