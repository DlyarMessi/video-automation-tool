#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "data" / "brands"
REGISTRY_PATH = ROOT / "data" / "taxonomy" / "canonical_registry_v1.yaml"
EXPORT_DIR = ROOT / "docs" / "pool_plan_exports"

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
        entries = data.get("entries") or {}
        out: dict[str, dict[str, Any]] = {}
        for k, v in entries.items():
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
    if not REGISTRY_PATH.exists():
        return {}
    return extract_registry_entries(load_yaml(REGISTRY_PATH))


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


def iter_topics(plan_data: dict[str, Any], topic_filter: str = "") -> list[dict[str, Any]]:
    topics = plan_data.get("topics", [])
    if not isinstance(topics, list):
        return []

    out = []
    topic_filter_clean = str(topic_filter or "").strip().lower()

    for topic in topics:
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("name", "") or "").strip()
        if topic_filter_clean and name.lower() != topic_filter_clean:
            continue
        out.append(topic)
    return out


def canonical_tuple(slot: dict[str, Any]) -> str:
    return " / ".join([
        str(slot.get("scene", "") or "").strip(),
        str(slot.get("content", "") or "").strip(),
        str(slot.get("coverage", "") or "").strip(),
        str(slot.get("move", "") or "").strip(),
    ])


def bullet_list(items: Any) -> str:
    if isinstance(items, list) and items:
        rows = "".join(f"<li>{html.escape(str(x))}</li>" for x in items if str(x).strip())
        if rows:
            return f"<ul>{rows}</ul>"
    if isinstance(items, str) and items.strip():
        return f"<p>{html.escape(items.strip())}</p>"
    return "<p class='muted'>—</p>"


def text_block(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return f"<p>{html.escape(value.strip())}</p>"
    return "<p class='muted'>—</p>"


def render_topic_section(topic: dict[str, Any], registry: dict[str, dict[str, Any]]) -> str:
    topic_name = str(topic.get("name", "") or "").strip() or "Untitled Topic"
    slots = topic.get("slots", [])
    if not isinstance(slots, list):
        slots = []

    card_html = []
    for idx, slot in enumerate(slots, start=1):
        if not isinstance(slot, dict):
            continue

        h = hydrate_slot(slot, registry)
        label = str(h.get("human_label", "") or "").strip() or f"Slot {idx}"
        registry_key = str(h.get("registry_key", "") or "").strip()
        target = h.get("target", "")
        priority = str(h.get("priority", "") or "").strip()
        purpose = h.get("purpose", "")
        card_html.append(
            f"""
            <div class="slot-card">
              <div class="slot-top">
                <div>
                  <h3>{html.escape(label)}</h3>
                  <div class="tiny">{html.escape(canonical_tuple(h))}</div>
                  {f'<div class="tiny">registry_key: {html.escape(registry_key)}</div>' if registry_key else ''}
                </div>
                <div class="slot-meta">
                  <span class="pill">target {html.escape(str(target))}</span>
                  <span class="pill">{html.escape(priority or 'priority n/a')}</span>
                </div>
              </div>

              <div class="grid">
                <div class="cell">
                  <div class="label">Shoot Brief</div>
                  {text_block(h.get("shoot_brief", ""))}
                </div>
                <div class="cell">
                  <div class="label">Purpose</div>
                  {text_block(purpose)}
                </div>
                <div class="cell">
                  <div class="label">Success Criteria</div>
                  {bullet_list(h.get("success_criteria", []))}
                </div>
                <div class="cell">
                  <div class="label">Fallback</div>
                  {bullet_list(h.get("fallback", []))}
                </div>
              </div>
            </div>
            """
        )

    return f"""
    <section class="topic-section">
      <h2>{html.escape(topic_name)}</h2>
      {''.join(card_html) if card_html else '<p class="muted">No valid slots in this topic.</p>'}
    </section>
    """


def build_html(brand_name: str, plan_name: str, topics: list[dict[str, Any]], registry: dict[str, dict[str, Any]], topic_filter: str = "") -> str:
    title = f"{brand_name} · {plan_name}"
    subtitle = f"Topic filter: {topic_filter}" if topic_filter else "Full plan export"

    sections = [render_topic_section(topic, registry) for topic in topics]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)} · Pool Plan Pack</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    margin: 24px;
    color: #111;
    background: #fafafa;
  }}
  .page {{
    max-width: 1080px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 30px;
    margin: 0 0 8px;
  }}
  h2 {{
    font-size: 22px;
    margin: 28px 0 14px;
  }}
  h3 {{
    font-size: 18px;
    margin: 0 0 6px;
  }}
  .muted {{
    color: #666;
  }}
  .tiny {{
    color: #777;
    font-size: 13px;
  }}
  .header {{
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 22px;
  }}
  .topic-section {{
    margin-bottom: 26px;
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
    body {{
      margin: 14px;
    }}
    .grid {{
      grid-template-columns: 1fr;
    }}
    .slot-top {{
      flex-direction: column;
    }}
  }}
</style>
</head>
<body>
  <div class="page">
    <div class="header">
      <h1>{html.escape(title)} · Pool Plan Pack</h1>
      <p class="muted">{html.escape(subtitle)}</p>
    </div>
    {''.join(sections) if sections else '<p class="muted">No matching topics were found.</p>'}
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a brand pool plan into a crew-readable HTML shooting pack."
    )
    parser.add_argument("brand_name", help="Brand display name or slug, e.g. Siglen or _starter")
    parser.add_argument("--plan", default="default", help="Plan name (default: default)")
    parser.add_argument("--topic", default="", help="Optional exact topic name filter")
    parser.add_argument("--out", default="", help="Optional custom output path")
    args = parser.parse_args()

    brand_name = str(args.brand_name or "").strip()
    brand_dir = get_brand_dir(brand_name)
    plan_path = choose_plan(brand_dir, args.plan)
    plan_data = load_yaml(plan_path)
    registry = load_registry_entries()

    if not isinstance(plan_data, dict):
        raise ValueError(f"Plan YAML must be a dictionary: {plan_path}")

    topics = iter_topics(plan_data, args.topic)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    slug = safe_slug(brand_name) or "starter"
    plan_slug = safe_slug(args.plan) or "default"
    topic_slug = safe_slug(args.topic) if args.topic else ""
    out_path = Path(args.out).expanduser().resolve() if args.out else (
        EXPORT_DIR / f"{slug}_{plan_slug}{'_' + topic_slug if topic_slug else ''}_pack.html"
    )

    html_text = build_html(
        brand_name=brand_name,
        plan_name=args.plan,
        topics=topics,
        registry=registry,
        topic_filter=args.topic,
    )
    out_path.write_text(html_text, encoding="utf-8")

    print(f"export_path        : {out_path}")
    print(f"topic_count        : {len(topics)}")
    print(f"topic_filter       : {args.topic or '(none)'}")


if __name__ == "__main__":
    main()
