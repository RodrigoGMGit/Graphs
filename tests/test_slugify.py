from chapter_sync.graphs import _slugify


def test_slugify_basic():
    assert _slugify('File name.xlsx') == 'File_name.xlsx'
    assert _slugify('áéí.xlsx') == 'aei.xlsx'
