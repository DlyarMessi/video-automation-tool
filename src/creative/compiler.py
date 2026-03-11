from __future__ import annotations

from typing import Any, Dict, List, Optional


class CreativeCompiler:
    """
    Creative Script -> Production Script (structural translation only)

    - Deterministic, tag-based source selection: next:tags:a,b,c
    - Comfortable sequencing inside each beat/block
    - VO is written into timeline shots (drives voiceover + subtitles)
    """

    def compile(self, creative: Dict[str, Any]) -> Dict[str, Any]:
        self._validate_creative(creative)
        project = self._compile_project(creative)
        timeline = self._compile_timeline(creative)
        return {"project": project, "timeline": timeline}

    # ---------------- validation ----------------
    def _validate_creative(self, creative: Dict[str, Any]) -> None:
        if not isinstance(creative, dict):
            raise ValueError("Creative Script must be a dict")
        for f in ("meta", "tone", "beats"):
            if f not in creative:
                raise ValueError(f"Creative Script missing required field: {f}")
        if not isinstance(creative.get("meta"), dict):
            raise ValueError("Creative Script 'meta' must be a dict")
        if not isinstance(creative.get("tone"), dict):
            raise ValueError("Creative Script 'tone' must be a dict")
        if not isinstance(creative.get("beats"), list):
            raise ValueError("Creative Script 'beats' must be a list")

    # ---------------- project ----------------
    def _compile_project(self, creative: Dict[str, Any]) -> Dict[str, Any]:
        meta = creative.get("meta", {}) or {}
        tone = creative.get("tone", {}) or {}

        director_profile = tone.get("profile", "content_factory")
        filename = meta.get("output_name") or meta.get("output_filename") or "output.mp4"

        output: Dict[str, Any] = {
            "filename": filename,
            "format": meta.get("format", "portrait_1080x1920"),
            "fit": meta.get("fit", "cover"),
            # ✅ default burn subtitles ON for "win condition"
            "burn_subtitles": meta.get("burn_subtitles", True),
        }

        project: Dict[str, Any] = {
            "director_profile": director_profile,
            "output": output,
        }

        # passthrough audio config if present (meta.audio.voiceover)
        if isinstance(meta.get("audio"), dict):
            project["audio"] = meta["audio"]

        return project

    # ---------------- timeline ----------------
    def _compile_timeline(self, creative: Dict[str, Any]) -> List[Dict[str, Any]]:
        meta = creative.get("meta", {}) or {}
        beats = creative.get("beats", []) or []

        target_len = meta.get("target_length")
        if not isinstance(target_len, (int, float)) or target_len <= 0:
            target_len = 20.0

        seq: List[Dict[str, Any]] = []

        for beat in beats:
            if not isinstance(beat, dict):
                continue

            purpose_raw = str(beat.get("purpose") or "").strip()
            purpose = self._normalize_purpose(purpose_raw)

            subtitle = str(beat.get("subtitle") or "").strip()
            vo_text = str(beat.get("vo") or "").strip()
            visual = str(beat.get("visual") or "").strip()
            scene = beat.get("scene") or self._infer_scene(visual) or "factory"

            if purpose == "establish_context":
                # context: wide -> detail
                seq.extend(
                    [
                        self._shot(scene, "line", "wide", "static", 3.0, subtitle, tag="context_wide", vo=vo_text),
                        self._shot(scene, "line", "detail", "static", 2.0, subtitle, tag="context_detail"),
                    ]
                )

            elif purpose == "show_capability":
                # capability(automation): wide -> detail -> medium
                seq.extend(
                    [
                        self._shot(scene, "automation", "wide", "slide", 3.0, subtitle, tag="automation_wide", vo=vo_text),
                        self._shot(scene, "automation", "detail", "static", 1.8, subtitle, tag="automation_detail"),
                        self._shot(scene, "automation", "medium", "pushin", 2.7, subtitle, tag="automation_medium"),
                    ]
                )

            elif purpose == "build_trust":
                # trust(testing): detail -> medium
                seq.extend(
                    [
                        self._shot(scene, "testing", "detail", "static", 2.2, subtitle, tag="testing_detail", vo=vo_text),
                        self._shot(scene, "testing", "medium", "static", 2.8, subtitle, tag="testing_medium"),
                    ]
                )

            elif purpose == "brand_close":
                close_sub = subtitle if subtitle else "SIGLEN"
                extra_moves = beat.get("move")
                move = str(extra_moves).strip() if isinstance(extra_moves, str) and extra_moves.strip() else "orbit"
                seq.append(self._shot(scene, "building", "hero", move, 4.5, close_sub, tag="hero", vo=vo_text))

            else:
                shot = self._compile_fallback_shot(beat, default_scene=scene)
                if shot is not None:
                    seq.append(shot)

        # normalize total length (gentle)
        total = sum(float(s.get("duration") or 0.0) for s in seq)
        if total > 0:
            scale = float(target_len) / float(total)
            scale = max(0.85, min(1.15, scale))
            for s in seq:
                if isinstance(s.get("duration"), (int, float)):
                    s["duration"] = round(float(s["duration"]) * scale, 2)

        cleaned: List[Dict[str, Any]] = []
        for s in seq:
            cleaned.append({k: v for k, v in s.items() if v is not None})
        return cleaned

    # ---------------- helpers ----------------
    def _normalize_purpose(self, purpose: str) -> str:
        p = (purpose or "").strip().lower()

        # direct canonical matches
        if p in {"establish_context", "show_capability", "build_trust", "brand_close"}:
            return p

        # common aliases from your scripts
        if "establish" in p or "capability" in p:
            return "establish_context"
        if "automation" in p or "show" in p:
            return "show_capability"
        if "quality" in p or "assurance" in p or "testing" in p or "qc" in p:
            return "build_trust"
        if "brand" in p or "close" in p or "hero" in p:
            return "brand_close"

        return "establish_context"

    def _shot(
        self,
        scene: str,
        content: str,
        coverage: str,
        move: str,
        duration: float,
        subtitle: str,
        tag: str,
        vo: Optional[str] = None,
    ) -> Dict[str, Any]:
        tags = [scene, content, coverage]
        if move:
            tags.append(move)

        out: Dict[str, Any] = {
            "source": "next:tags:" + ",".join(tags),
            "duration": float(duration),
            "subtitle": subtitle if subtitle else None,
            "tag": tag,
        }

        if isinstance(vo, str) and vo.strip():
            out["vo"] = vo.strip()

        return out

    def _compile_fallback_shot(self, beat: Dict[str, Any], default_scene: str) -> Optional[Dict[str, Any]]:
        vo = beat.get("vo")
        vo_clean = str(vo).strip() if isinstance(vo, str) else ""
        subtitle = str(beat.get("subtitle") or "").strip()

        # Explicit source has priority
        source = beat.get("source") or beat.get("source_hint")
        if isinstance(source, str) and source.strip():
            out: Dict[str, Any] = {"source": source.strip()}
            dur = beat.get("duration_hint")
            if isinstance(dur, (int, float)):
                out["duration"] = float(dur)
            if subtitle:
                out["subtitle"] = subtitle
            if vo_clean:
                out["vo"] = vo_clean
            out["tag"] = str(beat.get("purpose") or "beat")
            return out

        # Explicit tags(list) -> next:tags:...
        tags = beat.get("tags")
        if isinstance(tags, list) and tags:
            tag_str = ",".join([str(t).strip() for t in tags if str(t).strip()])
            out: Dict[str, Any] = {"source": f"next:tags:{tag_str}" if tag_str else "next:tags:generic"}
            dur = beat.get("duration_hint")
            if isinstance(dur, (int, float)):
                out["duration"] = float(dur)
            if subtitle:
                out["subtitle"] = subtitle
            if vo_clean:
                out["vo"] = vo_clean
            out["tag"] = str(beat.get("purpose") or "beat")
            return out

        # Last resort: safe generic with notes
        visual = str(beat.get("visual") or "").strip()
        dur = beat.get("duration_hint")
        out = {
            "source": f"next:tags:{default_scene},generic",
            "notes": visual if visual else None,
            "duration": float(dur) if isinstance(dur, (int, float)) else 3.0,
            "subtitle": subtitle or None,
            "vo": vo_clean or None,
            "tag": str(beat.get("purpose") or "beat"),
        }
        return out

    def _infer_scene(self, visual: str) -> str:
        v = (visual or "").lower()
        if "showroom" in v:
            return "showroom"
        if "villa" in v:
            return "villa"
        if "factory" in v:
            return "factory"
        return ""