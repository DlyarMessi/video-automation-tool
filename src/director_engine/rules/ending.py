# src/director_engine/rules/ending.py

from typing import List, Dict, Any


def _get_tags(shot: Dict[str, Any]) -> List[str]:
    """
    Normalize tags from shot.
    Supported formats:
      - shot["tags"] = ["factory", "hero"]
      - shot["tag"] = "factory"   (single)
      - shot["source"] contains "tags:..." (best-effort fallback)
    """
    tags = []

    t = shot.get("tags")
    if isinstance(t, list):
        tags.extend([str(x).strip() for x in t if str(x).strip()])

    t1 = shot.get("tag")
    if isinstance(t1, str) and t1.strip():
        tags.append(t1.strip())

    # best-effort parse from source spec like "next:tags:factory,hero"
    src = shot.get("source")
    if isinstance(src, str) and "tags:" in src:
        try:
            after = src.split("tags:", 1)[1]
            # stop at whitespace if any
            after = after.split()[0]
            # cut off other prefixes if nested
            for part in after.split(","):
                part = part.strip()
                if part:
                    tags.append(part)
        except Exception:
            pass

    # de-dup while preserving order
    out = []
    seen = set()
    for x in tags:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def apply(shots: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ending rule:
    - Add ending hold (extend last shot duration)
    - Prefer hero/landing style ending if required by profile
    - Forbid random ending (best-effort: if last shot source looks random/next, try pick a better last shot)
    """
    if not shots:
        return shots

    profile = context.get("profile", {})
    ending_cfg = profile.get("ending", {}) or {}
    pacing_cfg = profile.get("pacing", {}) or {}

    ending_hold = pacing_cfg.get("ending_hold", 0.0)
    require_hero = bool(ending_cfg.get("require_hero_tag", False))
    forbid_random_last = bool(ending_cfg.get("forbid_random_last", False))

    directed = [dict(s) for s in shots]

    # ---- 1) Choose a better last shot if required ----
    hero_tags = {"hero", "landing", "brand", "outro"}

    def is_randomish(shot: Dict[str, Any]) -> bool:
        src = str(shot.get("source") or "")
        return src.startswith("random") or "random:" in src or src.startswith("next") or "next:" in src

    def has_hero_tag(shot: Dict[str, Any]) -> bool:
        tags = set(_get_tags(shot))
        return bool(tags & hero_tags)

    if require_hero or forbid_random_last:
        last = directed[-1]
        need_replace = False

        if require_hero and not has_hero_tag(last):
            need_replace = True

        if forbid_random_last and is_randomish(last):
            need_replace = True

        if need_replace:
            # search from the end for a shot that has hero tag and/or is not randomish
            best_idx = None
            for idx in range(len(directed) - 1, -1, -1):
                cand = directed[idx]
                if require_hero and not has_hero_tag(cand):
                    continue
                if forbid_random_last and is_randomish(cand):
                    continue
                best_idx = idx
                break

            # If found, move it to the end (stable editorial “bring to end”)
            if best_idx is not None and best_idx != len(directed) - 1:
                best = directed.pop(best_idx)
                directed.append(best)

    # ---- 2) Add ending hold ----
    if isinstance(ending_hold, (int, float)) and ending_hold > 0:
        last = dict(directed[-1])
        dur = last.get("duration")
        if isinstance(dur, (int, float)):
            last["duration"] = float(dur) + float(ending_hold)
        else:
            # if duration missing, set a sensible default hold
            last["duration"] = float(ending_hold)
        directed[-1] = last

    return directed