# Open WebUI Response Splitting vs Kokoro skips

Date: 2026-08-04  
Server: v1.1.5 ov-gpu (trim closed PASS)  
Trigger: user Read Aloud of multi-sentence passage

## User observation

Text (approx):

> Seven silver swans swam smoothly south across the sea. Well, honestly, I think we should wait; however, the choice is yours. Wait, did you remember the keys, the wallet, and the passport? Peter packed a heavy box of bright blue berries. I think we can call this good. Full stop.

| Admin → Settings → Audio → Response Splitting | Result |
|-----------------------------------------------|--------|
| **Punctuation** (default) | Stopped just before “passport” |
| **None** | Complete, no pad moan |
| **Paragraphs** | Complete, no pad moan |

## What Response Splitting is (Open WebUI docs)

Open WebUI can split long assistant text into chunks **before** calling the TTS engine:

- **Punctuation** (default): split at sentence boundaries — `.` `!` `?` and newlines. Many small TTS requests; aims to start audio sooner.
- **Paragraphs**: split only on double newlines. Fewer, longer chunks.
- **None**: entire response as one TTS request. May delay start of audio on long text.

This is a **client/Open WebUI** behavior, not Kokoro sentence packing.

## Server-side evidence (this session, from Docker 172.22.0.3)

After the probe matrix, WebUI traffic shows:

1. Short multi-POST pattern (matches Punctuation-style sentence chunks), e.g.:
   - tokens=59 audio=4.13s rtf=0.89 (cached-ish / short)
   - tokens=84 audio=5.19s rtf=5.28
   - tokens=12 audio=1.19s rtf=17.98  ← tiny fragment
2. Later single large POSTs (matches None / Paragraphs on this one-block text):
   - tokens=293 audio=19.69s rtf=5.09  (~100 s wall)
   - tokens=306 audio=20.71s rtf=4.58  (~95 s wall)

All returned **HTTP 200**. No trim moan failures on those large jobs (stripped=1 on trailing pad only). So the “stopped before passport” failure is **not** v1.1.5 cutting speech mid-word on a full-string request.

## Why Punctuation breaks under ov-gpu; None/Paragraphs work

### Punctuation → many serial slow requests

With ov-gpu RTF ~4–6× (and lock serializing concurrent infers):

- WebUI fires one `/v1/audio/speech` per sentence (and sometimes smaller fragments).
- Each chunk waits ~5× realtime before audio bytes return.
- Playback is a pipeline of segments. If the UI starts playing early segments while later ones are still generating, **slow tail segments arrive late**.
- Symptom matches history and this run: skip/stop mid-passage (here: around wallet/passport sentence), even though each individual POST may 200.

Also seen: a **tokens=12** micropost (1.19 s audio, rtf 18). Punctuation split can create awkward fragments (dialogue, abbreviations, “Full stop.”, etc.), which adds more round-trips and odd prosody boundaries.

OV lock removed `Infer Request is busy` 500s but **queues** work — under multi-POST that makes the *last* sentences even later, which can worsen client-side drop/skip if the player does not wait forever.

### None → one request

- Entire passage in one body (here ~293–306 tokens → bucket 384).
- One compile/infer, one WAV, trim once at end.
- Wall clock ~95–100 s before audio is ready, but **no mid-pipeline segment loss**.
- Matches user: complete speech, no moan (trim v1.1.5).

### Paragraphs → same as None for this text

User’s paste is a **single paragraph** (single newlines / spaces between sentences, not blank-line paragraph breaks). So Paragraphs mode does **not** split it — one TTS call, same as None. That is why Paragraphs and None sounded the same.

If the assistant had used blank lines between sentences, Paragraphs would emit multiple medium chunks (middle ground: fewer POSTs than Punctuation, still more than None).

## Difference summary

| Mode | # TTS calls (this text) | Failure mode under RTF≫1 | Moan risk |
|------|-------------------------|---------------------------|-----------|
| Punctuation | many (1 per sentence/fragment) | client playback / late segments → **skips** | low per chunk if trim OK |
| Paragraphs | 1 if no blank lines; else few | usually OK here | low |
| None | 1 | long wait then full audio | low with v1.1.5 |

**Trim is not the differentiator.** Splitting policy + slow GPU backend is.

## Practical guidance

For **ov-gpu demo / offload** (RTF 4–6):
- Prefer **Response Splitting = None** or **Paragraphs** (if replies are single blocks).
- Expect long time-to-first-audio on long replies with None.

For **daily snappy Read Aloud**:
- Prefer **ort-cpu** backend (RTF ~0.4) with Punctuation — streaming sentence audio actually helps.
- Or keep ov-gpu but accept None/Paragraphs and latency.

Optional WebUI-side future work (not done): queue/playback that never drops a segment; larger client timeout; disable split when upstream RTF headers show ≫1.

## Relation to earlier skip hypothesis

notes/10 and notes/13 suspected WebUI multi-POST + RTF≫1 after server trim was fixed. This A/B **confirms** it: same server build, only WebUI split mode changed; None/Paragraphs PASS, Punctuation FAIL.

## Artifacts / logs

- `logs/server_v115.log` — WebUI lines from `172.22.0.3`
- Server still v1.1.5 ov-gpu on `:8880`
