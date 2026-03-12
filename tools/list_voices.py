import os
import requests

api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
if not api_key:
    raise RuntimeError("Missing ELEVENLABS_API_KEY")

session = requests.Session()
session.trust_env = False  # ✅ 忽略 SOCKS / HTTP 代理（你机器上是 socks5h）

resp = session.get(
    "https://api.elevenlabs.io/v1/voices",
    headers={"xi-api-key": api_key},
    timeout=30
)
resp.raise_for_status()

voices = resp.json().get("voices", [])
print("Total voices:", len(voices))
for v in voices:
    print(v.get("name"), "=>", v.get("voice_id"))