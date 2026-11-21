"""Outfit model (recsys/compat.py): loading, parity with the repo's math, the gate, and scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import torch
import torch.nn.functional as F
from safetensors.torch import save_file

from closet_worker.recsys import compat
from closet_worker.recsys.compat_eval import evaluate, summary, write_gate
from closet_worker.recsys.engine import ideas, ranked_candidates
from closet_worker.recsys.model import History

from .recsys_fixtures import TODAY, closet, ctx, piece

TINY = compat.CompatConfig(n_head=2, d_ffn=16, n_layers=1, dropout=0.0)


def _head(seed: int = 0) -> Any:
    torch.manual_seed(seed)
    h = compat.build_head(TINY)
    for p in h.parameters():  # the zero-initialized tokens too, so padding is exercised
        torch.nn.init.normal_(p, std=0.05)
    return h.eval()


def install(folder: Path, head: Any, cfg: compat.CompatConfig = TINY) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    wf = folder / compat.WEIGHTS_FILE
    save_file({k: v.contiguous() for k, v in head.state_dict().items()}, str(wf))
    d = {**cfg.__dict__, "sha256": compat.sha256(wf)}
    (folder / compat.CONFIG_FILE).write_text(json.dumps(d))
    return folder


def open_gate(folder: Path, n: int = 40, hr: float = 0.2, hc: float = 0.3) -> None:
    (folder / compat.GATE_FILE).write_text(
        json.dumps({"open": True, "n": n, "hit_rules": hr, "hit_compat": hc})
    )


def reference(head: Any, outfits: list[list[np.ndarray]]) -> list[float]:
    """predict_score from owj0421/outfit-transformer @ eef4be55, step by step."""
    b, n = len(outfits), max(len(o) for o in outfits)
    d = 2 * compat.HALF
    embs = torch.empty((b, n, d))
    mask = []
    for i, o in enumerate(outfits):
        embs[i, : len(o)] = torch.tensor(np.array(o))
        embs[i, len(o) :] = head.pad_emb
        mask.append([0] * len(o) + [1] * (n - len(o)))
    m = torch.BoolTensor(mask)
    task = torch.cat([head.task_emb, head.predict_emb], dim=-1)
    x = torch.cat([task.view(1, 1, -1).expand(b, -1, -1), embs], dim=1)
    m = torch.cat([torch.zeros(b, 1, dtype=torch.bool), m], dim=1)
    half = d // 2
    x = torch.cat(
        [F.normalize(x[:, :, :half], p=2, dim=-1), F.normalize(x[:, :, half:], p=2, dim=-1)],
        dim=-1,
    )
    h = head.style_enc(x, src_key_padding_mask=m)
    return [float(v) for v in head.predict_ffn(h[:, 0, :]).squeeze(-1)]


def rand_vec(rng: np.random.Generator) -> np.ndarray:
    v = rng.normal(size=compat.HALF).astype(np.float32)
    return v / np.linalg.norm(v)


def text_stub(prompts: list[str]) -> np.ndarray:
    out = []
    for s in prompts:
        rng = np.random.default_rng(abs(hash(s)) % (2**32))
        out.append(rand_vec(rng))
    return np.stack(out)


# ---------------------------------------------------------------- the head


def test_parity_with_repo_math_including_padding() -> None:
    head = _head()
    rng = np.random.default_rng(1)
    outfits = [
        [np.concatenate([rand_vec(rng), rand_vec(rng)]) for _ in range(k)] for k in (2, 4, 3)
    ]
    n = 4
    x = np.zeros((3, n, 2 * compat.HALF), dtype=np.float32)
    for i, o in enumerate(outfits):
        x[i, : len(o)] = np.stack(o)
    with torch.no_grad():
        got = head(torch.from_numpy(x), torch.tensor([len(o) for o in outfits])).tolist()
        want = reference(head, outfits)
    assert got == pytest.approx(want, abs=1e-5)


def test_load_checks_sha_keys_and_absence(tmp_path: Path) -> None:
    assert compat.load_head(tmp_path / "none") is None
    folder = install(tmp_path / "ok", _head())
    loaded = compat.load_head(folder)
    assert loaded is not None and loaded[1].n_layers == 1

    bad = install(tmp_path / "sha", _head())
    cfg = json.loads((bad / compat.CONFIG_FILE).read_text())
    (bad / compat.CONFIG_FILE).write_text(json.dumps({**cfg, "sha256": "0" * 64}))
    with pytest.raises(compat.CompatError, match="SHA-256"):
        compat.load_head(bad)

    extra = tmp_path / "keys"
    extra.mkdir()
    sd = {k: v.contiguous() for k, v in _head().state_dict().items()}
    sd["embed_ffn.0.weight"] = torch.zeros(4, 4)
    save_file(sd, str(extra / compat.WEIGHTS_FILE))
    (extra / compat.CONFIG_FILE).write_text(
        json.dumps({**TINY.__dict__, "sha256": compat.sha256(extra / compat.WEIGHTS_FILE)})
    )
    with pytest.raises(RuntimeError, match="Unexpected key"):
        compat.load_head(extra)


def test_wrong_embedder_is_refused(tmp_path: Path) -> None:
    folder = install(tmp_path, _head(), compat.CompatConfig(**{**TINY.__dict__, "embedder": "x"}))
    with pytest.raises(compat.CompatError, match="embeddings"):
        compat.load_head(folder)


# ---------------------------------------------------------------- the gate


def test_gate_closed_by_default_and_rechecked(tmp_path: Path) -> None:
    assert compat.read_gate(tmp_path).open is False
    open_gate(tmp_path, n=12)  # a hand-edited "open" with too few picks stays closed
    assert compat.read_gate(tmp_path).open is False
    open_gate(tmp_path, n=40, hr=0.3, hc=0.3)  # a tie isn't a win
    assert compat.read_gate(tmp_path).open is False
    open_gate(tmp_path, n=40, hr=0.3, hc=0.35)
    assert compat.read_gate(tmp_path).open is True


def test_decide_gate() -> None:
    assert compat.decide_gate(29, 0.1, 0.9, "t").open is False
    assert compat.decide_gate(30, 0.4, 0.4, "t").open is False
    assert compat.decide_gate(30, 0.4, 0.41, "t").open is True


def test_open_scorer_needs_model_and_gate(tmp_path: Path) -> None:
    calls: list[str] = []

    def vecs() -> dict[str, list[float]]:
        calls.append("vecs")
        return {}

    def text() -> compat.TextEmbed:
        return text_stub

    assert compat.open_scorer(tmp_path, vecs, text) is None  # nothing installed
    install(tmp_path, _head())
    assert compat.open_scorer(tmp_path, vecs, text) is None  # gate closed
    assert calls == []  # nothing fetched while it's off
    assert compat.open_scorer(tmp_path, vecs, text, require_gate=False) is not None
    open_gate(tmp_path)
    assert compat.open_scorer(tmp_path, vecs, text) is not None


def test_status(tmp_path: Path) -> None:
    assert compat.status(tmp_path) == {"installed": False, "on": False, "n": 0, "need": 30}
    install(tmp_path, _head())
    open_gate(tmp_path, n=31)
    assert compat.status(tmp_path) == {"installed": True, "on": True, "n": 31, "need": 30}


# ---------------------------------------------------------------- scoring


def scorer_with(pieces: list[Any], missing: set[str] = frozenset()) -> compat.CompatScorer:  # type: ignore[assignment]
    rng = np.random.default_rng(2)
    vecs = {p.id: rand_vec(rng).tolist() for p in pieces if p.id not in missing}
    return compat.CompatScorer(_head(), TINY, vecs, text_stub)


def test_scores_skip_accessories_and_missing_embeddings() -> None:
    top = piece("t", "Tops", type="oxford shirt", color_name="navy")
    bottom = piece("b", "Bottoms", type="chinos", color_name="khaki")
    watch = piece("w", "Accessories", type="watch")
    other = piece("x", "Bottoms", type="jeans", color_name="indigo")
    s = scorer_with([top, bottom, watch], missing={"x"})
    a, b, c, d = s.scores([(top, bottom), (top, bottom, watch), (top, other), (top,)])
    assert a is not None and -1 <= a <= 1
    assert b == a  # the watch isn't scored
    assert c is None  # no image embedding for "x"
    assert d is None  # one piece isn't an outfit


def test_scores_same_in_and_across_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    ps = closet()
    s = scorer_with(ps)
    cands = [(a, b) for a in ps[:2] for b in ps[2:4]] + [(ps[0], ps[2], ps[5])]
    whole = s.scores(cands)
    monkeypatch.setattr(compat, "BATCH", 2)
    assert s.scores(cands) == pytest.approx(whole, abs=1e-5)  # padding doesn't change scores


def test_describe() -> None:
    assert compat.describe(piece("a", "Tops", type="oxford shirt", color_name="navy"), TINY) == (
        "navy oxford shirt"
    )
    assert compat.describe(piece("b", "Tops", name="Tee"), TINY) == "tee"


def test_rules_unchanged_without_scorer() -> None:
    ps = closet()
    _, ranked = ranked_candidates(ps, ctx(), History())
    assert all("compat" not in s.terms for _, s in ranked)
    picks = ideas(ps, ctx(), History())
    assert [[p.id for p in o] for o, _ in picks] == [
        [p.id for p in o] for o, _ in ideas(ps, ctx(), History(), compat=None)
    ]


class Favor:
    """A stand-in scorer that likes one outfit (by its main pieces)."""

    cfg = TINY

    def __init__(self, ids: frozenset[str]) -> None:
        self.ids = ids

    def scores(self, outfits: list[Any]) -> list[float | None]:
        return [
            1.0 if frozenset(p.id for p in o if p.category != "Accessories") == self.ids else -1.0
            for o in outfits
        ]


def test_scorer_term_moves_ranking() -> None:
    ps = closet()
    _, ranked = ranked_candidates(ps, ctx(), History())
    last = frozenset(p.id for p in ranked[-1][0])
    _, boosted = ranked_candidates(ps, ctx(), History(), compat=Favor(last))  # type: ignore[arg-type]
    assert frozenset(p.id for p in boosted[0][0]) == last
    assert boosted[0][1].terms["compat"] == 1.0


# ---------------------------------------------------------------- compat-eval


def event(ids: list[str], action: str = "worn", day: str = TODAY.isoformat()) -> dict[str, Any]:
    return {"occasion": "office", "item_ids": ids, "context": {"date": day}, "action": action}


def test_evaluate_counts_hits_and_skips(tmp_path: Path) -> None:
    ps = closet()
    _, ranked = ranked_candidates(ps, ctx(), History())
    worst = sorted(p.id for p in ranked[-1][0])
    best = sorted(p.id for p in ranked[0][0])
    events = [
        event(best),
        event(best),  # same outfit and day: counted once
        event(worst),
        event(worst, action="skipped"),  # not a pick
        event(["gone-shirt", "grey-chinos"]),  # piece deleted since
    ]
    r = evaluate(ps, events, [], None, Favor(frozenset(worst)))  # type: ignore[arg-type]
    # Rules find only the best; favoring the worst lifts it into the top 3 and keeps the best.
    assert (r.n, r.skipped, r.hits_rules, r.hits_compat) == (2, 1, 1, 2)
    g = write_gate(tmp_path, r)
    assert g.open is False
    assert json.loads((tmp_path / compat.GATE_FILE).read_text())["n"] == 2
    text = summary(r, g)
    assert "28 more to go" in text and "50% (1/2)" in text and "100% (2/2)" in text


def test_evaluate_ignores_wears_from_that_day_on() -> None:
    ps = closet()
    _, ranked = ranked_candidates(ps, ctx(), History())
    best = sorted(p.id for p in ranked[0][0])
    logs = [{"worn_on": TODAY.isoformat(), "item_ids": best}]  # the pick itself
    r = evaluate(ps, [event(best)], logs, None, Favor(frozenset()))  # type: ignore[arg-type]
    assert r.hits_rules == 1  # no "worn today" penalty from its own wear


def test_head_state_takes_only_head_keys_from_a_repo_checkpoint() -> None:
    from closet_worker.recsys.compat_head import head_state

    sd = {f"module.{k}": v for k, v in _head().state_dict().items()}
    sd["module.item_enc.image_enc.model.weight"] = torch.zeros(1)
    sd["module.embed_ffn.0.weight"] = torch.zeros(1)
    sd["module.embed_emb"] = torch.zeros(1)
    fresh = compat.build_head(TINY)
    fresh.load_state_dict(head_state(sd), strict=True)  # no missing, no unexpected keys
