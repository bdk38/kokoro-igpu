# Grok note 5 — checkpoint after moan fix + WebUI skips

## Where we are

1. **Voices:** real. Sticky blend was Open WebUI model config, not the server.
2. **Moan:** real OV pad artifact. Old trim kept it; v1.1.1 first-quiet trim removes it on probe WAVs. User confirms moan gone, no last-word clip on those files.
3. **New failure:** Open WebUI Read Aloud **skips** interior phrases on a punctuation-heavy paragraph.

## User skip map

Input:

> Well, honestly, I think we should wait; however, the choice is yours. Wait, did you remember the keys, the wallet, and the passport? Peter packed a heavy box of bright blue berries. Seven silver swans swam smoothly south across the sea.

Heard:

- drop after `the wallet,` through `and the passport?`
- drop after `Seven silver swans` through end of last sentence

## My read

Highest-probability bug is **trim false positive on comma pauses**: v1.1.1 cuts at first sustained quiet inside the pad window. List intonation has exactly that shape. That would delete the tail of a chunk without erroring.

WebUI also splits into multiple POSTs and OV RTF is slow; concurrency 500s (`Infer Request is busy`) can contribute, but the wallet comma skip smells like trim.

## Don’t do next

Don’t keep tuning ears only through WebUI. One full-string curl WAV vs multi-segment WebUI capture will separate server trim from client playback.

## Do next

1. Full repro curl → WAV + per-chunk trim debug logs.
2. Trim v1.1.2: cut only if quiet is followed by a weaker secondary burst (true pad moan pattern).
3. Mutex around OV `req.infer`.

Canonical project write-up: `notes/10-status-trim-and-skips.md`.
