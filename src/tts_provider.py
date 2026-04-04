from __future__ import annotations

import hashlib
import json
import os
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from src.tts_local_settings import MMS_MODEL_MAP


@dataclass
class TTSRequest:
    text: str
    language: str                  # e.g. en-US / fr-FR / es-ES / ru-RU / ar-SA
    provider: str = "elevenlabs"
    voice: Optional[str] = None
    model: Optional[str] = None
    output_format: str = "mp3_44100_128"
    voice_settings: Optional[Dict[str, Any]] = None


def _lang_short(lang: str) -> str:
    return (lang or "").split("-", 1)[0].lower().strip()


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    h.update("\n".join(parts).encode("utf-8"))
    return h.hexdigest()[:16]


def _load_eleven_profile() -> Dict[str, Any]:
    p = Path("data/tts_profiles/elevenlabs.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def synthesize(req: TTSRequest, cache_dir: Path, timeout: int = 90) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    provider = (req.provider or "elevenlabs").lower().strip()

    if provider == "elevenlabs":
        return _elevenlabs_synthesize(req, cache_dir, timeout=timeout)

    if provider == "mms_local":
        return _mms_local_synthesize(req, cache_dir)

    if provider == "human_voice_wip":
        raise RuntimeError(
            "Uyghur currently uses the human voice path and is not available in automated TTS yet."
        )

    raise ValueError(f"Unsupported TTS provider: {provider}")


def _elevenlabs_synthesize(req: TTSRequest, cache_dir: Path, timeout: int = 90) -> Path:
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing environment variable ELEVENLABS_API_KEY")

    lang = _lang_short(req.language)

    env_voice = (os.environ.get(f"ELEVENLABS_VOICE_ID_{lang.upper()}") or "").strip()
    print("[DEBUG] ELEVENLABS_VOICE_ID_ENV =", env_voice)

    if not env_voice or env_voice.upper().startswith("PUT_"):
        raise RuntimeError(
            f"Missing/invalid env ELEVENLABS_VOICE_ID_{lang.upper()} "
            f"(must be a real ElevenLabs voice_id, not placeholder)"
        )

    voice_id = env_voice

    prof = _load_eleven_profile()
    defaults = prof.get("defaults", {}) if isinstance(prof.get("defaults"), dict) else {}

    model_id = req.model or defaults.get("model_id") or "eleven_multilingual_v2"
    output_format = req.output_format or defaults.get("output_format") or "mp3_44100_128"

    voice_settings = req.voice_settings or defaults.get("voice_settings") or {
        "stability": 0.5,
        "similarity_boost": 0.75,
    }

    key = _hash_key(lang, voice_id, model_id, output_format, req.text)
    out = cache_dir / f"vo_eleven_{lang}_{voice_id}_{key}.mp3"
    if out.exists() and out.stat().st_size > 2048:
        return out

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    payload = {
        "text": req.text,
        "model_id": model_id,
        "voice_settings": voice_settings,
    }

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    session = requests.Session()
    session.trust_env = False

    resp = session.post(
        url,
        headers=headers,
        json=payload,
        params={"output_format": output_format},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")

    out.write_bytes(resp.content)
    return out


def _sanitize_mms_text(text: str, lang: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise RuntimeError("TTS text is empty")

    short = _lang_short(lang)

    if short == "uz":
        latin_like = re.search(r"[A-Za-z]", cleaned) is not None
        if latin_like:
            raise RuntimeError(
                "MMS Uzbek currently expects Cyrillic Uzbek input. Current text looks Latin-script."
            )

    return cleaned


def _write_wave_file(path: Path, audio, sample_rate: int) -> Path:
    import numpy as np

    arr = np.asarray(audio)
    if arr.ndim > 1:
        arr = arr.squeeze()

    arr = arr.astype("float32")
    arr = arr.clip(-1.0, 1.0)
    pcm = (arr * 32767.0).astype("int16")

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())

    return path


def _mms_local_synthesize(req: TTSRequest, cache_dir: Path) -> Path:
    lang = _lang_short(req.language)
    model_id = MMS_MODEL_MAP.get(lang)
    if not model_id:
        raise RuntimeError(f"No MMS local model mapping configured for language: {req.language}")

    text = _sanitize_mms_text(req.text, req.language)
    key = _hash_key(lang, model_id, text)
    out = cache_dir / f"vo_mms_{lang}_{key}.wav"
    if out.exists() and out.stat().st_size > 2048:
        return out

    try:
        import torch
        from transformers import VitsModel, AutoTokenizer
    except Exception as e:
        raise RuntimeError(
            "MMS local provider requires transformers + torch. "
            "Install them in the project venv first."
        ) from e

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = VitsModel.from_pretrained(model_id)

    inputs = tokenizer(text=text, return_tensors="pt")

    with torch.no_grad():
        output = model(**inputs).waveform

    waveform = output[0].cpu().numpy()
    sample_rate = int(getattr(model.config, "sampling_rate", 16000) or 16000)

    _write_wave_file(out, waveform, sample_rate)
    return out
