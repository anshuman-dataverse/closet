from __future__ import annotations

from pathlib import Path

from eval.tagging import accuracy, confusion, norm, read_labels, recommend, score


def test_norm() -> None:
    assert norm("  Quarter-Zip  Sweater ") == "quarter zip sweater"


def test_accuracy_ignores_unlabeled_rows() -> None:
    assert accuracy(["a", "b", ""], ["a", "x", "z"]) == (0.5, 2)
    assert accuracy(["", ""], ["a", "b"]) == (0.0, 0)


def test_confusion_matrix() -> None:
    labels, m = confusion(["chinos", "jeans", "jeans"], ["chinos", "chinos", "jeans"])
    assert labels == ["chinos", "jeans"]
    assert m == [[1, 0], [1, 1]]


def test_score_and_recommend(tmp_path: Path) -> None:
    (tmp_path / "labels.csv").write_text(
        "file,item_name,category,type,pattern,color\n"
        "001.jpg,Navy shirt,Tops,Oxford shirt,solid,navy\n"
        "002.jpg,Chinos,Bottoms,chinos,solid,khaki\n"
        ",,,,,\n"
    )
    rows = read_labels(tmp_path / "labels.csv")
    assert len(rows) == 2 and rows[0].truth["type"] == "oxford shirt"
    good = score(
        rows,
        [{"category": "Tops", "type": "oxford shirt"}, {"category": "Bottoms", "type": "chinos"}],
    )
    bad = score(
        rows, [{"category": "Tops", "type": "polo shirt"}, {"category": "Tops", "type": "jeans"}]
    )
    assert good["accuracy"]["category"] == 1.0 and good["targets_met"]
    assert bad["accuracy"]["category"] == 0.5 and not bad["targets_met"]
    assert recommend({"good": good, "bad": bad}) == "good"


def test_fit_labels_normalize() -> None:
    from eval.tagging import norm_fit

    assert norm_fit("Baggy") == "wide" and norm_fit("Wide or baggy") == "wide"
    assert norm_fit("A-line") == "a-line" and norm_fit("flared") == "flare"
    assert norm_fit(" Slim fit ") == "slim" and norm_fit("") == ""


def test_fit_report_precision_per_fit() -> None:
    from eval.tagging import fit_report

    def case(truth: str, guess: str | None, photo: str | None = None) -> dict[str, object]:
        return {"group": "bottoms", "truth": truth, "guess": guess, "photo": photo or guess}

    cases = [
        *[case("flare", "flare") for _ in range(5)],
        case("straight", "flare"),  # a wrong "flared"
        *[case("slim", "slim") for _ in range(3)],  # right, but too few to trust
        case("wide", None, "wide"),  # no guess (the reads disagreed)
    ]
    r = fit_report(cases, min_precision=0.7, min_n=5)
    flare, slim = r["per_fit"]["bottoms/flare"], r["per_fit"]["bottoms/slim"]
    assert (flare["suggested"], flare["right"], flare["precision"], flare["passes"]) == (
        6,
        5,
        0.8333,
        True,
    )
    assert slim["passes"] is False and slim["precision"] == 1.0
    assert r["per_fit"]["bottoms/wide"] == {
        "labeled": 1,
        "suggested": 0,
        "right": 0,
        "precision": 0.0,
        "passes": False,
    }
    assert r["coverage"] == 0.9 and r["accuracy_when_guessed"] == round(8 / 9, 4)
    assert r["photo_model_top1"] == 0.9


def test_add_fit_column_keeps_your_edits(tmp_path: Path) -> None:
    import csv

    from closet_worker.export_eval import add_fit_column

    p = tmp_path / "labels.csv"
    p.write_text(
        "file,item_name,category,type,pattern,color\n001.jpg,Jeans,Bottoms,JEANS FIXED,,\n"
    )
    add_fit_column(p, {"001.jpg": "wide"})
    rows = list(csv.DictReader(p.open()))
    assert rows == [
        {
            "file": "001.jpg",
            "item_name": "Jeans",
            "category": "Bottoms",
            "type": "JEANS FIXED",
            "pattern": "",
            "color": "",
            "fit": "wide",
        }
    ]
    add_fit_column(p, {"001.jpg": "slim"})  # already there: unchanged
    assert next(csv.DictReader(p.open()))["fit"] == "wide"


def test_fit_gate_written_for_the_recommended_model(tmp_path: Path) -> None:
    import json

    from closet_worker.bundle import read_bundle
    from closet_worker.vision.fit import read_gate
    from eval.tagging import write_fit_results

    (tmp_path / "report.json").write_text("{}")
    per = {
        "bottoms/flare": {
            "labeled": 6,
            "suggested": 6,
            "right": 5,
            "precision": 0.83,
            "passes": True,
        },
        "bottoms/wide": {
            "labeled": 2,
            "suggested": 0,
            "right": 0,
            "precision": 0.0,
            "passes": False,
        },
    }
    result = {"models": {"m1": {"fit": {"n_labeled": 8, "per_fit": per}}}}
    z = write_fit_results(tmp_path, result, "m1", "menswear")
    gate = json.loads(read_bundle(z).files["fit_gate.json"])
    assert gate["model"] == "m1" and list(gate["per_fit"]) == ["bottoms/flare"]
    assert read_gate(tmp_path / "fit_gate.json", "m1") == frozenset({"bottoms/flare"})
    assert read_gate(tmp_path / "fit_gate.json", "other-model") == frozenset()
