# src/tts_azure_302ai.py
from __future__ import annotations

import base64
import hashlib
import html
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

import requests


def _hash(text: str, language: str, voice: str) -> str:
    h = hashlib.sha256()
    h.update((language + "\n" + voice + "\n" + text).encode("utf-8"))
    return h.hexdigest()[:16]


def _xml_escape(s: str) -> str:
    return html.escape(s or "", quote=False)


def _read_env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def _session_clean() -> requests.Session:
    """
    requests Session：不读取环境代理（ALL_PROXY/HTTP_PROXY/HTTPS_PROXY），避免 pip/环境污染。
    但我们允许在本 Session 上显式设置“仅 TTS 使用的代理”。
    """
    s = requests.Session()
    s.trust_env = False
    return s


def _maybe_set_tts_proxy(session: requests.Session) -> None:
    """
    仅用于 TTS 的代理配置（可选）：
    - 若设置了 TTS_HTTP_PROXY，则所有 TTS 请求走该代理（HTTP CONNECT），无需 PySocks。
    例：export TTS_HTTP_PROXY="http://127.0.0.1:8001"
    """
    p = _read_env("TTS_HTTP_PROXY")
    if p:
        session.proxies = {"http": p, "https": p}


def synthesize_wav(
    text: str,
    language: str,
    voice: str,
    cache_dir: Path,
    timeout: int = 90,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"vo_{language}_{voice}_{_hash(text, language, voice)}.wav"
    if out.exists() and out.stat().st_size > 1024:
        return out

    api_key = _read_env("AI302_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 AI302_API_KEY")

    # 固定到 AzureTTS API endpoint
    url = _read_env("AI302_AZURE_TTS_URL", "https://api.302.ai/cognitiveservices/v1")

    ssml = f"""<speak version="1.0"
  xmlns="http://www.w3.org/2001/10/synthesis"
  xmlns:mstts="http://www.w3.org/2001/mstts"
  xml:lang="{language}">
  <voice name="{voice}">
    {_xml_escape(text)}
  </voice>
</speak>"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/ssml+xml",
        "Accept": "application/json",
        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
        "User-Agent": "video-automation-tool",
        "Connection": "close",
    }

    def parse_json_safe(resp: requests.Response) -> Optional[Dict[str, Any]]:
        try:
            return resp.json()
        except Exception:
            return None

    session = _session_clean()
    _maybe_set_tts_proxy(session)

    max_retries = 6
    base_sleep = 0.8
    last_err: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.post(
                url,
                headers=headers,
                data=ssml.encode("utf-8"),
                timeout=timeout,
                allow_redirects=False,  # ✅ 禁止默默跳转到网页（HTML）
            )

            # ✅ 如果发生重定向，直接报出 Location，别让它落到 Next.js 网页
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location", "")
                raise RuntimeError(f"TTS got redirect HTTP {resp.status_code} -> {loc}")

            # 417：Expectation Failed（通常是链路/代理层对 Expect 类行为不兼容）
            if resp.status_code == 417:
                data = parse_json_safe(resp)
                last_err = RuntimeError(f"TTS HTTP 417 (attempt {attempt}): {data or resp.text[:200]}")
                time.sleep(min(base_sleep * (2 ** (attempt - 1)), 10.0))
                continue

            # 503：可能是临时不可用，也可能 body 带 -10011
            if resp.status_code == 503:
                data = parse_json_safe(resp)
                if isinstance(data, dict) and "error" in data and data["error"].get("err_code") == -10011:
                    raise RuntimeError(f"TTS Invalid request (-10011): {data}")
                last_err = RuntimeError(f"TTS HTTP 503 (attempt {attempt}): {data or resp.text[:200]}")
                time.sleep(min(base_sleep * (2 ** (attempt - 1)), 10.0))
                continue

            if resp.status_code >= 400:
                data = parse_json_safe(resp)
                raise RuntimeError(f"TTS HTTP {resp.status_code}: {data or resp.text[:200]}")

            # ✅ 2xx：优先 JSON（常见是 JSON+file）
            ctype = (resp.headers.get("Content-Type") or "").lower()

            # 如果是网页（text/html），说明仍然落到了前端
            if "text/html" in ctype or resp.content.startswith(b"<!DOCTYPE html"):
                raise RuntimeError(f"Unexpected HTML response (check proxy/redirect). head={resp.content[:120]!r}")

            data = parse_json_safe(resp)
            if isinstance(data, dict):
                if "error" in data:
                    raise RuntimeError(f"TTS error: {data['error']}")
                file_field = data.get("file") or data.get("audio") or data.get("data")
                if file_field:
                    if isinstance(file_field, str) and file_field.startswith("http"):
                        rr = session.get(file_field, timeout=timeout, allow_redirects=False)
                        rr.raise_for_status()
                        out.write_bytes(rr.content)
                    elif isinstance(file_field, str) and file_field.startswith("data:"):
                        b64 = file_field.split("base64,", 1)[-1]
                        out.write_bytes(base64.b64decode(b64))
                    elif isinstance(file_field, str):
                        out.write_bytes(base64.b64decode(file_field))
                    else:
                        raise RuntimeError(f"Unsupported file field type: {type(file_field)}")

                    if not out.read_bytes().startswith(b"RIFF"):
                        raise RuntimeError(f"Decoded output is not RIFF WAV, head={out.read_bytes()[:80]!r}")
                    return out

            # ✅ 兜底：少数情况直接返回 RIFF 音频流
            if resp.content.startswith(b"RIFF"):
                out.write_bytes(resp.content)
                return out

            raise RuntimeError(f"Unexpected TTS response, content-type={ctype}, head={resp.content[:200]!r}")

        except Exception as e:
            last_err = e
            # 请求无效直接停止
            if "Invalid request (-10011)" in str(e):
                break
            time.sleep(min(base_sleep * (2 ** (attempt - 1)), 10.0))

    raise RuntimeError(f"TTS failed after retries: {last_err}")