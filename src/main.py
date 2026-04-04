from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


import argparse
import logging
from pathlib import Path
from typing import Optional

from config import DATA_DIR, INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, COMPANY_CONFIG
from utils import process_company
from src.workflow import (
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
            print(f"ERROR: Missing directory: {p}")
            ok = False

    if input_dir and not in_dir.exists():
        print(f"WARNING: Input footage root does not exist: {in_dir}")

    if company:
        assets = COMPANY_CONFIG.get(company)
        if not assets:
            print(f"ERROR: Unknown company: {company}")
            return False
        if not assets.logo.exists():
            print(f"WARNING: {company} missing logo: {assets.logo} (watermark will be skipped)")
        if not assets.bgm.exists():
            print(f"WARNING: {company} missing bgm: {assets.bgm} (BGM will be skipped)")

    if script:
        sp = Path(script).expanduser().resolve()
        if not sp.exists():
            print(f"ERROR: Script does not exist: {sp}")
            ok = False
    return ok

def cmd_run(args: argparse.Namespace) -> int:
    if not check_environment(args.company, args.script, args.input):
        print("\nFix the missing directories / assets / script and run again.")
        return 1

    if not args.company:
        print("ERROR: --company is required")
        return 1

    if args.creative:
        creative_path = Path(args.creative).expanduser().resolve()
        if not creative_path.exists():
            print(f"ERROR: Creative script not found: {creative_path}")
            return 1
        process_company(args.company, script_path=str(creative_path), input_dir=args.input)
        print("\nDone")
        return 0

    process_company(args.company, script_path=args.script, input_dir=args.input)

    runtime_run_dir = str(os.environ.get("VIDEO_AUTOMATION_RUN_DIR", "") or "").strip()
    if runtime_run_dir:
        out_dir = Path(runtime_run_dir).expanduser().resolve()
        mp4s = [pp for pp in out_dir.iterdir() if pp.is_file() and pp.suffix.lower() == ".mp4"] if out_dir.exists() else []
        if not mp4s:
            print("ERROR: Render finished without a final video file. Check _internal/render.log.")
            return 1

    print("\nDone")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("Available companies:")
    for name in COMPANY_CONFIG.keys():
        print(f" - {name}")
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    creative_path = Path(args.creative).expanduser().resolve()
    if not creative_path.exists():
        print(f"ERROR: Creative script not found: {creative_path}")
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
    print(f"OK: Task rows created: {out_path}")
    print(f"OK: HTML guide created: {html_path}")
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
