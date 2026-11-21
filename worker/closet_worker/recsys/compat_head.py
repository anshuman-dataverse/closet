"""The outfit model's scoring head, self-contained (only torch) so Colab runs this same file.

A re-implementation of OutfitTransformer's compatibility path (owj0421/outfit-transformer
@ eef4be55, `predict_score` with precomputed embeddings), using the repo's parameter names so its
checkpoint loads with `strict=True` once the item encoder's keys are dropped.

Input per item: FashionCLIP image embedding (512) ⊕ FashionCLIP text embedding (512).
"""

from __future__ import annotations

from typing import Any

HALF = 512
KEYS_PREFIXES = ("style_enc.", "predict_ffn.")
KEYS_EXACT = ("task_emb", "predict_emb", "pad_emb")


def build(n_head: int = 16, d_ffn: int = 2024, n_layers: int = 6, dropout: float = 0.3) -> Any:
    import torch
    import torch.nn.functional as F
    from torch import nn

    d = 2 * HALF

    class CompatHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layer = nn.TransformerEncoderLayer(
                d_model=d,
                nhead=n_head,
                dim_feedforward=d_ffn,
                dropout=dropout,
                batch_first=True,
                norm_first=True,
                activation=F.mish,
            )
            self.style_enc = nn.TransformerEncoder(
                layer, num_layers=n_layers, enable_nested_tensor=False
            )
            self.predict_ffn = nn.Sequential(nn.Dropout(dropout), nn.Linear(d, 1), nn.Sigmoid())
            self.task_emb = nn.Parameter(torch.zeros(d // 2))
            self.predict_emb = nn.Parameter(torch.zeros(d // 2))
            self.pad_emb = nn.Parameter(torch.zeros(d))

        def forward(self, embs: Any, lengths: Any) -> Any:
            """embs [B, L, 1024] (rows past each length are ignored), lengths [B] → p [B]."""
            b, n, _ = embs.shape
            pos = torch.arange(n, device=embs.device).unsqueeze(0)
            pad = pos >= lengths.to(embs.device).unsqueeze(1)  # True where padded
            x = torch.where(pad.unsqueeze(-1), self.pad_emb.expand(b, n, -1), embs)
            task = torch.cat([self.task_emb, self.predict_emb]).view(1, 1, -1).expand(b, -1, -1)
            x = torch.cat([task, x], dim=1)
            mask = torch.cat([torch.zeros(b, 1, dtype=torch.bool, device=embs.device), pad], dim=1)
            x = torch.cat(
                [F.normalize(x[..., :HALF], p=2, dim=-1), F.normalize(x[..., HALF:], p=2, dim=-1)],
                dim=-1,
            )
            h = self.style_enc(x, src_key_padding_mask=mask)
            return self.predict_ffn(h[:, 0, :]).squeeze(-1)

    return CompatHead()


def head_state(repo_state: dict[str, Any]) -> dict[str, Any]:
    """The head's tensors from a repo checkpoint's `model` dict (drops DDP's `module.` prefix)."""
    out = {}
    for k, v in repo_state.items():
        k = k.removeprefix("module.")
        if k.startswith(KEYS_PREFIXES) or k in KEYS_EXACT:
            out[k] = v
    return out
