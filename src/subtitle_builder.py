# src/subtitle_builder.py
from typing import List, Dict

def build_subtitles_from_vo_events(vo_events) -> List[Dict]:
    """
    ✅ 唯一权威字幕生成器（定版）
    - MIN_GAP 真实生效，避免最后两句太赶/视觉重叠
    - 保证 start < end
    """
    MIN_GAP = 0.25
    segments: List[Dict] = []
    prev_end = None

    for i, ev in enumerate(vo_events, 1):
        start = float(ev.start)
        end = float(ev.start + ev.duration)

        # ✅ 呼吸间隔
        if prev_end is not None and start < prev_end + MIN_GAP:
            start = prev_end + MIN_GAP
            end = start + float(ev.duration)

        # ✅ 防御：至少 0.2s
        if end <= start:
            end = start + 0.2

        text = (ev.subtitle_text or "").strip() or (ev.vo_text or "").strip()
        if text:
            segments.append({
                "index": i,
                "id": f"vo_{i}",
                "source": "",
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "text": text,
                "style": "default",
            })

        prev_end = end

    return segments