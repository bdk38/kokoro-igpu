#!/usr/bin/env python3
"""Fire concurrent speech requests; expect 200s and no Infer Request is busy."""
import concurrent.futures as cf
import json
import time
import urllib.request

URL = "http://127.0.0.1:8880/v1/audio/speech"
TEXT = "The quick brown fox jumps over the lazy dog."

def one(i):
    body = json.dumps({
        "model": "kokoro",
        "input": TEXT,
        "voice": "af_bella",
        "response_format": "wav",
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
            rtf = resp.headers.get("X-Kokoro-RTF")
            return {"i": i, "ok": True, "code": resp.status, "n": len(data), "rtf": rtf, "s": round(time.time()-t0, 2)}
    except Exception as e:
        return {"i": i, "ok": False, "err": str(e), "s": round(time.time()-t0, 2)}

n = 4
t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=n) as ex:
    rows = list(ex.map(one, range(n)))
print(json.dumps({"wall_s": round(time.time()-t0, 2), "results": rows}, indent=2))
print("all_ok", all(r.get("ok") for r in rows))
