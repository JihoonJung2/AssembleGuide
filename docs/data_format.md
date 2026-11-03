# 공통 데이터 형식 (v3, 2026-11-04)

모든 모듈·스크립트는 이 형식만 주고받는다. 바꾸려면 팀 합의 후 이 문서와 `src/assembleguide/common/types.py`를 같이 고친다.

## 0. 기본 규칙

- **판**: A4 가로 종이 + 모서리 ArUco 마커 4개(`DICT_4X4_50`, ID 0~3, 한 변 35 mm) + 가운데 **12×6 듀플로 판(초록, 192×96 mm)**. 규격 `configs/board.yaml`, 인쇄본 `docs/board/board_a4.pdf` (`scripts/make_board.py`로 생성, 100% 크기로 인쇄).
  - 마커는 카메라가 판 위치·기울기와 **크기(mm)**를 재는 용도. 블록은 레고판에 끼우므로 칸 단위로 딱 맞게 놓인다.
- **좌표**: 판 좌표. 원점 = **레고판 왼쪽 위 모서리**, x 오른쪽(12칸 방향), y 아래쪽(6칸 방향, 위에서 본 영상 기준), 단위 mm. z(높이)는 층(layer)으로 표현.
- **칸**: 듀플로 스터드 간격 16 mm (일반 레고의 2배), 칸 좌표 x 0~11, y 0~5. 블록 위치는 **블록 왼쪽 위 칸**(정수). 모듈 사이에선 mm, 설계·라벨은 칸. 칸↔mm 변환은 `src/assembleguide/common/design.py` 한 곳에서만.
  - 블록 중심 mm = (x + sx/2) × 16, (y + sy/2) × 16. sx, sy는 회전 반영한 칸 수.
- **설계는 관계형**: "(3,1) 칸에 놓아라"가 아니라 "1번 블록 바로 오른쪽, 윗변 맞춰"처럼 **기준 블록과의 관계**로 적는다. 1단계는 판 위 아무 데나 놓고, 그 실제 위치가 이후 단계의 기준이 된다 (2절).
- **층(layer)**: 1 = 판 위 첫 층, 2 = 그 위. 블록 높이 19.2 mm (듀플로).
- **회전(rot)**: 0 또는 90(도). 0 = 긴 변이 x축 방향. 대칭이라 180=0, 270=90으로 취급.
- **블록 ID**: `{색}{짧은변}x{긴변}{형태}` — 색 R 빨강, B 파랑, Y 노랑, G 초록, W 흰색, K 검정. 형태는 일반 블록이면 생략, 경사(slope)면 `S`. 크기는 위에서 본 바닥 칸 수, 짧은 변을 앞에. 예 `R2x4`, `Y2x8`, `B2x2S`, `R3x4S`.
- **시간**: 영상 안 시간은 초(float, 영상 시작=0). 서버 기록은 ISO 8601 KST(+09:00).
- **인코딩**: UTF-8, CSV는 헤더 있음, 쉼표 구분.

## 1. 블록 목록 `configs/blocks.yaml`

```yaml
blocks:
  - {id: R2x2,  color: R, w: 2, h: 2, shape: brick, role: base}
  - {id: R2x4,  color: R, w: 2, h: 4, shape: brick, role: base}
  - {id: B2x2,  color: B, w: 2, h: 2, shape: brick, role: base}
  - {id: B2x4,  color: B, w: 2, h: 4, shape: brick, role: base}
  - {id: Y2x2,  color: Y, w: 2, h: 2, shape: brick, role: base}
  - {id: Y2x8,  color: Y, w: 2, h: 8, shape: brick, role: base}
  - {id: R2x2S, color: R, w: 2, h: 2, shape: slope, role: new}   # 새 블록: 학습·조정에 쓰지 않음
  - {id: B2x2S, color: B, w: 2, h: 2, shape: slope, role: new}
```

- 판별은 상단 카메라만 쓰므로, 위에서 봐서 구분 안 되는 블록(아치 vs 같은 크기 일반 블록 등)은 넣지 않는다.
- 판 색(초록)과 같은 색 블록은 쓰지 않는다.

## 2. 조립 설계 JSON `designs/D01.json`

```json
{
  "id": "D01",
  "name": "1층 5단계 기본",
  "plate": [12, 6],
  "max_layer": 1,
  "start": [1, 1],
  "steps": [
    {"step": 1, "block": "R2x4", "rot": 0, "layer": 1},
    {"step": 2, "block": "B2x2", "ref": 1, "side": "right", "align": "start", "rot": 0, "layer": 1},
    {"step": 3, "block": "Y2x8", "ref": 1, "side": "down",  "align": "start", "rot": 0, "layer": 1}
  ]
}
```

| 필드 | 뜻 |
| --- | --- |
| `start` | 1단계 **권장** 위치(왼쪽 위 칸). AR 안내용이고 판정에는 안 쓴다. 실제 1단계 위치가 기준이 된다 |
| `ref` | 기준이 되는 앞선 단계 번호. 1단계만 없음 |
| `side` | 기준 블록의 `right` / `left` / `down` / `up`(위에서 본 영상 기준, 바로 붙여서) / `on`(위에 쌓기, 2층) |
| `align` | 맞닿는 변을 따라 어디에 맞출지. `start`(위쪽·왼쪽 끝 맞춤) / `center` / `end`(아래쪽·오른쪽 끝 맞춤). `on`이면 두 방향 모두 적용 |
| `offset` | (선택) `[dx, dy]` 칸. 새 블록 왼쪽 위 − 기준 블록 왼쪽 위. 반 칸 어긋나게 겹치기처럼 `side`/`align`으로 안 되는 배치에 쓰고, 있으면 `side`/`align`보다 우선 |
| `rot` | 0 = 긴 변이 x 방향, 90 = 긴 변이 y 방향 (판 기준 절대값) |
| `layer` | 1 = 판 위, 2 = 그 위. `side: on`이면 기준 layer + 1 |

- `step`은 1부터 연속. 검사 `python scripts/check_design.py designs/D01.json`: 판(12×6) 밖, 같은 층 겹침, 받침 없는 2층, `center` 정렬 홀짝 불가 등을 확인하고 칸 배치를 글자 그림으로 보여준다.
- 판정: 새 블록의 위치를 **기준 블록의 확정된 실제 위치**와 비교한다 (`design.place_step`). 기준 블록이 1칸 어긋나 있어도 새 블록과의 관계만 맞으면 정답.
- 설계 5개: D01~D05 (1층 5단계 1개, 1층 8단계 1개, 2층 8~10단계 3개 정도).

## 3. 세션 계획 `splits/d2_sessions.csv`

녹화 전에 미리 정하는 "시험지 대본".

```csv
session_id,design,participant,split,hand_condition,error_plan
D02_P1_01,D02,P1,test,normal,"3:block:B2x4;6:position:dx+1"
D02_P2_01,D02,P2,tune,long_hold,""
```

- `split`: `tune`(조정용, 설정값 결정에만) / `test`(최종 시험, 보고 설정 고치기 금지)
- `hand_condition`: `normal` / `long_hold`(손 오래 머무름) / `two_hands` / `fix_after`(놓고 다시 고침) / `fast`(빠른 연속) / `arm_cover`(팔이 판 대부분 가림)
- `error_plan`: `단계:오류종류:내용`을 `;`로 연결. 비어 있으면 전부 정답 세션.
  - 내용 예: `block:B2x4`(다른 블록), `position:dx+1`(설계보다 x로 1칸 밀기), `position:side=left`(반대쪽에 붙이기), `rotation:90`, `layer:1`(2층 대신 1층), `skip`.

## 4. 영상 파일 이름

`{session_id}_{cam}.mp4` — 예 `D02_P1_01_TOP.mp4`, `D02_P1_01_SIDE.mp4`
- `cam`: `TOP`(상단, 판·손·인식) / `SIDE`(측면, 층 확인)
- 1280×720, 30fps, 자동 노출·화이트밸런스 끔. 두 카메라는 같은 스크립트로 동시에 녹화 → 프레임 시각 `{session_id}_frames.csv`(`frame,t_top,t_side`) 저장.

## 5. 정답 라벨 `data/d2/labels/{session_id}.csv`

```csv
step,t_place,t_hand_out,block_true,x_true,y_true,rot_true,layer_true,correct,error_type
1,4.20,5.10,R2x4,1,1,0,1,1,none
3,15.80,17.30,B2x2,1,3,0,1,0,block
```

- `t_place`: 블록이 판에 닿은 시각, `t_hand_out`: 손이 판 영역에서 완전히 빠진 시각 (라벨링 도구로 찍음)
- `x_true`, `y_true`: 실제로 놓인 블록의 왼쪽 위 칸 (레고판 스터드를 세어 적는다, 정수)
- `correct`: 기준 블록과의 관계·블록·회전·층이 설계와 맞으면 1
- `error_type`: `none` / `block`(다른 블록) / `position`(기준 블록과의 관계가 틀림: 방향·붙음·정렬) / `rotation` / `layer` / `skip`(단계 건너뜀)

## 6. 판정 로그 (실시간·오프라인 공통) `results/logs/{session_id}_{method}.jsonl`

프레임마다가 아니라 **이벤트마다** 한 줄.

```json
{"session_id":"D02_P1_01","method":"final","step":3,"t":17.95,"state":"judge","hand_present":false,
 "pred_block":"B2x2","pred_score":0.91,"pred_x_mm":55.2,"pred_y_mm":24.6,"pred_rot":0,"pred_layer":1,
 "verdict":"error","error_type":"block","latency_s":0.65}
```

- `pred_x_mm`, `pred_y_mm`: 인식한 블록 중심의 판 좌표(mm)
- `method`: `single`(단일 프레임 즉시) / `hand_mask` / `fixed_wait`(고정 N초 대기) / `settle`(안정화 대기) / `final`(+다중 프레임)
- `state`: `idle` / `hand_in` / `settling` / `judge`
- `verdict`: `ok` / `error` / `pending`. `latency_s` = 판정 시각 − `t_hand_out`
- 화면 깜빡임(오경보) 분석을 위해 판정이 바뀔 때마다 기록.

## 7. 인식 데이터

**D1 크롭** `data/d1/{block_id}/{block_id}_{번호:04d}.jpg` + `data/d1/meta.csv`
```csv
path,block_id,area_mm2,rot,layer,light,source
d1/R2x4/R2x4_0001.jpg,R2x4,2048,0,1,L1,TOP
```

**분할** `splits/`
- `kaggle_classes.yaml`: `head_train: [10종]`, `test: [6종]` — 종류 단위 분할
- `d1_split.csv`: `path,split` (`train_yolo` / `support` / `query`)
- `fewshot_episodes_seed0.json`: 5-way K-shot 에피소드 목록 (모든 방법이 같은 에피소드로 평가)

**인식 결과** (함수 반환 `Prediction`)
```json
{"top1": "R2x4", "score": 0.91, "top3": [["R2x4",0.91],["R2x2",0.72],["B2x4",0.40]], "area_mm2": 2010}
```

**블록 등록소** `data/registry/{backbone}/{block_id}.npy` (등록 사진 임베딩 평균) + `registry.yaml`(`block_id, n_images, registered_at, register_sec`)

## 8. 실험 결과 CSV `results/{실험}_{YYMMDD}.csv` + 같은 이름 `.yaml`(사용한 설정)

- 실험 1: `method,n_steps,accuracy,false_alarm_rate,miss_rate,latency_mean_s,latency_p90_s,fps`
- 실험 2: `dataset,method,backbone,shots,n_way,episodes,accuracy_mean,accuracy_std,train_images_per_class,add_block_sec`
  - YOLO는 `shots` 자리에 블록당 학습 장수(5/20/50/150)
- 실험 3: `design,n_layer2_steps,layer_accuracy,...`

### 지표 정의 (단계 단위)
- 판정 정확도 = 맞게 판정한 단계 / 전체 단계
- 오경보율 = 정답인데 오류라고 한 단계 / 정답 단계
- 놓친 오류율 = 오류인데 정답이라고 한 단계 / 오류 단계
- 판정 지연 = 최종 판정 시각 − `t_hand_out`

## 9. 서버 기록 (FastAPI, SQLite)

- `POST /sessions` `{design_id, participant, mode: "ar"|"paper"}` → `{session_id}`
- `POST /sessions/{id}/steps` 판정 로그 6번 한 줄과 같은 필드
- 에러 `{"error": "코드", "message": "설명"}`
