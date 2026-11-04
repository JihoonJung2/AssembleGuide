"""판정 1번에 드는 인식 시간: 크롭 K장(3/5) × 한 장씩/묶어서 × 백본.

판정은 손이 빠진 뒤 K프레임을 모아서 한다. 블록 종류 인식을 몇 장에 할지(recog_frames),
묶어서 한 번에 넣을지(recog_batch)에 따라 인식 시간이 얼마나 줄어드는지 잰다.
정확도는 재지 않는다 (영상 프레임 다수결 정확도는 실험 1의 D2 영상으로 잰다).

    python experiments/exp2_recog/latency_bench.py              # 가능한 장비 전부 (cpu, cuda)
    python experiments/exp2_recog/latency_bench.py --devices cpu
"""

from __future__ import annotations

import argparse
import platform
import statistics
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from PIL import Image

from assembleguide.recog.backbone import BACKBONES, build_transform, embed, load_backbone

# 듀플로 2x4 크롭 크기 추정: 카메라 30 cm, 1280 px 가로 ≈ 46 cm → 약 2.8 px/mm, 64×32 mm
CROP_PX = (180, 90)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--backbones", nargs="+", default=list(BACKBONES), choices=BACKBONES)
    p.add_argument(
        "--frames", nargs="+", type=int, default=[3, 5], help="판정 1번에 인식할 크롭 수"
    )
    p.add_argument("--img-size", type=int, default=224)
    p.add_argument("--devices", nargs="+", default=None, help="기본: cpu (+ cuda 있으면)")
    p.add_argument("--reps", type=int, default=30, help="반복 측정 횟수")
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--threads", type=int, default=None, help="CPU 스레드 수 (기본: torch 기본값)")
    p.add_argument("--out-dir", type=Path, default=Path("results"))
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def make_crops(n: int, rng: np.random.Generator) -> list[Image.Image]:
    """측정용 크롭. 시간은 이미지 내용과 무관하므로 무작위 픽셀로 만든다."""
    w, h = CROP_PX
    return [Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8)) for _ in range(n)]


def judge_once(model, crops, tf, device, batch: bool) -> None:
    """판정 1번 분량의 인식: 전처리 + 임베딩. batch=True 면 한 번에, 아니면 한 장씩."""
    if batch:
        embed(model, torch.stack([tf(c) for c in crops]).to(device))
    else:
        for c in crops:
            embed(model, tf(c).unsqueeze(0).to(device))
    if device.type == "cuda":
        torch.cuda.synchronize()


def bench(model, crops, tf, device, batch: bool, reps: int, warmup: int) -> list[float]:
    """판정 1번 인식 시간(ms) 목록."""
    for _ in range(warmup):
        judge_once(model, crops, tf, device, batch)
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        judge_once(model, crops, tf, device, batch)
        times.append((time.perf_counter() - t0) * 1000)
    return times


def main() -> None:
    args = parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    devices = args.devices or (["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"])
    rng = np.random.default_rng(args.seed)
    tf = build_transform(args.img_size)
    max_k = max(args.frames)
    crops_all = make_crops(max_k, rng)

    rows = []
    for dev_name in devices:
        device = torch.device(dev_name)
        for bb in args.backbones:
            model, _ = load_backbone(bb, device)
            for k in args.frames:
                for batch in (False, True):
                    t = bench(model, crops_all[:k], tf, device, batch, args.reps, args.warmup)
                    med = statistics.median(t)
                    rows.append(
                        {
                            "backbone": bb,
                            "device": dev_name,
                            "img_size": args.img_size,
                            "frames": k,
                            "mode": "batch" if batch else "sequential",
                            "ms_median": round(med, 1),
                            "ms_p90": round(float(np.percentile(t, 90)), 1),
                            "ms_per_crop": round(med / k, 1),
                        }
                    )
                    mode = "batch" if batch else "seq"
                    print(f"[{dev_name}] {bb:14s} K={k} {mode:5s} {med:7.1f} ms")
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()

    df = pd.DataFrame(rows)
    # 기준(5장 한 장씩) 대비 비율
    base = df[(df["frames"] == 5) & (df["mode"] == "sequential")].set_index(["backbone", "device"])
    df["vs_5seq"] = [
        (
            round(r.ms_median / base.loc[(r.backbone, r.device), "ms_median"], 2)
            if (r.backbone, r.device) in base.index
            else None
        )
        for r in df.itertuples()
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"exp2_latency_{datetime.now():%y%m%d}"
    df.to_csv(args.out_dir / f"{stem}.csv", index=False)
    cfg = {
        **{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "devices": devices,
        "crop_px": list(CROP_PX),
        "cpu": platform.processor() or platform.machine(),
        "torch_threads": torch.get_num_threads(),
        "torch": str(torch.__version__),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    (args.out_dir / f"{stem}.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(df.to_string(index=False))
    print(f"[saved] {args.out_dir / stem}.csv / .yaml")


if __name__ == "__main__":
    main()
