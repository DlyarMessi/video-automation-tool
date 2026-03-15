#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intake_models import NormalizedIntakeBrief
from src.script_pipeline import build_default_compiler_bundle, response_to_dict, run_script_pipeline
from src.script_provider_gemini import GeminiScriptProvider
from src.script_provider_manual import ManualScriptProvider


def load_brief(path: Path) -> NormalizedIntakeBrief:
    if not path.exists():
        raise FileNotFoundError(f"Intake file not found: {path}")

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        text = path.read_text(encoding="utf-8")
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(text)
        except Exception:
            data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError("Intake file must contain an object/mapping")

    return NormalizedIntakeBrief(**data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the script intake -> compile -> provider pipeline.")
    parser.add_argument("--intake", required=True, help="Path to normalized intake YAML/JSON file")
    parser.add_argument("--provider", default="manual", choices=["manual", "gemini"], help="Provider mode")
    parser.add_argument("--manual-response", default="", help="Optional local YAML/JSON for manual provider")
    parser.add_argument("--gemini-api-key", default="", help="Gemini API key (not used in scaffold)")
    parser.add_argument("--gemini-model", default="gemini-1.5-pro", help="Gemini model name")
    parser.add_argument("--out", default="", help="Optional output JSON file path")
    args = parser.parse_args()

    brief = load_brief(Path(args.intake))
    bundle = build_default_compiler_bundle(ROOT)

    if args.provider == "manual":
        provider = ManualScriptProvider(Path(args.manual_response) if args.manual_response else None)
    else:
        provider = GeminiScriptProvider(api_key=args.gemini_api_key, model=args.gemini_model)

    result = run_script_pipeline(brief=brief, provider=provider, bundle=bundle)
    payload = response_to_dict(result)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote: {out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
