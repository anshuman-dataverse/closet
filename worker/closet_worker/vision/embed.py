"""Fashion CLIP embedders (SPEC 5.1 step 3). Vectors are L2-normalized.

- patrickjohncyh/fashion-clip  → transformers CLIPModel, 512-d
- Marqo/marqo-fashionSigLIP    → open_clip via hf-hub, 768-d
Models download from public Hugging Face repos on first use and stay in memory.
"""

from __future__ import annotations

from functools import cache
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from PIL import Image

FASHION_CLIP = "patrickjohncyh/fashion-clip"
MARQO_SIGLIP = "Marqo/marqo-fashionSigLIP"
MODELS = (FASHION_CLIP, MARQO_SIGLIP)


class Embedder(Protocol):
    model_id: str
    dim: int
    logit_scale: float  # multiplies cosine similarity before softmax in zero-shot

    def image(self, imgs: list[Image.Image]) -> NDArray[np.float32]: ...
    def text(self, prompts: list[str]) -> NDArray[np.float32]: ...


def l2(x: NDArray[Any]) -> NDArray[np.float32]:
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return np.asarray(x / np.maximum(n, 1e-12), dtype=np.float32)


def pick_device(pref: str = "auto") -> str:
    import torch

    if pref in ("cpu", "mps", "cuda"):
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _features(out: Any) -> Any:
    """transformers ≥5 returns an output object with the projected features in pooler_output."""
    return out if hasattr(out, "detach") else out.pooler_output


class HfClipEmbedder:
    def __init__(self, model_id: str = FASHION_CLIP, device: str = "auto") -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.model_id = model_id
        self.device = pick_device(device)
        model: Any = CLIPModel.from_pretrained(model_id)
        self.model = model.to(self.device).eval()
        self.proc = CLIPProcessor.from_pretrained(model_id)
        self.dim = int(self.model.config.projection_dim)
        self.logit_scale = float(self.model.logit_scale.exp().item())
        self._torch = torch

    def image(self, imgs: list[Image.Image]) -> NDArray[np.float32]:
        with self._torch.no_grad():
            x = self.proc(images=[i.convert("RGB") for i in imgs], return_tensors="pt").to(
                self.device
            )
            f = _features(self.model.get_image_features(**x))
        return l2(f.detach().float().cpu().numpy())

    def text(self, prompts: list[str]) -> NDArray[np.float32]:
        with self._torch.no_grad():
            x = self.proc(text=prompts, return_tensors="pt", padding=True, truncation=True).to(
                self.device
            )
            f = _features(self.model.get_text_features(**x))
        return l2(f.detach().float().cpu().numpy())


class OpenClipEmbedder:
    def __init__(self, model_id: str = MARQO_SIGLIP, device: str = "auto") -> None:
        import open_clip
        import torch

        self.model_id = model_id
        self.device = pick_device(device)
        model, _, preprocess = open_clip.create_model_and_transforms(
            f"hf-hub:{model_id}", device=self.device
        )
        self.model = model.eval()
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(f"hf-hub:{model_id}")
        self._torch = torch
        with torch.no_grad():
            probe = self.model.encode_text(self.tokenizer(["a shirt"]).to(self.device))
        self.dim = int(probe.shape[-1])
        self.logit_scale = 100.0  # as in Marqo's zero-shot examples

    def image(self, imgs: list[Image.Image]) -> NDArray[np.float32]:
        with self._torch.no_grad():
            x = self._torch.stack([self.preprocess(i.convert("RGB")) for i in imgs]).to(self.device)
            f = self.model.encode_image(x)
        return l2(f.detach().float().cpu().numpy())

    def text(self, prompts: list[str]) -> NDArray[np.float32]:
        with self._torch.no_grad():
            f = self.model.encode_text(self.tokenizer(prompts).to(self.device))
        return l2(f.detach().float().cpu().numpy())


@cache
def load_embedder(model_id: str, device: str = "auto") -> Embedder:
    if model_id == MARQO_SIGLIP or "siglip" in model_id.lower():
        return OpenClipEmbedder(model_id, device)
    return HfClipEmbedder(model_id, device)
