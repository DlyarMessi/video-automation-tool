from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, COMPANY_CONFIG
from utils import process_company
from workflow import compile_creative_file_to_production, generate_shooting_rows, render_html_task_table, load_yaml_text


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def _base_output_root() -> Path:
    base = OUTPUT_DIR
    if base.name in ("portrait", "landscape"):
        base = base.parent
    return base


def check_environment(company: Optional[str], script: Optional[str], input_dir: Optional[str]) -> bool:
    ok = True
    in_dir = Path(input_dir).expanduser().resolve() if input_dir else INPUT_DIR
    for p in [DATA_DIR, _base_output_root(), SCRIPTS_DIR]:
        if not p.exists():
            print(f"❌ 缺少目录: {p}")
            ok = False

    if input_dir and not in_dir.exists():
        print(f"⚠️ 输入素材目录不存在: {in_dir}")

    if company:
        assets = COMPANY_CONFIG.get(company)
        if not assets:
            print(f"❌ 未知公司: {company}")
            return False
        if not assets.logo.exists():
            print(f"⚠️ {company} 缺少 logo: {assets.logo}（将跳过水印）")
        if not assets.bgm.exists():
            print(f"⚠️ {company} 缺少 bgm: {assets.bgm}（将跳过BGM）")

    if script:
        sp = Path(script).expanduser().resolve()
        if not sp.exists():
            print(f"❌ 指定脚本不存在: {sp}")
            ok = False
    return ok


def _default_output_dir(company: str, run_name: str) -> Path:
    base = _base_output_root()
    d = base / "portrait" / company / run_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_run(args: argparse.Namespace) -> int:
    if not check_environment(args.company, args.script, args.input):
        print("\n👉 请根据提示补齐目录/素材/脚本后再运行。")
        return 1

    if not args.company:
        print("❌ 必须指定 --company")
        return 1

    if args.creative:
        creative_path = Path(args.creative).expanduser().resolve()
        if not creative_path.exists():
            print(f"❌ 指定 creative 脚本不存在: {creative_path}")
            return 1
        run_name = creative_path.stem
        out_dir = _default_output_dir(args.company, run_name)
        compiled_path = out_dir / f"{run_name}.compiled.yaml"
        compile_creative_file_to_production(creative_path, compiled_path)
        logging.info("✅ 已生成内部 production 脚本: %s", compiled_path)
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
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ 指定 creative 脚本不存在: {creative_path}")
        return 1
    out_path = Path(args.out).expanduser().resolve()
    compile_creative_file_to_production(creative_path, out_path)
    print(f"✅ 已生成 Production Script: {out_path}")
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ 指定 creative 脚本不存在: {creative_path}")
        return 1
    text = creative_path.read_text(encoding="utf-8")
    creative = load_yaml_text(text)
    rows = generate_shooting_rows(creative)

    import json
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out_path.with_suffix(".html")
    html_path.write_text(render_html_task_table(rows), encoding="utf-8")
    print(f"✅ 已生成 Shooting Rows: {out_path}")
    print(f"✅ 已生成 Shooting HTML: {html_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="video-automation-tool", description="Script-first video automation tool")
    p.add_argument("-v", "--verbose", action="store_true", help="输出更多调试日志")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="运行生成视频")
    run.add_argument("--company", help="公司名，例如 Siglen / Fareo")
    run.add_argument("--script", help="指定 production 脚本路径（可选）")
    run.add_argument("--creative", help="指定创意脚本路径（可选）")
    run.add_argument("--input", help="指定素材目录（可选）")
    run.set_defaults(func=cmd_run)

    lst = sub.add_parser("list", help="列出公司")
    lst.set_defaults(func=cmd_list)

    cp = sub.add_parser("compile", help="将 Creative Script 编译为内部 production YAML")
    cp.add_argument("--creative", required=True, help="创意脚本路径")
    cp.add_argument("--out", required=True, help="输出 production 脚本路径")
    cp.set_defaults(func=cmd_compile)

    gd = sub.add_parser("guide", help="从 Creative Script 生成任务 rows")
    gd.add_argument("--creative", required=True, help="创意脚本路径")
    gd.add_argument("--out", required=True, help="输出 rows json 路径")
    gd.set_defaults(func=cmd_guide)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
