from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, COMPANY_CONFIG
from utils import process_company
from src.workflow import (
    compile_creative_file_to_production,
    generate_shooting_rows,
    render_html_task_table,
    load_yaml_text,
)


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
            print(f"❌ Missing directory: {p}")
            ok = False

    if input_dir and not in_dir.exists():
        print(f"⚠️ Input footage root does not exist: {in_dir}")

    if company:
        assets = COMPANY_CONFIG.get(company)
        if not assets:
            print(f"❌ Unknown company: {company}")
            return False
        if not assets.logo.exists():
            print(f"⚠️ {company} missing logo: {assets.logo} (watermark will be skipped)")
        if not assets.bgm.exists():
            print(f"⚠️ {company} missing bgm: {assets.bgm} (BGM will be skipped)")

    if script:
        sp = Path(script).expanduser().resolve()
        if not sp.exists():
            print(f"❌ Script does not exist: {sp}")
            ok = False
    return ok


def _default_output_dir(company: str, run_name: str) -> Path:
    base = _base_output_root()
    d = base / "portrait" / company / run_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_run(args: argparse.Namespace) -> int:
    if not check_environment(args.company, args.script, args.input):
        print("\n👉 Fix the missing directories / assets / script and run again.")
        return 1

    if not args.company:
        print("❌ --company is required")
        return 1

    if args.creative:
        creative_path = Path(args.creative).expanduser().resolve()
        if not creative_path.exists():
            print(f"❌ Creative script not found: {creative_path}")
            return 1
        run_name = creative_path.stem
        out_dir = _default_output_dir(args.company, run_name)
        compiled_path = out_dir / f"{run_name}.compiled.yaml"
        compile_creative_file_to_production(creative_path, compiled_path)
        logging.info("✅ Internal production script created: %s", compiled_path)
        process_company(args.company, script_path=str(compiled_path), input_dir=args.input)
        print("\n✨ Done")
        return 0

    process_company(args.company, script_path=args.script, input_dir=args.input)
    print("\n✨ Done")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("Available companies:")
    for name in COMPANY_CONFIG.keys():
        print(f" - {name}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ Creative script not found: {creative_path}")
        return 1
    out_path = Path(args.out).expanduser().resolve()
    compile_creative_file_to_production(creative_path, out_path)
    print(f"✅ Production script created: {out_path}")
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"❌ Creative script not found: {creative_path}")
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
    print(f"✅ Task rows created: {out_path}")
    print(f"✅ HTML guide created: {html_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="video-automation-tool", description="Script-first video automation tool")
    p.add_argument("-v", "--verbose", action="store_true", help="more logs")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="render video")
    run.add_argument("--company", help="company name, e.g. Siglen / Fareo")
    run.add_argument("--script", help="production script path (optional)")
    run.add_argument("--creative", help="creative script path (optional)")
    run.add_argument("--input", help="footage input root (optional)")
    run.set_defaults(func=cmd_run)

    lst = sub.add_parser("list", help="list companies")
    lst.set_defaults(func=cmd_list)

    cp = sub.add_parser("compile", help="compile creative script to internal production YAML")
    cp.add_argument("--creative", required=True, help="creative script path")
    cp.add_argument("--out", required=True, help="production YAML output path")
    cp.set_defaults(func=cmd_compile)

    gd = sub.add_parser("guide", help="generate task rows from creative script")
    gd.add_argument("--creative", required=True, help="creative script path")
    gd.add_argument("--out", required=True, help="task rows json output path")
    gd.set_defaults(func=cmd_guide)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
