from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def project_root_from_config(config_path: str | Path) -> Path:
    p = Path(config_path).resolve()
    return p.parent.parent if p.parent.name == "config" else p.parent


def resolve_paths(cfg: dict, config_path: str | Path) -> dict:
    root = project_root_from_config(config_path)
    cfg = dict(cfg)
    for key in ("data_dir", "output_dir"):
        p = Path(cfg[key])
        if not p.is_absolute():
            p = root / p
        cfg[key] = p.resolve()
    cfg["project_root"] = root
    return cfg
