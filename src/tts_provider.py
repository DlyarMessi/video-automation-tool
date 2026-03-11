from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from tts_azure_302ai import synthesize_wav as azure_synthesize_wav  # 兜底保留


@dataclass
class TTSRequest:
    text: str
    language: str                  # e.g. en-US / fr-FR / es-ES / ru-RU / ar-SA
    provider: str = "azure"        # azure | elevenlabs
    voice: Optional[str] = None    # azure voice name OR elevenlabs voice_id
    model: Optional[str] = None    # elevenlabs model_id
    output_format: str = "mp3_44100_128"
    voice_settings: Optional[Dict[str, Any]] = None


def _lang_short(lang: str) -> str:
    return (lang or "").split("-", 1)[0].lower().strip()


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    h.update("\n".join(parts).encode("utf-8"))
    return h.hexdigest()[:16]


def _load_eleven_profile() -> Dict[str, Any]:
    """
    Optional config file:
      data/tts_profiles/elevenlabs.json

    If missing, we fallback to env mapping:
      ELEVENLABS_VOICE_ID_EN / _FR / _ES / _RU / _AR ...
    """
    p = Path("data/tts_profiles/elevenlabs.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def synthesize(req: TTSRequest, cache_dir: Path, timeout: int = 90) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    provider = (req.provider or "azure").lower().strip()

    if provider == "azure":
        # Azure(302.ai) 输出 WAV，已有成熟缓存逻辑
        voice = req.voice or "en-US-AndrewMultilingualNeural"
        return azure_synthesize_wav(req.text, req.language, voice, cache_dir, timeout=timeout)

    if provider == "elevenlabs":
        return _elevenlabs_synthesize(req, cache_dir, timeout=timeout)

    raise ValueError(f"Unknown provider: {provider}")


def _elevenlabs_synthesize(req: TTSRequest, cache_dir: Path, timeout: int = 90) -> Path:
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("缺少环境变量 ELEVENLABS_API_KEY")

    lang = _lang_short(req.language)

    # === DEBUG: 强制只从环境变量取 ElevenLabs voice_id ===
    env_voice = (os.environ.get(f"ELEVENLABS_VOICE_ID_{lang.upper()}") or "").strip()
    print("[DEBUG] ELEVENLABS_VOICE_ID_ENV =", env_voice)

    if not env_voice or env_voice.upper().startswith("PUT_"):
        raise RuntimeError(
            f"Missing/invalid env ELEVENLABS_VOICE_ID_{lang.upper()} "
            f"(must be a real ElevenLabs voice_id, not placeholder)"
        )

    voice_id = env_voice

    # 下面这些保留：用 config 取默认 model / output_format / voice_settings（不影响 voice_id）
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

    # ✅ 不吃系统 SOCKS 代理
    session = requests.Session()
    session.trust_env = False

    resp = session.post(
        url,
        headers=headers,
        json=payload,
        params={"output_format": output_format},
        timeout=timeout
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")

    out.write_bytes(resp.content)
    return out