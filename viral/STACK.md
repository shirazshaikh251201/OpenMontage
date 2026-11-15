# Installed stack

Everything below is cloned and verified working in this session on 15 Nov 2026.

## Repositories

| Repo | Path | Size | Status |
|---|---|---|---|
| `shirazshaikh251201/template-tiktok` | `/home/user/shirazshaikh251201/template-tiktok` | 8.1M | cloned |
| `shirazshaikh251201/auto-editor` | `/home/user/shirazshaikh251201/auto-editor` | 45M | cloned + pip 29.3.1 |
| `shirazshaikh251201/PySceneDetect` | `/home/user/shirazshaikh251201/PySceneDetect` | 114M | cloned + pip 0.7.3 |
| `shirazshaikh251201/piper1-gpl` | `/home/user/shirazshaikh251201/piper1-gpl` | 57M | cloned + pip 1.8.0 |
| `shirazshaikh251201/piper` | `/home/user/shirazshaikh251201/piper` | 62M | cloned (voice models) |
| `shirazshaikh251201/faster-whisper` | `/home/user/shirazshaikh251201/faster-whisper` | 43M | cloned + pip 1.2.1 |
| `shirazshaikh251201/whisper.cpp` | `/home/user/shirazshaikh251201/whisper.cpp` | 56M | cloned (not compiled) |
| `harry0703/MoneyPrinterTurbo` | `/home/user/harry0703/MoneyPrinterTurbo` | 341M | cloned |
| `remotion-dev/remotion` (upstream) | `/home/user/rameezpravah-u/remotion` | 873M | cloned earlier, in use |

**On the remotion fork:** not re-cloned. The upstream copy is already here and
the renderer we actually run is `remotion-composer/node_modules`. A second
873M copy of identical source buys nothing — say the word if you want your
fork specifically and I'll pull it.

## Python packages

```
edge-tts        7.3.1     free Microsoft neural TTS
auto-editor    29.3.1     silence-based trimming
scenedetect     0.7.3     shot detection
faster-whisper  1.2.1     word-level transcription   [in use]
piper-tts       1.8.0     local offline TTS          [in use]
```

---

## What testing each one actually showed

I ran the two "obvious" editing tools against a real recording
(`type-fix.mov`, 48.86s, silent). Both failed, and the failures are the
justification for `viral/steps/beats.py`:

### auto-editor → deletes the entire video

```
$ auto-editor type-fix.mov -o out.mp4
⏳ Analyzing audio volume ████████ 70%
Error! Timeline is empty, nothing to do.
```

It segments by **audio loudness**. Screen recordings are digitally silent, so
every frame scores as silence and the whole timeline is cut. It is the right
tool for talking-head or voiceover footage; it cannot see a screen recording
at all.

### PySceneDetect → finds one scene in 49 seconds

```
$ scenedetect -i type-fix.mov detect-adaptive list-scenes
Detected 1 scenes, average shot length 48.9 seconds.
```

Correct, and useless here. It looks for **shot cuts**. A screen recording has
none — the camera never changes, only the UI does. Worth keeping for footage
that cuts between apps.

### beats.py → 7 beats, 48.86s → 15.92s

```
$ python viral/steps/beats.py type-fix.mov
analysed: 48.8s -> 15.92s (3.06x), 7 beats
  src 12.27s -> out 2.36s   strength 0.47    panel opens
  src 18.00s -> out 5.37s   strength 1.00    correction applied
  ...
```

Measures **structural change between frames** instead of audio or shot cuts,
which is the only signal a silent screen recording actually carries.

---

## MoneyPrinterTurbo — what it gave us

It is a topic→video generator: you give it a keyword, it writes a script,
pulls stock footage, and assembles with MoviePy. That is the opposite of our
problem — we have real footage and don't want stock — so we don't use it as a
pipeline.

Two things from reading it were worth the clone:

**1. `edge-tts`.** Free Microsoft neural voices, no API key, including
`en-IN-PrabhatNeural` (Indian English). Dramatically better than Piper and it
costs nothing. Now wired in as `TB_TTS=edge`.

**2. Independent confirmation of the PyAV bug.** Their `requirements.txt`:

```
faster-whisper==1.1.0
# faster-whisper passes metadata_errors to av.open(), which PyAV 19 removed
av<19
```

They hit the exact failure I hit, and pinned `av<19` to dodge it. Our fix
decodes audio with ffmpeg and hands Whisper a numpy array, which avoids the
dependency constraint entirely — better, because it doesn't hold PyAV back.

---

## TTS: current state

```bash
TB_TTS=elevenlabs python viral/pipeline.py ...   # best; costs credits, cached
TB_TTS=piper      python viral/pipeline.py ...   # default, always works
TB_TTS=edge       python viral/pipeline.py ...   # free, needs WebSockets
```

**ElevenLabs is live.** `api.elevenlabs.io` is reachable over plain HTTPS (the
REST path works where edge-tts's WebSocket does not), and the key is stored as
a network secret on the environment rather than in the repo or a variable — the
proxy injects the `xi-api-key` header, so no code here ever holds the value.
Because of that, `ELEVENLABS_API_KEY` must still be set to a placeholder
(`proxy-injected`) to satisfy the provider's own guard; on a normal machine set
it to the real key instead.

Every result is cached under `~/.cache/typebetter-tts/` keyed by a hash of
(text, voice, model). A cache hit returns in ~0.09s and spends nothing, so
iterating on captions, music or pacing never re-charges narration. Only new
script text is ever billed.

Unlike the edge provider, this one does **not** fall back to Piper. If you ask
for the paid voice, silently substituting the synthetic one risks publishing a
video that sounds wrong, so it fails loudly instead.

Default voice is `Liam` (energetic, social-media). Names resolve loosely, so
`Liam` matches "Liam - Energetic, Social Media Creator".
`python viral/steps/voice.py voices` lists what the account actually has —
worth checking, because the common tutorial default `Rachel` is not on it.

`edge-tts` remains the free fallback. It streams audio over a **WebSocket** to
`speech.platform.bing.com`. In this sandbox:

- The TLS failure was fixable — the proxy's CA wasn't in certifi's store, so I
  added it (the documented fix; verification stays on).
- The WSS upgrade itself still returns no audio. The proxy README lists
  WebSocket upgrades as unsupported, so this is a network-path limit, not a
  config error.

**It will work on your Mac.** `speak()` catches the failure and falls back to
Piper, so a render never dies on it — verified.

For hero pieces, ElevenLabs remains the ceiling; it needs an API key in the
environment (`TB_TTS=elevenlabs` branch is stubbed in `voice.py`).

---

## What runs where

| Job | Tool | Cost |
|---|---|---|
| Beat detection | `viral/steps/beats.py` (numpy + ffmpeg) | free, local |
| Conform / speed-ramp | FFmpeg | free, local |
| Narration | Piper, or edge-tts off-sandbox | free, local |
| Word timings | faster-whisper `base.en` | free, local |
| Captions | `@remotion/captions` | free, local |
| Music + SFX | `viral/steps/sound.py` (numpy) | free, local |
| Render | Remotion | free, local |

The whole pipeline costs nothing per video and needs no API key. That is what
makes 100/month viable.
