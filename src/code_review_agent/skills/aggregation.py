from __future__ import annotations

from pathlib import Path

from ..review import run_aggregate


def run(*, output_path: Path, input_paths: tuple[Path, ...]) -> None:
    run_aggregate(output_path=output_path, input_paths=input_paths)
