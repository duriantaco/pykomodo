# src/config.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class PriorityRule:
    pattern: str
    score: int

@dataclass
class KomodoConfig:
    max_size: int = 10 * 1024 * 1024
    token_mode: bool = False
    output_dir: Optional[Path] = None
    stream: bool = False
    ignore_patterns: list[str] = None
    priority_rules: list[PriorityRule] = None
    binary_extensions: list[str] = None
