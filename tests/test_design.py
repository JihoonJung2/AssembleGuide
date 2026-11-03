import pytest

from assembleguide.common.design import check_design, load_blocks, load_design, place_step, resolve

BLOCKS = load_blocks("configs/blocks.yaml")
PLATE = (12, 6)


def test_d01_passes():
    design = load_design("designs/D01.json")
    assert check_design(design, BLOCKS, PLATE) == []
    p = {x.step: x for x in resolve(design, BLOCKS)}
    assert (p[2].x, p[2].y) == (5, 1)  # R2x4(1,1) 오른쪽, 윗변 맞춤
    assert (p[5].x, p[5].y) == (9, 3)  # Y2x8 오른쪽, 아랫변 맞춤


def test_relative_to_actual_anchor():
    design = load_design("designs/D01.json")
    p = {x.step: x for x in resolve(design, BLOCKS, start=(2, 0))}
    assert (p[2].x, p[2].y) == (6, 0)  # 1단계가 옮겨지면 나머지도 같이 옮겨짐


def test_layer2_on_and_support():
    design = {
        "id": "T",
        "name": "t",
        "max_layer": 2,
        "steps": [
            {"step": 1, "block": "R2x4", "rot": 0, "layer": 1},
            {"step": 2, "block": "B2x2", "ref": 1, "side": "on", "align": "center", "layer": 2},
            {"step": 3, "block": "Y2x2", "ref": 1, "side": "right", "align": "start", "layer": 2},
        ],
    }
    errors = check_design(design, BLOCKS, PLATE)
    assert len(errors) == 1 and "받침" in errors[0]  # 3단계는 공중에 뜸


def test_center_parity_error():
    blocks = {**BLOCKS, "R2x3S": {"id": "R2x3S", "w": 2, "h": 3}}  # 홀수 칸 블록
    ref = place_step({"step": 1, "block": "R2x4", "rot": 0}, blocks, None)
    with pytest.raises(ValueError):
        place_step(
            {"step": 2, "block": "R2x3S", "ref": 1, "side": "down", "align": "center", "rot": 0},
            blocks,
            ref,
        )


def test_out_of_plate():
    design = {
        "id": "T",
        "name": "t",
        "start": [6, 0],
        "steps": [{"step": 1, "block": "Y2x8", "rot": 0, "layer": 1}],
    }
    assert "판 밖" in check_design(design, BLOCKS, PLATE)[0]
