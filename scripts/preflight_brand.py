#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
DOCS_AUDIT_DIR = ROOT / "docs" / "brand_audits"


def safe_slug(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_brand_dir(brand_name: str) -> Path:
    clean = str(brand_name or "").strip()
    if clean == "_starter":
        return BRANDS_DIR / "_starter"

    slug = safe_slug(clean)
    if slug == "starter" and (BRANDS_DIR / "_starter").exists():
        return BRANDS_DIR / "_starter"

    return BRANDS_DIR / slug


def run_cmd(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout


def status_label(code: int) -> str:
    return "PASS" if code == 0 else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a brand-level preflight over registry, plan validation, audit, and sync dry-run."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen or _starter")
    parser.add_argument("--plan", default="default", help="Plan name (default: default)")
    parser.add_argument("--write-report", action="store_true", help="Write a consolidated markdown report")
    args = parser.parse_args()

    brand_name = str(args.brand_name or "").strip()
    brand_dir = get_brand_dir(brand_name)
    logo_path = brand_dir / "logo.png"

    py = sys.executable

    registry_code, registry_out = run_cmd([py, "scripts/validate_canonical_registry.py"])
    plan_code, plan_out = run_cmd([py, "scripts/validate_pool_plan.py", brand_name, "--plan", args.plan])

    audit_args = [py, "scripts/audit_brand_setup.py", brand_name, "--plan", args.plan]
    if args.write_report:
        audit_args.append("--write-report")
    audit_code, audit_out = run_cmd(audit_args)

    sync_code, sync_out = run_cmd([py, "scripts/sync_pool_plan_from_registry.py", brand_name, "--plan", args.plan])

    overall_ok = (registry_code == 0) and (plan_code == 0) and (audit_code == 0) and (sync_code == 0)

    print(f"=== Brand Preflight | {brand_name} / {args.plan} ===")
    print(f"brand_dir           : {brand_dir}")
    print(f"logo                : {'found' if logo_path.exists() else 'optional / not set'}")
    print(f"registry_validate   : {status_label(registry_code)}")
    print(f"pool_plan_validate  : {status_label(plan_code)}")
    print(f"brand_audit         : {status_label(audit_code)}")
    print(f"registry_sync_dry   : {status_label(sync_code)}")
    print(f"overall             : {'PASS' if overall_ok else 'FAIL'}")

    if args.write_report:
        DOCS_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        slug = safe_slug(brand_name)
        if not slug and brand_name == "_starter":
            slug = "starter"
        if not slug:
            slug = "brand"
        report_path = DOCS_AUDIT_DIR / f"{slug}_preflight.md"

        report = []
        report.append(f"# Brand Preflight · {brand_name}")
        report.append("")
        report.append("## Summary")
        report.append("")
        report.append(f"- Brand dir: `{brand_dir.relative_to(ROOT)}`")
        report.append(f"- Logo: `{'found' if logo_path.exists() else 'optional / not set'}`")
        report.append(f"- Registry validation: **{status_label(registry_code)}**")
        report.append(f"- Pool plan validation: **{status_label(plan_code)}**")
        report.append(f"- Brand audit: **{status_label(audit_code)}**")
        report.append(f"- Registry sync dry-run: **{status_label(sync_code)}**")
        report.append(f"- Overall: **{'PASS' if overall_ok else 'FAIL'}**")
        report.append("")
        report.append("## Registry validation output")
        report.append("")
        report.append("```text")
        report.append(registry_out.rstrip())
        report.append("```")
        report.append("")
        report.append("## Pool plan validation output")
        report.append("")
        report.append("```text")
        report.append(plan_out.rstrip())
        report.append("```")
        report.append("")
        report.append("## Brand audit output")
        report.append("")
        report.append("```text")
        report.append(audit_out.rstrip())
        report.append("```")
        report.append("")
        report.append("## Registry sync dry-run output")
        report.append("")
        report.append("```text")
        report.append(sync_out.rstrip())
        report.append("```")
        report.append("")
        report_path.write_text("\n".join(report), encoding="utf-8")
        print(f"report_written      : {report_path.relative_to(ROOT)}")

    if not overall_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
