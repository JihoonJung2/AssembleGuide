# AssembleGuide

**손 가림과 새 부품에 강건한 AI 기반 AR 조립 작업 보조 시스템**
가천대 AI P-실무프로젝트 (2026-2)

웹캠 2대(상단+측면)와 A4 ArUco 마커 판으로 **다음에 놓을 블록과 위치를 화면에 안내**하고, 작업자가 놓은 결과를 **자동으로 판정**한다.
실험 대상은 레고 호환 블록(실제 산업 부품의 대체물)이며, 제조 키팅·신입 작업자 교육을 주 활용처로 본다.

## 핵심 기여

1. **손 가림 강건 판정** — MediaPipe 손 인식 → 상태 머신(손이 판에서 빠진 뒤 안정 대기) → K개 프레임 다수결.
   손이 화면을 가리는 동안 생기는 오경보를 줄인다.
2. **few-shot 블록 인식** — 고정 백본(DINOv2 ViT-S/14 또는 ResNet18) + 메트릭 러닝으로 학습한 작은 인식 헤드 + HSV 색 + 실측 면적.
   헤드는 기존 블록으로 한 번만 학습하고, **새 블록은 재학습 없이 사진 3~5장 등록만** 한다.

모든 기능은 설정(`configs/default.yaml`)으로 끄고 켤 수 있어, 실험에서 baseline과 같은 데이터로 비교한다.

## 동작 흐름

```txt
상단 카메라 ─► 판 자세 추정(ArUco) ─► 손 감지 ─► 상태 머신
                                                  │ judge 상태일 때만
                                                  ▼
                              위에서 본 영상 ─► 변화 검출 ─► 블록 인식 ─┐
측면 카메라 ─────────────────────────────────► 층 판정 ───────────────┤
                                                                     ▼
                                     K프레임 다수결 판정 ─► 2D AR 오버레이 + 로그
```

## 하드웨어

| 항목 | 내용 |
| --- | --- |
| 카메라 | Innomaker U20CAM-1080P × 2 (상단: 판·손·블록 인식, 측면: 층 확인) |
| 거치대 | 2020 알루미늄 프로파일, 상단 카메라 높이 30~35 cm |
| 판 | A4 ArUco 마커 판 (모서리 마커 4개, 16×16 스터드 격자) |
| 촬영 | 1280×720, 30fps, 자동 노출·화이트밸런스 끔 |
| 추론 | 노트북 CPU (학습은 Kaggle 무료 GPU) |

## 블록 세트

| 구분 | 블록 | 비고 |
| --- | --- | --- |
| 기본 6종 | `R2x2` `R1x4` `R2x4` `B2x2` `B1x4` `B2x4` | 빨강·파랑 × 3모양 |
| 새 블록 2종 | `R2x3` `B1x2` | 헤드 학습·설정 조정에 쓰지 않음 (등록만) |

새 블록 시나리오: *제품 사양 변경으로 같은 색 계열의 신규 규격 부품이 투입된 키팅 상황.*

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Python 3.11 기준. Kaggle 노트북에서는 `requirements-kaggle.txt`를 쓴다.

## 실행

```bash
# 메인 앱 (카메라 번호 또는 영상 파일)
python -m assembleguide.app --top 0 --side 1 --design designs/D01.json
python -m assembleguide.app --top data/d2/D02_P1_01_TOP.mp4 --side data/d2/D02_P1_01_SIDE.mp4 --design designs/D02.json

# 모듈별 단독 데모
python -m assembleguide.hand.demo --video x.mp4
```

> 코드 작성 중. 명령 인자는 구현에 맞춰 갱신한다.

## 레포 구조

```txt
configs/        판정·인식 설정, 블록 세트, 실험 설정
designs/        조립 설계 JSON (D01~D05)
docs/           데이터 형식, 시나리오, 관련 연구 baseline 표
src/assembleguide/
  common/       공용 타입, 칸→mm 변환, 입출력
  board/        ArUco 자세 추정, rectify
  hand/         MediaPipe 손 인식, 상태 머신
  change/       변화 검출
  recog/        백본·헤드·등록·색·면적 결합
  layer/        측면 카메라 층 판정
  verify/       위치 검증, 다중 프레임 판정
  ar/           2D 오버레이
  baselines/    HSV 규칙, YOLO11n-cls
  app.py        실시간 메인 루프
server/         FastAPI (세션·판정 기록, SQLite)
dashboard/      Streamlit 대시보드
experiments/    실험 1~3 평가 스크립트
kaggle/         Kaggle 학습 노트북
scripts/        녹화·라벨링·설계 검증 도구
splits/         학습/조정/시험 분할 목록
results/        실험 결과 CSV·YAML·그림
tests/
```

데이터(`data/`), 영상, 가중치는 git에 올리지 않는다.

## 데이터 형식

좌표는 **판 기준 mm**(원점 격자 왼쪽 위, x 오른쪽, y 아래), 층은 1/2, 회전은 0/90.
설계 JSON·라벨·판정 로그·결과 CSV의 상세 형식은 [docs/data_format.md](docs/data_format.md) 참고.

## 실험

| 실험 | 내용 | 비교 방법 | 주요 지표 |
| --- | --- | --- | --- |
| 1 (메인) | 손 가림 판정 | 단일 프레임 / 손 마스크 / 고정 대기 / 안정 대기 / +다중 프레임 | 판정 정확도, 오경보율, 놓친 오류율, 판정 지연, FPS |
| 2 | 블록 인식 | HSV 규칙 / YOLO11n-cls(블록당 5·20·50·150장) / ResNet18 / DINOv2 / +헤드 / +색·면적 | 정확도, 필요한 사진 수, 새 블록 추가 시간 |
| 3 | 층 판정 | 2층 조립 단계 | 층 판정 정확도 |
| 4 (도전) | 사용자 실험 | 종이 설명서 vs AR | 완료 시간, 오류 수, NASA-TLX, SUS 등 |

시험 데이터는 `splits/`에 고정하고, 시험 데이터를 보고 설정을 고치지 않는다.

## 팀

| 이름 | 담당 |
| --- | --- |
| 정지훈 | 판 인식, 변화 검출, 층 판정, AR, 설계 |
| 이세윤 | 손 인식·상태 머신, 판정, 실험 1 |
| 양수겸 | few-shot 인식, 실험 2 |
| 김두은 | baseline, 통합, 서버·대시보드 |

## 기여 규칙

- 브랜치: `main`(제출용) ← `dev`(통합) ← `feat/파트-기능`, `exp/실험명`, `fix/내용`
- 커밋: `타입: 내용` (feat / fix / exp / data / refactor / docs / chore)
- PR은 `dev`로, 팀원 1명 이상 확인 후 merge
- `black` 포맷, `ruff` 린트
