"""Tests for file discovery functions with subdirectory structure."""

import os
import tempfile
import shutil
from pathlib import Path
import pytest

from chapter_sync import graphs
from chapter_sync.chapter_leaders import (
    _list_excels,
    _find_by_tokens,
    find_source_for,
)


@pytest.fixture
def temp_files_dir():
    """Create a temporary directory structure for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Create subdirectory structure
        subdirs = ["Calidad", "DR", "NivelesMadurez", "TMD"]
        for subdir in subdirs:
            os.makedirs(os.path.join(temp_dir, subdir), exist_ok=True)

        # Create test Excel files in subdirectories
        test_files = {
            "Calidad/Calidad.xlsx": "Calidad",
            "DR/DR.xlsx": "DR",
            "NivelesMadurez/NivelesMadurez.xlsx": "NivelesMadurez",
            "TMD/TMD.xlsx": "TMD",
        }

        for rel_path, content in test_files.items():
            full_path = os.path.join(temp_dir, rel_path)
            # Create empty file (just for testing discovery)
            Path(full_path).touch()

        # Also create a file at root level for backward compatibility test
        root_file = os.path.join(temp_dir, "TestRoot.xlsx")
        Path(root_file).touch()

        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


def test_list_excels_recursive(temp_files_dir):
    """Test that _list_excels finds files in subdirectories."""
    files = _list_excels(temp_files_dir)
    assert len(files) == 5  # 4 in subdirs + 1 at root
    # Normalize paths for cross-platform compatibility
    files_normalized = [f.replace("\\", "/") for f in files]
    assert "Calidad/Calidad.xlsx" in files_normalized
    assert "DR/DR.xlsx" in files_normalized
    assert "NivelesMadurez/NivelesMadurez.xlsx" in files_normalized
    assert "TMD/TMD.xlsx" in files_normalized
    assert "TestRoot.xlsx" in files_normalized


def test_find_file_by_keyword_subdirectory(temp_files_dir):
    """Test _find_file_by_keyword finds files in subdirectories."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir
        # Test finding Calidad file
        result = graphs._find_file_by_keyword("CALIDAD")
        assert result is not None
        assert "Calidad" in result
        assert result.endswith("Calidad.xlsx")
        assert os.path.exists(result)

        # Test finding TMD file
        result = graphs._find_file_by_keyword("TMD")
        assert result is not None
        assert "TMD" in result
        assert result.endswith("TMD.xlsx")
    finally:
        graphs.FILES_DIR = original_files_dir


def test_find_by_tokens_subdirectory(temp_files_dir):
    """Test _find_by_tokens finds files in subdirectories."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir

        # Test finding DR file
        result = _find_by_tokens(["DR", "dashboard"])
        assert result is not None
        assert "DR" in result
        assert result.endswith("DR.xlsx")

        # Test finding NivelesMadurez file
        result = _find_by_tokens(["NivelesMadurez", "Reporte_NM"])
        assert result is not None
        assert "NivelesMadurez" in result
        assert result.endswith("NivelesMadurez.xlsx")
    finally:
        graphs.FILES_DIR = original_files_dir


def test_find_source_for_all_types(temp_files_dir):
    """Test find_source_for locates all file types in subdirectories."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir

        # Test calidad
        result = find_source_for("calidad")
        assert result is not None
        assert "Calidad" in result

        # Test dedicacion
        result = find_source_for("dedicacion")
        assert result is not None
        assert "DR" in result

        # Test madurez
        result = find_source_for("madurez")
        assert result is not None
        assert "NivelesMadurez" in result

        # Test tiempo
        result = find_source_for("tiempo")
        assert result is not None
        assert "TMD" in result
    finally:
        graphs.FILES_DIR = original_files_dir


def test_backward_compatibility_root_level(temp_files_dir):
    """Test that files at root level still work (backward compatibility)."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir

        # Should find TestRoot.xlsx at root level
        result = graphs._find_file_by_keyword("TESTROOT")
        assert result is not None
        assert "TestRoot.xlsx" in result
        # Should be at root, not in subdirectory
        rel_path = os.path.relpath(result, temp_files_dir)
        assert "/" not in rel_path and "\\" not in rel_path
    finally:
        graphs.FILES_DIR = original_files_dir


def test_multiple_matches_latest_selected(temp_files_dir):
    """Test that multiple matches return the latest file by date."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir

        # Create files with dates in names
        old_file = os.path.join(temp_files_dir, "Calidad", "Calidad-2025-01-15.xlsx")
        new_file = os.path.join(temp_files_dir, "Calidad", "Calidad-2025-10-27.xlsx")
        Path(old_file).touch()
        Path(new_file).touch()

        # Should return the latest file (by date in filename)
        result = graphs._find_file_by_keyword("CALIDAD")
        assert result is not None
        assert "2025-10-27" in result  # Latest date
    finally:
        graphs.FILES_DIR = original_files_dir


def test_multiple_matches_no_date_fallback(temp_files_dir):
    """Test that files without dates fall back to modification time."""
    original_files_dir = graphs.FILES_DIR
    try:
        graphs.FILES_DIR = temp_files_dir

        # Create files without dates
        file1 = os.path.join(temp_files_dir, "Calidad", "Calidad.xlsx")
        file2 = os.path.join(temp_files_dir, "Calidad", "Calidad2.xlsx")
        Path(file1).touch()
        # Wait a bit and create second file (newer modification time)
        import time

        time.sleep(0.1)
        Path(file2).touch()

        # Should return one of them (newest by mtime)
        result = graphs._find_file_by_keyword("CALIDAD")
        assert result is not None
        assert "Calidad" in result
    finally:
        graphs.FILES_DIR = original_files_dir


def test_file_discovery_integration(temp_files_dir):
    """Integration test: verify file discovery works end-to-end."""
    original_files_dir = graphs.FILES_DIR
    original_cache_dir = graphs.CACHE_DIR
    try:
        graphs.FILES_DIR = temp_files_dir
        graphs.CACHE_DIR = os.path.join(temp_files_dir, "cached_files")

        # Test that all file types can be found
        file_types = ["calidad", "dedicacion", "madurez", "tiempo"]
        for file_type in file_types:
            path = find_source_for(file_type)
            assert path is not None, f"Could not find file for {file_type}"
            assert os.path.exists(path), f"File path does not exist: {path}"
            assert path.endswith(".xlsx"), f"File is not Excel: {path}"
    finally:
        graphs.FILES_DIR = original_files_dir
        graphs.CACHE_DIR = original_cache_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
