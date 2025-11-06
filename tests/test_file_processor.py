"""Tests for file processing module."""

import tempfile
import shutil
from pathlib import Path
import pytest

from chapter_sync.file_processor import (
    process_downloaded_files,
    parse_date_from_filename,
    extract_date_from_standardized_filename,
    _identify_file_type,
    DMY_DOTS,
    YMD_COMPACT,
    DMY_UNDERSCORE_2Y,
)


@pytest.fixture
def temp_downloads_dir():
    """Create a temporary downloads directory."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_files_dir():
    """Create a temporary files directory."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


def test_parse_date_dmy_dots():
    """Test parsing date from DMY_DOTS format."""
    filename = "Pases a Producción y Reversiones - 27.10.2025.xlsx"
    date_obj = parse_date_from_filename(filename, DMY_DOTS)
    assert date_obj is not None
    assert date_obj.year == 2025
    assert date_obj.month == 10
    assert date_obj.day == 27


def test_parse_date_ymd_compact():
    """Test parsing date from YMD_COMPACT format."""
    filename = "dashboard-20251102.xlsx"
    date_obj = parse_date_from_filename(filename, YMD_COMPACT)
    assert date_obj is not None
    assert date_obj.year == 2025
    assert date_obj.month == 11
    assert date_obj.day == 2


def test_parse_date_dmy_underscore():
    """Test parsing date from DMY_UNDERSCORE_2Y format."""
    filename = "Reporte_NM_26_10_25.xlsx"
    date_obj = parse_date_from_filename(filename, DMY_UNDERSCORE_2Y)
    assert date_obj is not None
    assert date_obj.year == 2025
    assert date_obj.month == 10
    assert date_obj.day == 26


def test_extract_date_from_standardized():
    """Test extracting date from standardized filename."""
    filename = "Calidad-2025-10-27.xlsx"
    date_obj = extract_date_from_standardized_filename(filename)
    assert date_obj is not None
    assert date_obj.year == 2025
    assert date_obj.month == 10
    assert date_obj.day == 27


def test_extract_date_from_standardized_no_date():
    """Test extracting date when no date in filename."""
    filename = "Calidad.xlsx"
    date_obj = extract_date_from_standardized_filename(filename)
    assert date_obj is None


def test_identify_file_type_calidad():
    """Test identifying Calidad file type."""
    filename = "Pases a Producción y Reversiones - 27.10.2025.xlsx"
    result = _identify_file_type(filename)
    assert result is not None
    name, pattern = result
    assert name == "Calidad"
    assert pattern == DMY_DOTS


def test_identify_file_type_tmd():
    """Test identifying TMD file type."""
    filename = "BD Dashboard OKR T.Desarrollo - 03.11.2025.xlsx"
    result = _identify_file_type(filename)
    assert result is not None
    name, pattern = result
    assert name == "TMD"
    assert pattern == DMY_DOTS


def test_identify_file_type_dr():
    """Test identifying DR file type."""
    filename = "dashboard-20251102.xlsx"
    result = _identify_file_type(filename)
    assert result is not None
    name, pattern = result
    assert name == "DR"
    assert pattern == YMD_COMPACT


def test_identify_file_type_nivelesmadurez():
    """Test identifying NivelesMadurez file type."""
    filename = "Reporte_NM_26_10_25.xlsx"
    result = _identify_file_type(filename)
    assert result is not None
    name, pattern = result
    assert name == "NivelesMadurez"
    assert pattern == DMY_UNDERSCORE_2Y


def test_identify_file_type_unknown():
    """Test identifying unknown file type."""
    filename = "UnknownFile.xlsx"
    result = _identify_file_type(filename)
    assert result is None


class TestProcessDownloadedFiles:
    """Test suite for process_downloaded_files function."""

    def test_process_calidad_file(
        self, temp_downloads_dir, temp_files_dir, monkeypatch
    ):
        """Test processing a Calidad file."""
        # Create test file in downloads
        test_file = (
            temp_downloads_dir / "Pases a Producción y Reversiones - 27.10.2025.xlsx"
        )
        test_file.touch()

        # Mock the directory getters
        def mock_get_downloads():
            return temp_downloads_dir

        def mock_get_files():
            return temp_files_dir

        monkeypatch.setattr(
            "chapter_sync.file_processor._get_downloads_dir",
            mock_get_downloads,
        )
        monkeypatch.setattr(
            "chapter_sync.file_processor._get_files_dir",
            mock_get_files,
        )

        # Process files
        processed = process_downloaded_files([test_file])

        # Verify file was moved
        assert len(processed) == 1
        source, dest = processed[0]
        assert source == test_file
        assert dest.name == "Calidad-2025-10-27.xlsx"
        assert dest.parent == temp_files_dir / "Calidad"
        assert dest.exists()
        assert not source.exists()  # Original should be gone

    def test_process_multiple_files(
        self, temp_downloads_dir, temp_files_dir, monkeypatch
    ):
        """Test processing multiple files of different types."""
        # Create test files
        files = [
            (temp_downloads_dir / "Pases a Producción y Reversiones - 27.10.2025.xlsx"),
            (temp_downloads_dir / "BD Dashboard OKR T.Desarrollo - 03.11.2025.xlsx"),
            temp_downloads_dir / "dashboard-20251102.xlsx",
            temp_downloads_dir / "Reporte_NM_26_10_25.xlsx",
        ]
        for f in files:
            f.touch()

        # Mock the directory getters
        def mock_get_downloads():
            return temp_downloads_dir

        def mock_get_files():
            return temp_files_dir

        monkeypatch.setattr(
            "chapter_sync.file_processor._get_downloads_dir",
            mock_get_downloads,
        )
        monkeypatch.setattr(
            "chapter_sync.file_processor._get_files_dir",
            mock_get_files,
        )

        # Process files
        processed = process_downloaded_files(files)

        # Verify all files were processed
        assert len(processed) == 4

        # Check destinations
        dest_names = {dest.name for _, dest in processed}
        assert "Calidad-2025-10-27.xlsx" in dest_names
        assert "TMD-2025-11-03.xlsx" in dest_names
        assert "DR-2025-11-02.xlsx" in dest_names
        assert "NivelesMadurez-2025-10-26.xlsx" in dest_names

        # Verify originals are gone
        for source, _ in processed:
            assert not source.exists()

    def test_process_duplicate_dates(
        self, temp_downloads_dir, temp_files_dir, monkeypatch
    ):
        """Test processing files with duplicate dates."""
        # Create two different source files that will both standardize
        # to the same destination. Both files have the same date
        # (27.10.2025) and map to "Calidad"
        base_name = "Pases a Producción y Reversiones - 27.10.2025.xlsx"
        file1 = temp_downloads_dir / base_name
        file2_name = "Pases a Producción y Reversiones - 27.10.2025-v2.xlsx"
        file2 = temp_downloads_dir / file2_name
        file1.touch()
        file2.touch()

        # Mock directories
        def mock_get_downloads():
            return temp_downloads_dir

        def mock_get_files():
            return temp_files_dir

        monkeypatch.setattr(
            "chapter_sync.file_processor._get_downloads_dir",
            mock_get_downloads,
        )
        monkeypatch.setattr(
            "chapter_sync.file_processor._get_files_dir",
            mock_get_files,
        )

        # Process files
        processed = process_downloaded_files([file1, file2])

        # Verify both files were processed
        assert len(processed) == 2

        # Check destinations - first should be standard name,
        # second should have (1) suffix
        dest_names = {dest.name for _, dest in processed}
        assert "Calidad-2025-10-27.xlsx" in dest_names
        assert "Calidad-2025-10-27 (1).xlsx" in dest_names

        # Verify both files are in the Calidad directory
        for _, dest in processed:
            assert dest.parent == temp_files_dir / "Calidad"
            assert dest.exists()

        # Verify originals are gone
        assert not file1.exists()
        assert not file2.exists()

    def test_process_file_without_date(
        self, temp_downloads_dir, temp_files_dir, monkeypatch
    ):
        """Test processing file without date (should be skipped)."""
        # Create file without recognizable date
        test_file = temp_downloads_dir / "Pases a Producción y Reversiones.xlsx"
        test_file.touch()

        # Mock directories
        def mock_get_downloads():
            return temp_downloads_dir

        def mock_get_files():
            return temp_files_dir

        monkeypatch.setattr(
            "chapter_sync.file_processor._get_downloads_dir",
            mock_get_downloads,
        )
        monkeypatch.setattr(
            "chapter_sync.file_processor._get_files_dir",
            mock_get_files,
        )

        # Process files
        processed = process_downloaded_files([test_file])

        # File should be skipped (no date found)
        assert len(processed) == 0
        # Original file should still exist
        assert test_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
