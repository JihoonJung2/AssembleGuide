"""실험 2 예비: 고정 백본(ResNet18 vs DINOv2) + 프로토타입, 5-way K-shot 정확도.

헤드 없이 백본만 비교한다. 데이터는 Kaggle "Images of LEGO Bricks"(16종).
종류 단위로 head_train 10종 / test 6종을 나누고, 이 스크립트는 test 6종만 평가한다.

    python experiments/exp2_recog/backbone_fewshot.py --data-root <클래스 폴더들이 있는 경로>
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from assembleguide.recog.backbone import BACKBONES, build_transform, embed, load_backbone
from assembleguide.recog.fewshot import classify, prototypes

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
DATASET_NAME = "kaggle_lego16"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument(
        "--data-root", type=Path, default=None, help="없으면 /kaggle/input 에서 자동 탐색"
    )
    p.add_argument("--backbones", nargs="+", default=list(BACKBONES), choices=BACKBONES)
    p.add_argument("--shots", nargs="+", type=int, default=[1, 3, 5])
    p.add_argument("--n-way", type=int, default=5)
    p.add_argument("--n-query", type=int, default=15)
    p.add_argument("--episodes", type=int, default=600)
    p.add_argument("--n-test-classes", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--splits-dir", type=Path, default=Path("splits"))
    p.add_argument("--out-dir", type=Path, default=Path("results"))
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--img-size", type=int, default=224)
    return p.parse_args()


def class_dirs(root: Path) -> list[Path]:
    """root 바로 아래에서 이미지가 들어 있는 폴더 목록 (이름순)."""
    return sorted(
        d
        for d in root.iterdir()
        if d.is_dir() and any(f.suffix.lower() in IMG_EXTS for f in d.iterdir())
    )


def find_data_root(base: Path = Path("/kaggle/input"), max_depth: int = 5) -> Path:
    """클래스 폴더가 가장 많이 모인 디렉터리를 데이터 루트로 고른다.

    Kaggle 입력은 심볼릭 링크로 붙는 경우가 있어 링크도 따라간다.
    """
    best, best_n = None, 0
    for cur, subdirs, _ in os.walk(base, followlinks=True):
        if len(Path(cur).relative_to(base).parts) >= max_depth:
            subdirs.clear()
            continue
        n = len(class_dirs(Path(cur)))
        if n:
            print(f"  [후보] {cur}  ({n}개 클래스 폴더)")
        if n > best_n:
            best, best_n = Path(cur), n
    if best is None or best_n < 6:
        listing = "\n".join(f"    {p}" for p in sorted(base.glob("*/*"))[:30]) or "    (비어 있음)"
        raise FileNotFoundError(
            f"{base} 아래에서 클래스 폴더를 못 찾음. --data-root 로 지정\n"
            f"  {base} 내용:\n{listing}"
        )
    return best


def load_or_make_class_split(root: Path, splits_dir: Path, n_test: int, seed: int) -> dict:
    """splits/kaggle_classes.yaml 이 있으면 읽고, 없으면 종류 단위로 나눠 저장."""
    path = splits_dir / "kaggle_classes.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    names = [d.name for d in class_dirs(root)]
    rng = random.Random(seed)
    shuffled = names[:]
    rng.shuffle(shuffled)
    split = {
        "seed": seed,
        "head_train": sorted(shuffled[n_test:]),
        "test": sorted(shuffled[:n_test]),
    }
    splits_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(split, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[split] 새로 만듦 → {path}")
    return split


def list_images(root: Path, classes: list[str]) -> dict[str, list[Path]]:
    return {
        c: sorted(f for f in (root / c).iterdir() if f.suffix.lower() in IMG_EXTS) for c in classes
    }


def load_or_make_episodes(
    files: dict[str, list[Path]], args: argparse.Namespace
) -> dict[str, list[dict]]:
    """고정 에피소드. 모든 백본이 같은 에피소드로 평가된다. 이미지는 클래스 내 인덱스로 저장."""
    path = args.splits_dir / f"fewshot_episodes_seed{args.seed}.json"
    meta = {"n_way": args.n_way, "n_query": args.n_query, "episodes": args.episodes}
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["meta"] == meta and all(str(k) in saved["shots"] for k in args.shots):
            return saved["shots"]
        print(f"[episodes] {path} 설정이 달라 새로 만듦")
    rng = random.Random(args.seed)
    classes = sorted(files)
    shots = {}
    for k in args.shots:
        eps = []
        for _ in range(args.episodes):
            way = rng.sample(classes, args.n_way)
            eps.append({c: rng.sample(range(len(files[c])), k + args.n_query) for c in way})
        shots[str(k)] = eps
    args.splits_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "shots": shots}), encoding="utf-8")
    print(f"[episodes] 새로 만듦 → {path}")
    return shots


class ImageList(Dataset):
    def __init__(self, paths: list[Path], transform):
        self.paths, self.transform = paths, transform

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, i: int) -> torch.Tensor:
        return self.transform(Image.open(self.paths[i]).convert("RGB"))


def embed_all(model, paths: list[Path], args, device) -> tuple[torch.Tensor, float]:
    """전체 이미지 임베딩 (N,D) + 배치 처리 기준 장당 ms."""
    loader = DataLoader(
        ImageList(paths, build_transform(args.img_size)),
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )
    out = []
    t0 = time.perf_counter()
    for x in loader:
        out.append(embed(model, x.to(device)).cpu())
    if device.type == "cuda":
        torch.cuda.synchronize()
    return torch.cat(out), (time.perf_counter() - t0) / len(paths) * 1000


def latency_bs1(model, paths: list[Path], args, device, n: int = 50) -> float:
    """배치 1 (실제 사용과 같은 조건) 장당 ms. 전처리 포함, 워밍업 5장 제외."""
    tf = build_transform(args.img_size)
    times = []
    for i, p in enumerate(paths[: n + 5]):
        t0 = time.perf_counter()
        embed(model, tf(Image.open(p).convert("RGB")).unsqueeze(0).to(device))
        if device.type == "cuda":
            torch.cuda.synchronize()
        if i >= 5:
            times.append((time.perf_counter() - t0) * 1000)
    return float(np.median(times))


def evaluate(emb: dict[str, torch.Tensor], episodes: list[dict], k: int) -> np.ndarray:
    """에피소드별 정확도 배열."""
    accs = []
    for ep in episodes:
        sup, sup_y, qry, qry_y = [], [], [], []
        for label, (c, idx) in enumerate(ep.items()):
            e = emb[c][idx]
            sup.append(e[:k])
            qry.append(e[k:])
            sup_y += [label] * k
            qry_y += [label] * (len(idx) - k)
        protos = prototypes(torch.cat(sup), torch.tensor(sup_y), len(ep))
        pred, _ = classify(torch.cat(qry), protos)
        accs.append((pred == torch.tensor(qry_y)).float().mean().item())
    return np.array(accs)


def plot(df: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 3.5))
    for bb, g in df.groupby("backbone"):
        ax.errorbar(
            g["shots"], g["accuracy_mean"], yerr=g["accuracy_ci95"], marker="o", capsize=3, label=bb
        )
    ax.set_xlabel("shots (images per class)")  # 기본 폰트에 한글이 없어 영어로
    ax.set_ylabel("accuracy")
    ax.set_xticks(sorted(df["shots"].unique()))
    ax.set_title(f"{DATASET_NAME} test classes, {df['n_way'].iloc[0]}-way")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    root = args.data_root or find_data_root()
    print(f"[data] {root}  device={device}")
    split = load_or_make_class_split(root, args.splits_dir, args.n_test_classes, args.seed)
    files = list_images(root, split["test"])
    for c, fs in files.items():
        print(f"  test  {c}: {len(fs)}장")
    episodes = load_or_make_episodes(files, args)

    all_paths = [p for c in sorted(files) for p in files[c]]
    rows, timing = [], {}
    for bb in args.backbones:
        model, dim = load_backbone(bb, device)
        flat, ms_batch = embed_all(model, all_paths, args, device)
        ms_bs1 = latency_bs1(model, all_paths, args, device)
        timing[bb] = {
            "dim": dim,
            "ms_per_img_batch": round(ms_batch, 2),
            "ms_per_img_bs1": round(ms_bs1, 2),
        }
        print(f"[{bb}] dim={dim}  batch {ms_batch:.1f} ms/img  bs1 {ms_bs1:.1f} ms/img")

        emb, i = {}, 0
        for c in sorted(files):
            emb[c] = flat[i : i + len(files[c])]
            i += len(files[c])

        for k in args.shots:
            accs = evaluate(emb, episodes[str(k)], k)
            ci = 1.96 * accs.std() / np.sqrt(len(accs))
            rows.append(
                {
                    "dataset": DATASET_NAME,
                    "method": f"{bb}_proto",
                    "backbone": bb,
                    "shots": k,
                    "n_way": args.n_way,
                    "episodes": len(accs),
                    "accuracy_mean": round(float(accs.mean()), 4),
                    "accuracy_std": round(float(accs.std()), 4),
                    "train_images_per_class": 0,
                    # 등록 = k장 임베딩 + 평균. 이 장비 기준 추정치 (노트북 CPU는 따로 측정)
                    "add_block_sec": round(k * ms_bs1 / 1000, 3),
                    "accuracy_ci95": round(float(ci), 4),
                }
            )
            print(f"  {k}-shot  acc {accs.mean():.4f} ± {ci:.4f}")
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"exp2_backbone_{datetime.now():%y%m%d}"
    df = pd.DataFrame(rows)
    df.drop(columns="accuracy_ci95").to_csv(args.out_dir / f"{stem}.csv", index=False)
    cfg = {
        **{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "data_root": str(root),
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "torch": str(torch.__version__),
        "class_split": split,
        "timing": timing,
        "accuracy_ci95": {f"{r['backbone']}_{r['shots']}shot": r["accuracy_ci95"] for r in rows},
    }
    (args.out_dir / f"{stem}.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    plot(df, args.out_dir / f"{stem}.png")
    print(df.drop(columns=["dataset", "train_images_per_class"]).to_string(index=False))
    print(f"[saved] {args.out_dir / stem}.csv / .yaml / .png")


if __name__ == "__main__":
    main()
