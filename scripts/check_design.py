"""설계 JSON 검사 + 판 위 배치 그림(글자) 출력.

python scripts/check_design.py designs/D01.json [designs/D02.json ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from assembleguide.common.design import check_design, load_blocks, load_design, resolve


def draw(placements, plate: tuple[int, int], layer: int) -> str:
    """layer 한 층을 칸마다 단계 번호로 그린다 (빈칸은 .)."""
    w, h = plate
    grid = [["." for _ in range(w)] for _ in range(h)]
    for p in placements:
        if p.layer != layer:
            continue
        for x, y in p.cells():
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = str(p.step % 10)
    return "\n".join("    " + " ".join(row) for row in grid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("designs", nargs="+", type=Path)
    ap.add_argument("--blocks", type=Path, default=Path("configs/blocks.yaml"))
    ap.add_argument("--board", type=Path, default=Path("configs/board.yaml"))
    args = ap.parse_args()

    blocks = load_blocks(args.blocks)
    board = yaml.safe_load(args.board.read_text(encoding="utf-8"))
    ok = True
    for path in args.designs:
        design = load_design(path)
        plate = tuple(design.get("plate", board["plate"]["studs"]))
        errors = check_design(design, blocks, plate)
        n_steps = len(design["steps"])
        print(f"[{design['id']}] {design['name']}  ({n_steps}단계, 판 {plate[0]}x{plate[1]})")
        if errors:
            ok = False
            for e in errors:
                print(f"  ✗ {e}")
            continue
        placements = resolve(design, blocks)
        for p in placements:
            print(f"  step {p.step}: {p.block:6s} 칸 ({p.x},{p.y}) {p.sx}x{p.sy} layer {p.layer}")
        for layer in range(1, design.get("max_layer", 1) + 1):
            print(f"  layer {layer}:\n{draw(placements, plate, layer)}")
        print("  ✓ 통과")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
