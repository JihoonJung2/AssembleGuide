"""조립 설계 JSON: 관계형 단계 → 판 칸 좌표. 칸↔mm 변환은 이 파일에서만 한다.

설계 단계는 "기준 블록(ref)의 어느 쪽(side)에, 어떻게 맞춰(align)" 놓는지로 적는다.
1단계(기준 없음)는 판 위 아무 데나 놓고, 그 실제 위치가 이후 단계의 기준이 된다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

SIDES = ("right", "left", "down", "up", "on")
ALIGNS = ("start", "center", "end")
STUD_MM = 16.0  # 듀플로. configs/board.yaml 의 plate.stud_mm 과 맞춘다


@dataclass(frozen=True)
class Placement:
    """판 위에 놓인 블록 하나. x, y는 왼쪽 위 칸, sx, sy는 회전 반영한 칸 수."""

    step: int
    block: str
    x: int
    y: int
    sx: int
    sy: int
    rot: int
    layer: int

    def cells(self) -> set[tuple[int, int]]:
        """차지하는 칸 목록."""
        return {(self.x + i, self.y + j) for i in range(self.sx) for j in range(self.sy)}

    def center_mm(self, stud_mm: float = STUD_MM) -> tuple[float, float]:
        """블록 중심의 판 좌표(mm)."""
        return ((self.x + self.sx / 2) * stud_mm, (self.y + self.sy / 2) * stud_mm)


def load_blocks(path: str | Path = "configs/blocks.yaml") -> dict[str, dict]:
    """블록 ID → 블록 정보."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {b["id"]: b for b in data["blocks"]}


def load_design(path: str | Path) -> dict:
    """설계 JSON 읽기."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def footprint(block: dict, rot: int) -> tuple[int, int]:
    """(x 방향 칸 수, y 방향 칸 수). rot 0 = 긴 변이 x 방향."""
    long_, short = max(block["w"], block["h"]), min(block["w"], block["h"])
    return (long_, short) if rot % 180 == 0 else (short, long_)


def _aligned(ref_start: int, ref_len: int, new_len: int, align: str) -> int:
    if align == "start":
        return ref_start
    if align == "end":
        return ref_start + ref_len - new_len
    diff = ref_len - new_len
    if diff % 2:
        raise ValueError(f"center 정렬 불가: 기준 {ref_len}칸, 새 블록 {new_len}칸 (홀짝 다름)")
    return ref_start + diff // 2


def place_step(step: dict, blocks: dict[str, dict], ref: Placement | None) -> Placement:
    """설계 단계 하나 + 기준 블록의 실제 위치 → 놓아야 할 위치.

    1단계(ref 없음)는 step 의 x, y(없으면 0, 0)를 쓴다. 실시간에서는 감지한 실제 위치로 대체한다.
    """
    rot = step.get("rot", 0)
    sx, sy = footprint(blocks[step["block"]], rot)
    layer = step.get("layer", 1)
    if ref is None:
        x, y = step.get("x", 0), step.get("y", 0)
    elif "offset" in step:
        dx, dy = step["offset"]
        x, y = ref.x + dx, ref.y + dy
    else:
        side, align = step["side"], step.get("align", "start")
        if side not in SIDES or align not in ALIGNS:
            raise ValueError(f"step {step['step']}: side {side} / align {align} 확인")
        if side == "right":
            x, y = ref.x + ref.sx, _aligned(ref.y, ref.sy, sy, align)
        elif side == "left":
            x, y = ref.x - sx, _aligned(ref.y, ref.sy, sy, align)
        elif side == "down":
            x, y = _aligned(ref.x, ref.sx, sx, align), ref.y + ref.sy
        elif side == "up":
            x, y = _aligned(ref.x, ref.sx, sx, align), ref.y - sy
        else:  # on
            x, y = _aligned(ref.x, ref.sx, sx, align), _aligned(ref.y, ref.sy, sy, align)
    return Placement(step["step"], step["block"], x, y, sx, sy, rot, layer)


def resolve(
    design: dict, blocks: dict[str, dict], start: tuple[int, int] | None = None
) -> list[Placement]:
    """설계 전체를 칸 좌표로 펼친다. start 는 1단계 왼쪽 위 칸 (없으면 설계의 start 권장값)."""
    start = start or tuple(design.get("start", (0, 0)))
    placed: dict[int, Placement] = {}
    for step in design["steps"]:
        if "ref" in step:
            ref = placed[step["ref"]]
            placed[step["step"]] = place_step(step, blocks, ref)
        else:
            placed[step["step"]] = place_step({**step, "x": start[0], "y": start[1]}, blocks, None)
    return list(placed.values())


def check_design(design: dict, blocks: dict[str, dict], plate_studs: tuple[int, int]) -> list[str]:
    """설계 오류 목록 (비어 있으면 통과). 판 밖, 겹침, 받침 없는 2층, 기준 단계 순서 등."""
    errors = []
    steps = design["steps"]
    if [s["step"] for s in steps] != list(range(1, len(steps) + 1)):
        errors.append("step 은 1부터 연속이어야 함")
    for s in steps:
        if s["block"] not in blocks:
            errors.append(f"step {s['step']}: 블록 {s['block']} 이 blocks.yaml 에 없음")
        if s.get("layer", 1) > design.get("max_layer", 1):
            errors.append(f"step {s['step']}: layer {s['layer']} > max_layer")
        if "ref" in s and not 1 <= s["ref"] < s["step"]:
            errors.append(f"step {s['step']}: ref 는 앞선 단계여야 함")
        if s["step"] > 1 and "ref" not in s:
            errors.append(f"step {s['step']}: 1단계 외에는 ref 필요")
    if errors:
        return errors
    try:
        placements = resolve(design, blocks)
    except ValueError as e:
        return [str(e)]

    w, h = plate_studs
    by_step = {p.step: p for p in placements}
    occupied: dict[tuple[int, int, int], int] = {}
    for s, p in zip(steps, placements, strict=True):
        if p.x < 0 or p.y < 0 or p.x + p.sx > w or p.y + p.sy > h:
            errors.append(f"step {p.step}: 판 밖 (x={p.x}, y={p.y}, {p.sx}x{p.sy}칸, 판 {w}x{h})")
        if s.get("side") == "on" and p.layer != by_step[s["ref"]].layer + 1:
            errors.append(f"step {p.step}: side=on 이면 layer = 기준 layer + 1")
        for c in p.cells():
            key = (*c, p.layer)
            if key in occupied:
                errors.append(
                    f"step {p.step}: step {occupied[key]} 와 겹침 (칸 {c}, layer {p.layer})"
                )
                break
            occupied[key] = p.step
        if p.layer > 1 and not any((*c, p.layer - 1) in occupied for c in p.cells()):
            errors.append(f"step {p.step}: 아래층 받침 없음")
    return errors


def cell_to_mm(x: float, y: float, stud_mm: float = STUD_MM) -> tuple[float, float]:
    """칸 좌표 → 판 좌표(mm)."""
    return x * stud_mm, y * stud_mm


def mm_to_cell(x_mm: float, y_mm: float, stud_mm: float = STUD_MM) -> tuple[float, float]:
    """판 좌표(mm) → 칸 좌표 (실수, 반올림은 호출하는 쪽에서)."""
    return x_mm / stud_mm, y_mm / stud_mm
