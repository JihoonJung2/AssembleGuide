"""고정 백본 임베딩 추출 (ResNet18 / DINOv2 ViT-S/14)."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms

BACKBONES = ("resnet18", "dinov2_vits14")
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def load_backbone(name: str, device: str | torch.device = "cpu") -> tuple[nn.Module, int]:
    """백본 이름 → (평가 모드 모델, 임베딩 차원)."""
    if name == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        model.fc = nn.Identity()
        dim = 512
    elif name == "dinov2_vits14":
        model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")
        dim = 384
    else:
        raise ValueError(f"알 수 없는 백본: {name} (가능: {BACKBONES})")
    model.eval().to(device)
    for p in model.parameters():
        p.requires_grad_(False)
    return model, dim


def build_transform(img_size: int = 224) -> transforms.Compose:
    """PIL 이미지 → 정규화된 텐서. 224는 ViT-S/14 패치(14) 배수."""
    return transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )


@torch.no_grad()
def embed(model: nn.Module, images: torch.Tensor) -> torch.Tensor:
    """(B,3,H,W) → L2 정규화된 (B,D) 임베딩. DINOv2는 CLS 토큰."""
    return F.normalize(model(images), dim=-1)
