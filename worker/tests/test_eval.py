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
