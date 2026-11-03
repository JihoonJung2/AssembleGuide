"""프로토타입(등록 사진 임베딩 평균) 기반 few-shot 분류."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def prototypes(support: torch.Tensor, labels: torch.Tensor, n_way: int) -> torch.Tensor:
    """support (N,D) + 라벨 (N,) → 클래스별 평균 임베딩 (n_way,D), L2 정규화."""
    protos = torch.stack([support[labels == c].mean(0) for c in range(n_way)])
    return F.normalize(protos, dim=-1)


def classify(query: torch.Tensor, protos: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """query (M,D) → (예측 클래스 (M,), 코사인 유사도 (M,n_way))."""
    scores = query @ protos.T
    return scores.argmax(dim=1), scores
