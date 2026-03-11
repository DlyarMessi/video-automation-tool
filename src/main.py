from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, COMPANY_CONFIG
from utils import process_company
from script_loader import load_script

from creative.compiler import CreativeCompiler
from shooting.guide_generator import ShootingGuideGenerator


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def _orientation_from_format(fmt: Optional[str]) -> str:
    s = (fmt or "").strip().lower()
    return "landscape" if s.startswith("landscape") else "portrait"


def _normalize_run_name(name: str) -> str:
    for suffix in (".compiled", ".shooting_guide", ".shooting-guide", ".shootingguide"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def _base_output_root() -> Path:
    base = OUTPUT_DIR
    if base.name in ("portrait", "landscape"):
        base = base.parent
    return base


def check_environment(company: Optional[str], script: Optional[str], input_dir: Optional[str]) -> bool:
    ok = True
    in_dir = Path(input_dir).expanduser().resolve() if input_dir else INPUT_DIR
    for p in [DATA_DIR, _base_output_root(), SCRIPTS_DIR, in_dir]:
        if not p.exists():
            print(f"❌ 缺少目录: {p}")
            ok = False

    if company:
        assets = COMPANY_CONFIG.get(company)
        if not assets:
            print(f"❌ 未知公司: {company}")
            return False
        if not assets.logo.exists():
            print(f"⚠️ {company} 缺少 logo: {assets.logo}（将跳过水印）")
        if not assets.bgm.exists():
            print(f"⚠️ {company} 缺少 bgm: {assets.bgm}（将跳过BGM）")
    else:
        for name, assets in COMPANY_CONFIG.items():
            if not assets.logo.exists():
                print(f"⚠️ {name} 缺少 logo: {assets.logo}（将跳过水印）")
            if not assets.bgm.exists():
                print(f"⚠️ {name} 缺少 bgm: {assets.bgm}（将跳过BGM）")

    if script:
        sp = Path(script).expanduser().resolve()
        if not sp.exists():
            print(f"❌ 指定脚本不存在: {sp}")
            ok = False
    return ok


# -----------------------------
# Creative integration helpers
# -----------------------------
def _dump_yaml(data: dict, out_path: Path) -> None:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "需要写出 YAML，但当前环境没有安装 PyYAML。\n"
            "请执行: python3 -m pip install pyyaml\n"
            f"原始错误: {e}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _default_output_dir(company: str, run_name: str, orientation: str) -> Path:
    base = _base_output_root()
    d = base / orientation / company / run_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compile_creative_to_production(
    creative_path: Path,
    company: str,
    out_path: Optional[Path] = None
) -> Path:
    creative = load_script(creative_path)

    meta = creative.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    creative["meta"] = meta

    if not meta.get("output_name"):
        meta["output_name"] = f"{company}_compiled.mp4"

    compiler = CreativeCompiler()
    production = compiler.compile(creative)

    # ✅ keep project as-is (includes audio passthrough if present)
    proj = production.get("project", {}) if isinstance(production.get("project", {}), dict) else {}
    dsl = {
        "project": proj,
        "timeline": production.get("timeline", []),
    }

    run_name = _normalize_run_name(creative_path.stem)
    fmt = ""
    out_cfg = proj.get("output", {}) if isinstance(proj.get("output", {}), dict) else {}
    if isinstance(out_cfg, dict):
        fmt = str(out_cfg.get("format", ""))

    orientation = _orientation_from_format(fmt)

    # ✅ only create default output dir when --out not supplied
    if out_path is None:
        out_dir = _default_output_dir(company, run_name, orientation)
        out_path = out_dir / f"{run_name}.compiled.yaml"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    _dump_yaml(dsl, out_path)
    return out_path


def _generate_shooting_guide(
    creative_path: Path,
    company: str,
    out_path: Optional[Path] = None
) -> Path:
    creative = load_script(creative_path)
    generator = ShootingGuideGenerator()
    guide = generator.generate(creative)

    run_name = _normalize_run_name(creative_path.stem)
    fmt = (creative.get("meta", {}) or {}).get("output", {}) if isinstance(creative.get("meta", {}), dict) else {}
    out_fmt = ""
    if isinstance(fmt, dict):
        out_fmt = str(fmt.get("format", ""))
    orientation = _orientation_from_format(out_fmt)

    out_dir = _default_output_dir(company, run_name, orientation)

    if out_path is None:
        out_path = out_dir / f"{run_name}.shooting_guide.json"

    import json
    out_path.write_text(json.dumps(guide, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        from shooting.guide_generator import generate_rename_plan  # type: ignore
        rename_text = generate_rename_plan(guide)
        rename_path = out_dir / f"{run_name}.rename_plan.txt"
        rename_path.write_text(rename_text, encoding="utf-8")
    except Exception as e:
        logging.warning("⚠️ 生成 rename_plan.txt 失败（将忽略）：%s", e)

    if hasattr(generator, "render_markdown"):
        try:
            md_text = generator.render_markdown(guide)  # type: ignore
            md_path = out_dir / f"{run_name}.shooting_guide.md"
            md_path.write_text(md_text, encoding="utf-8")
        except Exception as e:
            logging.warning("⚠️ 生成 shooting_guide.md 失败（将忽略）：%s", e)

    return out_path


# -----------------------------
# Commands
# -----------------------------
def cmd_run(args: argparse.Namespace) -> int:
    if not check_environment(args.company, args.script, args.input):
        print("\n👉 请根据提示补齐目录/素材/脚本后再运行。")
        return 1

    if args.all:
        for name in COMPANY_CONFIG.keys():
            process_company(name, script_path=args.script, input_dir=args.input)
        print("\n✨ 完成")
        return 0

    if not args.company:
        print("❌ 必须指定 --company，或使用 --all")
        return 1

    if args.creative:
        creative_path = Path(args.creative).expanduser().resolve()
        if not creative_path.exists():
            print(f"❌ 指定 creative 脚本不存在: {creative_path}")
            return 1
        compiled_path = _compile_creative_to_production(creative_path, args.company)
        logging.info("✅ 已编译 Creative Script → Production Script: %s", compiled_path)
        process_company(args.company, script_path=str(compiled_path), input_dir=args.input)
        print("\n✨ 完成")
        return 0

    process_company(args.company, script_path=args.script, input_dir=args.input)
    print("\n✨ 完成")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("可用公司：")
    for name in COMPANY_CONFIG.keys():
        print(f" - {name}")
    print("\n脚本目录：", str(SCRIPTS_DIR))
    print("提示：默认脚本发现规则是 scripts/<company>_promo.(yaml/yml/toml/json/txt)")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    if not args.company:
        print("❌ 必须指定 --company（用于输出路径与资源绑定）")
        return 1
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ 指定 creative 脚本不存在: {creative_path}")
        return 1
    out_path = Path(args.out).expanduser().resolve() if args.out else None
    compiled_path = _compile_creative_to_production(creative_path, args.company, out_path=out_path)
    print(f"✅ 已生成 Production Script: {compiled_path}")
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    if not args.company:
        print("❌ 必须指定 --company（用于输出路径与资源绑定）")
        return 1
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ 指定 creative 脚本不存在: {creative_path}")
        return 1
    out_path = Path(args.out).expanduser().resolve() if args.out else None
    guide_path = _generate_shooting_guide(creative_path, args.company, out_path=out_path)
    print(f"✅ 已生成 Shooting Guide: {guide_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="video-automation-tool",
        description="视频自动化剪辑系统（MoviePy 2.x）",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="输出更多调试日志")

    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="运行生成视频")
    run.add_argument("--company", help="公司名，例如 Siglen / Fareo")
    run.add_argument("--all", action="store_true", help="运行所有公司（忽略 --company）")
    run.add_argument("--script", help="指定生产脚本路径（可选）")
    run.add_argument("--creative", help="指定创意脚本路径（可选）")
    run.add_argument("--input", help="指定素材目录（可选），例如 /Volumes/MySSD/input_videos")
    run.set_defaults(func=cmd_run)

    lst = sub.add_parser("list", help="列出公司与脚本规则")
    lst.set_defaults(func=cmd_list)

    cp = sub.add_parser("compile", help="将 Creative Script 编译为 Production Script（生成可跑 YAML）")
    cp.add_argument("--company", required=True, help="公司名（用于输出路径与资源绑定）")
    cp.add_argument("--creative", required=True, help="创意脚本路径（yaml/yml/json/toml）")
    cp.add_argument("--out", help="输出 production 脚本路径（可选）")
    cp.set_defaults(func=cmd_compile)

    gd = sub.add_parser("guide", help="从 Creative Script 生成拍摄清单（Shooting Guide）")
    gd.add_argument("--company", required=True, help="公司名（用于输出路径与资源绑定）")
    gd.add_argument("--creative", required=True, help="创意脚本路径（yaml/yml/json/toml）")
    gd.add_argument("--out", help="输出 guide 路径（可选）")
    gd.set_defaults(func=cmd_guide)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())