from pathlib import Path
import os

from script_loader import load_script
from voiceover_a2 import extract_vo_events  # 继续用你现有的 VO event 提取
from tts_provider import synthesize, TTSRequest  # 走统一 provider 入口（azure/elevenlabs 都可）


SCRIPT = Path(os.environ.get("VO_SCRIPT", "scripts/siglen_promo.yaml")).expanduser().resolve()
OUT_CACHE = Path(os.environ.get("VO_CACHE_DIR", "output_videos/Siglen/test_run_v1/cache_tts")).expanduser().resolve()
TTS_PROVIDER = (os.environ.get("TTS_PROVIDER", "azure") or "azure").strip().lower()

dsl = load_script(SCRIPT)
project = dsl.get("project", {})
shots = dsl.get("timeline", [])

audio_cfg = project.get("audio", {}) if isinstance(project.get("audio", {}), dict) else {}
vo_cfg = audio_cfg.get("voiceover", {}) if isinstance(audio_cfg.get("voiceover", {}), dict) else {}

lang = vo_cfg.get("language", "en-US")
voice = vo_cfg.get("voice")  # azure voice name 或 eleven voice_id（如果你想脚本覆盖）
vol = float(vo_cfg.get("volume", 1.0))

events = extract_vo_events(shots, lang, voice, vol)
print("VO events:", len(events))

OUT_CACHE.mkdir(parents=True, exist_ok=True)

for e in events:
    # ✅ 兼容不同 VOEvent 字段名：text/caption/content
    # ✅ 兼容不同 VOEvent 结构，优先用 vo_text（你的 VOEvent 就是这个字段）
    vo_text = None
    for attr in ("vo_text", "text", "caption", "subtitle_text", "content"):
        if hasattr(e, attr):
            v = getattr(e, attr)
            if isinstance(v, str) and v.strip():
                vo_text = v.strip()
                break

    if not vo_text:
        raise RuntimeError(f"VOEvent 没有可用文案字段: {e}")
    if not vo_text:
        raise RuntimeError(f"VOEvent 没有可用文案字段: {e}")

    print("TTS:", getattr(e, "start", 0.0), vo_text[:60])

    event_voice = getattr(e, "voice", None) or voice

    # ✅ 如果是 elevenlabs，不要把 Azure voice name 传过去
    if TTS_PROVIDER == "elevenlabs":
        event_voice = None

    req = TTSRequest(
        text=vo_text,
        language=getattr(e, "language", lang),
        provider=TTS_PROVIDER,
        voice=event_voice,
        model=getattr(e, "model", None),
    )
    synthesize(req, OUT_CACHE)

print("Done. Cache at:", OUT_CACHE)