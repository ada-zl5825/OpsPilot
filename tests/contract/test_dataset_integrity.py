from benchmarks.datasets.check_integrity import check_integrity


def test_current_dataset_has_no_integrity_errors() -> None:
    assert check_integrity() == []
