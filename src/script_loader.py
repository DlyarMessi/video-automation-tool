from __future__ import annotations

"""Load structured edit scripts for the video automation tool.

Supported:
- YAML (.yaml/.yml) via PyYAML
- TOML (.toml) via tomllib (Py3.11+) or tomli fallback
- JSON (.json)

Design goals:
- tiny, dependency-light
- deterministic errors
"""

from pathlib import Path
import json


def load_script(path: Path) -> dict:
    suffix = path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "需要解析 YAML 脚本，但当前环境没有安装 PyYAML。\n"
                "请执行: python3 -m pip install pyyaml\n"
                f"原始错误: {e}"
            )
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("脚本顶层必须是一个对象(dict)")
        return data

    if suffix == ".toml":
        try:
            import tomllib  # Python 3.11+
        except Exception:
            import tomli as tomllib  # type: ignore
        with path.open("rb") as f:
            data = tomllib.load(f)
        if not isinstance(data, dict):
            raise ValueError("脚本顶层必须是一个对象(dict)")
        return data

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("脚本顶层必须是一个对象(dict)")
        return data

    raise ValueError(f"不支持的脚本格式: {suffix}（支持 .yaml/.yml/.toml/.json）")