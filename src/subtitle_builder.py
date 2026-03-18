from typing import Dict, List


def build_subtitles_from_vo_events(vo_events, min_gap: float = 0.0) -> List[Dict]:
    """
    Build subtitle segments directly from the corrected VO schedule.
    """
    segments: List[Dict] = []
    prev_end = 0.0
    min_visible = max(float(min_gap or 0.0), 0.2)

    for i, ev in enumerate(vo_events, 1):
        start = max(float(getattr(ev, "start", 0.0) or 0.0), prev_end)
        duration = max(float(getattr(ev, "duration", 0.0) or 0.0), min_visible)
        end = start + duration

        text = (getattr(ev, "subtitle_text", "") or "").strip() or (getattr(ev, "vo_text", "") or "").strip()
        if text:
            segments.append(
                {
                    "index": i,
                    "id": f"vo_{i}",
                    "source": "",
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "duration": round(end - start, 3),
                    "text": text,
                    "style": "default",
                    "note": getattr(ev, "schedule_note", "") or "",
                }
            )

        prev_end = end

    return segments
