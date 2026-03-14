#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
INPUT_ROOT = ROOT / "input_videos"
EXPORT_DIR = ROOT / "docs" / "pool_gap_reports"
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv"}

NON_ENTRY_KEYS = {"version", "meta", "status", "about", "principles", "governed_fields", "notes", "entries"}
SEMANTIC_FIELDS = ["human_label", "shoot_brief", "success_criteria", "fallback", "purpose"]
DEFAULT_FIELDS = ["energy", "quality_status", "continuity_group", "intro_safe", "hero_safe", "outro_safe"]


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


def load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def choose_plan(brand_dir: Path, plan_name: str) -> Path:
    plan_dir = brand_dir / "pool_plans"
    if not plan_dir.exists():
        raise FileNotFoundError(f"Missing pool_plans directory: {plan_dir}")

    slug = safe_slug(plan_name or "default")
    for ext in (".yaml", ".yml"):
        p = plan_dir / f"{slug}{ext}"
        if p.exists():
            return p

    raise FileNotFoundError(f"Could not find plan '{plan_name}' under {plan_dir}")


def extract_registry_entries(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}

    if isinstance(data.get("entries"), dict):
        out: dict[str, dict[str, Any]] = {}
        for k, v in (data.get("entries") or {}).items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k] = v
        return out

    out: dict[str, dict[str, Any]] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_") or k in NON_ENTRY_KEYS:
            continue
        if isinstance(v, dict):
            out[k] = v
    return out


def load_registry_entries() -> dict[str, dict[str, Any]]:
    registry_path = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
    if not registry_path.exists():
        return {}
    return extract_registry_entries(load_yaml(registry_path))


def hydrate_slot(slot: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hydrated = dict(slot)
    registry_key = str(hydrated.get("registry_key", "") or "").strip()
    entry = registry.get(registry_key, {}) if registry_key else {}
    if not isinstance(entry, dict):
        return hydrated

    for key in SEMANTIC_FIELDS:
        cur = hydrated.get(key)
        if cur is None or (isinstance(cur, str) and not cur.strip()) or (isinstance(cur, list) and not cur):
            if key in entry:
                hydrated[key] = entry.get(key)

    entry_defaults = entry.get("defaults", {}) if isinstance(entry.get("defaults", {}), dict) else {}
    slot_defaults = hydrated.get("defaults", {}) if isinstance(hydrated.get("defaults", {}), dict) else {}
    merged_defaults = dict(slot_defaults)

    for key in DEFAULT_FIELDS:
        if key not in merged_defaults and key in entry_defaults:
            merged_defaults[key] = entry_defaults.get(key)

    if merged_defaults:
        hydrated["defaults"] = merged_defaults

    return hydrated


def canonical_tuple(slot: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(slot.get("scene", "") or "").strip(),
        str(slot.get("content", "") or "").strip(),
        str(slot.get("coverage", "") or "").strip(),
        str(slot.get("move", "") or "").strip(),
    )


def count_pool_matches(factory_files: list[Path], scene: str, content: str, coverage: str, move: str) -> int:
    scene_s = safe_slug(scene)
    content_s = safe_slug(content)
    coverage_s = safe_slug(coverage)
    move_s = safe_slug(move)
    prefix = f"{scene_s}_{content_s}_{coverage_s}_{move_s}_"
    return len(
        [
            p for p in factory_files
            if p.is_file()
            and p.suffix.lower() in VIDEO_SUFFIXES
            and p.name.lower().startswith(prefix.lower())
        ]
    )


def collect_factory_files(orientation: str, brand_name: str) -> tuple[Path, list[Path]]:
    brand_dir = INPUT_ROOT / orientation / brand_name / "factory"
    if not brand_dir.exists():
        return brand_dir, []
    files = sorted([p for p in brand_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES])
    return brand_dir, files


def get_topics(plan_data: dict[str, Any], topic_filter: str = "") -> list[dict[str, Any]]:
    topics = plan_data.get("topics", [])
    if not isinstance(topics, list):
        return []

    out: list[dict[str, Any]] = []
    topic_filter_clean = str(topic_filter or "").strip().lower()

    for topic in topics:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("name", "") or "").strip()
        if topic_filter_clean and name.lower() != topic_filter_clean:
            continue
        out.append(topic)
    return out


def build_gap_rows(topic: dict[str, Any], registry: dict[str, dict[str, Any]], factory_files: list[Path]) -> list[dict[str, Any]]:
    slots = topic.get("slots", [])
    if not isinstance(slots, list):
        return []

    rows: list[dict[str, Any]] = []
    for idx, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            continue

        h = hydrate_slot(slot, registry)
        scene, content, coverage, move = canonical_tuple(h)
        target = int(h.get("target", 0) or 0)
        existing = count_pool_matches(factory_files, scene, content, coverage, move)
        missing = max(target - existing, 0)

        label = str(h.get("human_label", "") or "").strip()
        if not label:
            label = f"{scene} / {content} / {coverage} / {move}"

        rows.append(
            {
                **h,
                "_slot_index": idx,
                "_display_label": label,
                "_tuple_text": " / ".join([scene, content, coverage, move]),
                "_target": target,
                "_existing": existing,
                "_missing": missing,
            }
        )

    rows.sort(key=lambda r: (-int(r["_missing"]), str(r.get("priority", "")), str(r["_display_label"])))
    return rows


def list_block(items: Any) -> str:
    if isinstance(items, list) and items:
        body = "".join(f"<li>{html.escape(str(x))}</li>" for x in items if str(x).strip())
        if body:
            return f"<ul>{body}</ul>"
    if isinstance(items, str) and items.strip():
        return f"<p>{html.escape(items.strip())}</p>"
    return "<p class='muted'>—</p>"


def text_block(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return f"<p>{html.escape(value.strip())}</p>"
    return "<p class='muted'>—</p>"


def priority_pill(priority: str) -> str:
    clean = str(priority or "").strip().lower()
    return f"<span class='pill'>{html.escape(clean or 'priority n/a')}</span>"


def render_topic(topic: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    topic_name = str(topic.get("name", "") or "").strip() or "Untitled Topic"
    total_target = sum(int(r["_target"]) for r in rows)
    total_existing = sum(int(r["_existing"]) for r in rows)
    total_missing = sum(int(r["_missing"]) for r in rows)

    cards = []
    for row in rows:
        cards.append(
            f"""
            <div class="slot-card">
              <div class="slot-top">
                <div>
                  <h3>{html.escape(str(row["_display_label"]))}</h3>
                  <div class="tiny">{html.escape(str(row["_tuple_text"]))}</div>
                  {f"<div class='tiny'>registry_key: {html.escape(str(row.get('registry_key', '') or ''))}</div>" if str(row.get("registry_key", "") or "").strip() else ""}
                </div>
                <div class="slot-meta">
                  {priority_pill(str(row.get("priority", "") or ""))}
                  <span class="pill">target {row["_target"]}</span>
                  <span class="pill ok">have {row["_existing"]}</span>
                  <span class="pill warn">missing {row["_missing"]}</span>
                </div>
              </div>

              <div class="grid">
                <div class="cell">
                  <div class="label">Shoot Brief</div>
                  {text_block(row.get("shoot_brief", ""))}
                </div>
                <div class="cell">
                  <div class="label">Purpose</div>
                  {text_block(row.get("purpose", ""))}
                </div>
                <div class="cell">
                  <div class="label">Success Criteria</div>
                  {list_block(row.get("success_criteria", []))}
                </div>
                <div class="cell">
                  <div class="label">Fallback</div>
                  {list_block(row.get("fallback", []))}
                </div>
              </div>
            </div>
            """
        )

    return f"""
    <section class="topic-section">
      <div class="topic-header">
        <div>
          <h2>{html.escape(topic_name)}</h2>
          <p class="muted">Target {total_target} · Existing {total_existing} · Missing {total_missing}</p>
        </div>
      </div>
      {''.join(cards) if cards else "<p class='muted'>No valid slots in this topic.</p>"}
    </section>
    """


def build_html(
    *,
    brand_name: str,
    plan_name: str,
    orientation: str,
    factory_dir: Path,
    topics: list[dict[str, Any]],
    topic_rows: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    topic_filter: str = "",
) -> str:
    title = f"{brand_name} · {plan_name} · {orientation}"
    subtitle = f"Topic filter: {topic_filter}" if topic_filter else "Full plan gap report"

    grand_target = sum(sum(int(r["_target"]) for r in rows) for _, rows in topic_rows)
    grand_existing = sum(sum(int(r["_existing"]) for r in rows) for _, rows in topic_rows)
    grand_missing = sum(sum(int(r["_missing"]) for r in rows) for _, rows in topic_rows)

    sections = [render_topic(topic, rows) for topic, rows in topic_rows]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)} · Pool Fill Gap Report</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    margin: 24px;
    color: #111;
    background: #fafafa;
  }}
  .page {{
    max-width: 1120px;
    margin: 0 auto;
  }}
  .header {{
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 22px;
  }}
  h1 {{ font-size: 30px; margin: 0 0 8px; }}
  h2 {{ font-size: 22px; margin: 0 0 8px; }}
  h3 {{ font-size: 18px; margin: 0 0 6px; }}
  .muted {{ color: #666; }}
  .tiny {{ color: #777; font-size: 13px; }}
  .summary {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 12px;
  }}
  .topic-section {{ margin-bottom: 28px; }}
  .topic-header {{
    background: white;
    border: 1px solid #ececec;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .slot-card {{
    background: white;
    border: 1px solid #e8e8e8;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  }}
  .slot-top {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 12px;
  }}
  .slot-meta {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .pill {{
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    color: #333;
  }}
  .pill.ok {{
    background: #ecfdf5;
    border-color: #a7f3d0;
  }}
  .pill.warn {{
    background: #fff7ed;
    border-color: #fdba74;
  }}
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }}
  .cell {{
    background: #fcfcfc;
    border: 1px solid #efefef;
    border-radius: 12px;
    padding: 12px;
  }}
  .label {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #666;
    margin-bottom: 6px;
    font-weight: 600;
  }}
  ul {{
    margin: 0;
    padding-left: 18px;
  }}
  p {{
    margin: 0;
    line-height: 1.5;
  }}
  @media (max-width: 780px) {{
    body {{ margin: 14px; }}
    .grid {{ grid-template-columns: 1fr; }}
    .slot-top {{ flex-direction: column; }}
  }}
</style>
</head>
<body>
  <div class="page">
    <div class="header">
      <h1>{html.escape(title)} · Pool Fill Gap Report</h1>
      <p class="muted">{html.escape(subtitle)}</p>
      <p class="tiny">Factory dir: {html.escape(str(factory_dir))}</p>
      <div class="summary">
        <span class="pill">target {grand_target}</span>
        <span class="pill ok">existing {grand_existing}</span>
        <span class="pill warn">missing {grand_missing}</span>
      </div>
    </div>
    {''.join(sections) if sections else "<p class='muted'>No matching topics were found.</p>"}
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a real pool-fill gap report from plan + current factory footage."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen")
    parser.add_argument("--plan", default="default", help="Plan name (default: default)")
    parser.add_argument("--orientation", default="portrait", choices=["portrait", "landscape"], help="Factory orientation root")
    parser.add_argument("--topic", default="", help="Optional exact topic name filter")
    parser.add_argument("--out", default="", help="Optional custom output path")
    args = parser.parse_args()

    brand_name = str(args.brand_name or "").strip()
    brand_dir = get_brand_dir(brand_name)
    plan_path = choose_plan(brand_dir, args.plan)
    plan_data = load_yaml(plan_path)

    if not isinstance(plan_data, dict):
        raise ValueError(f"Plan YAML must be a dictionary: {plan_path}")

    registry = load_registry_entries()
    plan_brand_name = str(plan_data.get("brand", "") or "").strip() or brand_dir.name
    factory_dir, factory_files = collect_factory_files(args.orientation, plan_brand_name)

    topics = get_topics(plan_data, args.topic)
    topic_rows: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for topic in topics:
        topic_rows.append((topic, build_gap_rows(topic, registry, factory_files)))

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(brand_name) or "brand"
    plan_slug = safe_slug(args.plan) or "default"
    topic_slug = safe_slug(args.topic) if args.topic else ""
    out_path = Path(args.out).expanduser().resolve() if args.out else (
        EXPORT_DIR / f"{slug}_{plan_slug}_{args.orientation}{'_' + topic_slug if topic_slug else ''}_gap_report.html"
    )

    html_text = build_html(
        brand_name=brand_name,
        plan_name=args.plan,
        orientation=args.orientation,
        factory_dir=factory_dir,
        topics=topics,
        topic_rows=topic_rows,
        topic_filter=args.topic,
    )
    out_path.write_text(html_text, encoding="utf-8")

    total_rows = sum(len(rows) for _, rows in topic_rows)
    total_missing = sum(sum(int(r["_missing"]) for r in rows) for _, rows in topic_rows)

    print(f"export_path        : {out_path}")
    print(f"factory_dir        : {factory_dir}")
    print(f"topic_count        : {len(topics)}")
    print(f"slot_count         : {total_rows}")
    print(f"total_missing      : {total_missing}")
    print(f"topic_filter       : {args.topic or '(none)'}")


if __name__ == "__main__":
    main()
