from chapter_sync.graphs import normalize_name


def test_normalize_name_basic():
    assert normalize_name("Rene Ruben Plaz Cabrera") == "RENERUBENPLAZCABRERA"
    assert normalize_name(" René  Plaz ") == "RENEPLAZ"
    assert normalize_name(123) == ""
