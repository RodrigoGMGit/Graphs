from pathlib import Path


def make_dirs_if_missing(*dirs: str | Path) -> None:
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

