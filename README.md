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
| 판 | A4 가로 종이 + 모서리 ArUco 마커 4개 + 가운데 12×6 초록 듀플로 판(192×96 mm). 인쇄본 [docs/board/board_a4.pdf](docs/board/board_a4.pdf) (100% 크기로 인쇄) |
| 촬영 | 1280×720, 30fps, 자동 노출·화이트밸런스 끔 |
| 추론 | 노트북 CPU (학습은 Kaggle 무료 GPU) |

## 블록 세트

| 구분 | 블록 | 비고 |
| --- | --- | --- |
| 기본 6종 | `R2x2` `R2x4` `B2x2` `B2x4` `Y2x2` `Y2x8` | 빨강·파랑·노랑 일반 블록. 색 + 크기로 구분됨 |
| 새 블록 2종 | `R2x2S` `B2x2S` (경사 2x2) | 기존 2x2와 **색·면적이 같고 모양만 다름**. 헤드 학습·설정 조정에 쓰지 않음 (등록만) |

새 블록 시나리오: *제품 사양 변경으로 색·크기가 같은 신규 부품이 투입된 키팅 상황.* 색 규칙(HSV)과 면적으로는 구분할 수 없고, YOLO는 재학습이 필요하다.

블록 ID는 `{색}{짧은변}x{긴변}{형태}` (형태: 일반은 생략, `S` 경사). 판별은 상단 카메라만 쓰므로 위에서 봐서 구분 안 되는 블록은 넣지 않는다.

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Python 3.11 기준. Kaggle 노트북에서는 `requirements-kaggle.txt`를 쓴다.

- 레포가 OneDrive 같은 동기화 폴더 안에 있으면 가상환경은 밖에 만든다 (예: `C:\Users\<me>\venvs\assembleguide`). 수만 개 파일이 동기화되며 느려진다.
- ultralytics가 `opencv-python`을 같이 깔아 `opencv-contrib-python`(ArUco 포함)과 충돌하면 contrib만 남긴다:
  `pip uninstall -y opencv-python opencv-contrib-python && pip install opencv-contrib-python`

## Kaggle 실험 (실험 2 예비: ResNet18 vs DINOv2)

1. Kaggle에서 New Notebook → File → Import Notebook → `kaggle/exp2_backbone/exp2_backbone.ipynb`
2. Add Input → `joosthazelzet/lego-brick-images`, Settings → GPU T4 · Internet On
3. 첫 코드 셀의 `BRANCH`를 확인하고 Run All
4. Output의 `results/`, `splits/`를 받아 레포에 커밋

CLI로 돌리려면 `kaggle/exp2_backbone/kernel-metadata.json`의 `id`에 Kaggle 사용자 이름을 넣고 `kaggle kernels push -p kaggle/exp2_backbone`.

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
designs/        조립 설계 JSON (D01~D05, 관계형)
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

좌표는 **판 기준 mm**(원점 = 레고판 왼쪽 위, x 오른쪽, y 아래), 블록 위치는 칸(듀플로 스터드 16 mm) 단위, 층은 1/2, 회전은 0/90.
설계는 **관계형**이다. "1번 블록 바로 오른쪽, 윗변 맞춰"처럼 기준 블록과의 관계로 적고, 판정도 기준 블록의 실제 위치 기준으로 한다.

```bash
python scripts/check_design.py designs/D01.json   # 설계 검사 + 칸 배치 그림
python scripts/make_board.py                      # 판 인쇄본 다시 만들기 (configs/board.yaml 수정 시)
```
설계 JSON·라벨·판정 로그·결과 CSV의 상세 형식은 [docs/data_format.md](docs/data_format.md) 참고.

## 실험

| 실험 | 내용 | 비교 방법 | 주요 지표 |
| --- | --- | --- | --- |
| 1 (메인) | 손 가림 판정 | 단일 프레임 / 손 마스크 / 고정 대기 / 안정 대기 / +다중 프레임 | 판정 정확도, 오경보율, 놓친 오류율, 판정 지연, FPS |
| 2 | 블록 인식 | HSV 규칙 / YOLO11n-cls(블록당 5·20·50·150장) / ResNet18 / DINOv2 / +헤드 / +색·면적 | 정확도, 필요한 사진 수, 새 블록 추가 시간 |
| 3 | 층 판정 | 2층 조립 단계 | 층 판정 정확도 |
| 4 (도전) | 사용자 실험 | 종이 설명서 vs AR | 완료 시간, 오류 수, NASA-TLX, SUS 등 |

시험 데이터는 `splits/`에 고정하고, 시험 데이터를 보고 설정을 고치지 않는다.
실험별 절차와 결과: [실험 2](experiments/exp2_recog/README.md)

## 팀

| 이름 | 담당 |
| --- | --- |
|  |  |
|  |  |
|  |  |
|  |  |

## 개발 컨벤션

### 브랜치

| 브랜치 | 용도 | 예 |
| --- | --- | --- |
| `main` | 발표·제출용 안정 버전 | `dev`에서 PR로만 merge |
| `dev` | 통합 개발 (**기본 브랜치**) | 기능 브랜치를 PR로 merge |
| `feat/파트-기능` | 기능 개발 | `feat/hand-state-machine`, `feat/recog-fewshot` |
| `exp/실험명` | 실험·분석 | `exp/multiframe-ablation` |
| `fix/내용` | 버그 수정 | `fix/aruco-occlusion` |
| `chore/내용` | 설정·문서·환경 | `chore/init-setup` |

`main`·`dev`는 보호 브랜치라 직접 push가 안 된다. 작업은 항상 `dev`에서 브랜치를 따서 시작한다.

```bash
git fetch origin
git checkout -b feat/hand-state-machine origin/dev
# ... 작업, 커밋 ...
git push -u origin feat/hand-state-machine   # → GitHub에서 dev로 PR
```

### 커밋 메시지

형식 `타입: 내용` (한글 OK)

| 타입 | 사용 | 예 |
| --- | --- | --- |
| `feat` | 새 기능 | `feat: 손 인식 상태 머신 추가` |
| `fix` | 버그 수정 | `fix: 마커 가려질 때 자세 유지` |
| `exp` | 실험 코드·결과 | `exp: 5-way 3-shot 캐글 평가` |
| `data` | 데이터 스크립트·라벨 | `data: 녹화 라벨링 스크립트` |
| `refactor` | 동작 변화 없는 정리 | `refactor: 인식 모듈 함수 분리` |
| `docs` | README·문서·주석 | `docs: 설치 방법 추가` |
| `chore` | 설정·패키지 | `chore: requirements 업데이트` |

### PR

- `dev`로 보내고, 팀원 1명 이상 확인 후 merge
- 설명에 **무엇을 바꿨는지, 어떻게 확인했는지** 적기 (스크린샷·GIF 환영)
- 제출 시점에 `dev` → `main` PR

### 코드 스타일

- Python 3.11, 가상환경 필수. 패키지 추가 시 `requirements.txt` 갱신
- `black` 포맷, `ruff` 린트 (커밋 전 실행)
- 이름: 함수·변수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_CASE`
- 공개 함수는 타입 힌트 + 한 줄 docstring (한글 OK)
- 숫자 설정값(대기 프레임 수, 임계값 등)은 코드에 박지 말고 `configs/*.yaml`에
- 기능은 설정으로 끄고 켤 수 있게 만든다 (실험에서 baseline과 비교하기 위해)
- 좌표는 모듈 사이에서 **판 기준 mm**로 통일, 픽셀은 모듈 내부에서만
- 각 모듈은 영상 파일 하나로 단독 실행되는 데모를 둔다 (`python -m assembleguide.<모듈>.demo --video x.mp4`)
- 영상·가중치·데이터·`.env`·API 키는 커밋 금지

### 실험 기록

- 랜덤 시드 고정, 결과는 `results/{실험}_{YYMMDD}.csv` + 사용한 설정 `.yaml`
- 학습·조정에 쓴 블록·영상은 최종 시험에서 제외, 분할 목록은 `splits/`에 기록
- 시험 데이터를 보고 설정을 고치지 않는다
