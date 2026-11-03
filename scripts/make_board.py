"""작업 판 인쇄본(A4 PDF + 미리보기 PNG) 생성. 규격은 configs/board.yaml.

    python scripts/make_board.py   → docs/board/board_a4.pdf, board_a4.png

인쇄할 때 반드시 "실제 크기(100%)". 인쇄 후 아래 100 mm 눈금자를 자로 재서 확인한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

MM_PER_INCH = 25.4


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("configs/board.yaml"))
    ap.add_argument("--out-dir", type=Path, default=Path("docs/board"))
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    sw, sh = cfg["sheet_mm"]
    fig = plt.figure(figsize=(sw / MM_PER_INCH, sh / MM_PER_INCH))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, sw)
    ax.set_ylim(sh, 0)  # y 아래 방향
    ax.set_aspect("equal")
    ax.axis("off")

    # ArUco 마커
    aru = cfg["aruco"]
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, aru["dict"]))
    m = aru["marker_mm"]
    for mid, (x, y) in aru["markers"].items():
        img = cv2.aruco.generateImageMarker(dictionary, int(mid), 600)
        ax.imshow(
            img, cmap="gray", extent=(x, x + m, y + m, y), interpolation="nearest", vmin=0, vmax=255
        )
        ax.text(x + m / 2, y + m + 4, f"ID {mid}", ha="center", va="top", fontsize=7, color="0.4")

    # 레고판 자리
    pl = cfg["plate"]
    px, py = pl["origin_on_sheet_mm"]
    pw, ph = pl["studs"][0] * pl["stud_mm"], pl["studs"][1] * pl["stud_mm"]
    ax.add_patch(Rectangle((px, py), pw, ph, fill=False, lw=1.2, ec="black"))
    for i in range(pl["studs"][0]):
        for j in range(pl["studs"][1]):
            cx, cy = px + (i + 0.5) * pl["stud_mm"], py + (j + 0.5) * pl["stud_mm"]
            r = 0.3 * pl["stud_mm"]  # 스터드 지름 ≈ 간격의 60%
            ax.add_patch(plt.Circle((cx, cy), r, fill=False, lw=0.3, ec="0.75"))
    label = (
        f"place {pl['studs'][0]}x{pl['studs'][1]} plate here ({pw:.0f} x {ph:.0f} mm, "
        f"stud {pl['stud_mm']:g} mm)"
    )
    ax.text(px + pw / 2, py - 4, label, ha="center", va="bottom", fontsize=8)
    ax.annotate("", xy=(px + 14, py), xytext=(px, py), arrowprops={"arrowstyle": "->", "lw": 0.8})
    ax.annotate("", xy=(px, py + 14), xytext=(px, py), arrowprops={"arrowstyle": "->", "lw": 0.8})
    ax.text(px - 2, py - 2, "origin (0,0)", ha="right", va="bottom", fontsize=6)
    ax.text(px + 15, py + 1, "x", fontsize=6, va="top")
    ax.text(px + 1, py + 15, "y", fontsize=6, ha="left")

    # 100 mm 눈금자 (인쇄 배율 확인)
    rx, ry = sw / 2 - 50, 178
    ax.plot([rx, rx + 100], [ry, ry], color="black", lw=0.8)
    for k in range(11):
        tick = 3 if k % 5 == 0 else 1.5
        ax.plot([rx + 10 * k, rx + 10 * k], [ry, ry - tick], color="black", lw=0.6)
    ax.text(
        sw / 2,
        ry + 3,
        "100 mm  -  print at 100% (actual size) and check with a ruler",
        ha="center",
        va="top",
        fontsize=7,
    )
    ax.text(
        sw / 2,
        sh - 6,
        f"AssembleGuide board v2 (DUPLO)  |  {aru['dict']}  IDs 0-3  |  marker {m} mm",
        ha="center",
        va="bottom",
        fontsize=6,
        color="0.5",
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out_dir / "board_a4.pdf")
    fig.savefig(args.out_dir / "board_a4.png", dpi=100)
    print(f"[saved] {args.out_dir / 'board_a4.pdf'} / .png")


if __name__ == "__main__":
    main()
