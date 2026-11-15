# Handoff — TypeBetter viral video system

Written 15 Nov 2026, at the point where the system is built and waiting on
footage. Read this plus [`README.md`](README.md) and you have the full picture.

## What exists

A working pipeline that turns one raw iPhone screen recording into a
publishable vertical video with no manual editing:

```bash
TB_TTS=elevenlabs ELEVENLABS_API_KEY=proxy-injected \
  python viral/pipeline.py --recording raw/clip.mov --concept mistake-reveal
```

Six concepts live in `viral/concepts/`. One recording run against all six
gives six genuinely different videos — the hook, script, captions, pacing and
music style all change.

`README.md` covers the architecture and the craft decisions. `STACK.md`
covers what is installed and what was tested and rejected.

## State as of this handoff

| Thing | Status |
|---|---|
| Beat detection, conform, captions, sound, render | Working end to end |
| ElevenLabs narration | **Working.** Default voice `Liam`. Cached, so re-renders cost nothing |
| Six concept files | Written, updated for iOS theme and the 2,000-word offer |
| Recording script | `RECORDING-SCRIPT.md`, corrected after on-device testing |
| **Five recordings** | **Shot by the user, not yet delivered into a session** |
| Music | Synthesised bed by default. Drop an `.mp3` in `music_library/` to override |
| App icon | Reconstructed from the App Store listing; the original would be better |

## The immediate next step

The user has **five clips already recorded**. Get them into the session
(a Google Drive link has worked before; direct upload failed on file size),
then run every concept against them:

```bash
for c in viral/concepts/*.json; do
  TB_TTS=elevenlabs ELEVENLABS_API_KEY=proxy-injected \
    python viral/pipeline.py --recording raw/clip.mov --concept "$c"
done
```

That first batch is an **experiment, not a deliverable**: six different hooks
against one product. The useful output is which hook holds attention past
three seconds. Once one wins, clone it and retire the rest.

## Things that will bite you

**The recordings are silent.** Screen captures have no audio (−91 dB). So
captions cannot come from the footage. The pipeline generates narration with
TTS, then transcribes *its own generated audio* for word timings. Nearly every
auto-caption tutorial assumes otherwise and breaks here.

**ElevenLabs key is a network secret, not a variable.** It is saved on the
environment and injected by the proxy into requests to `api.elevenlabs.io`.
Nothing holds the value. Because of that `ELEVENLABS_API_KEY` must still be
set to the placeholder `proxy-injected` so the provider's own guard passes.
A new session in the same environment inherits the secret.

**Crop full-width only.** `crop=1170:2080:0:452,scale=1080:1920`. Horizontal
crops clip phone UI text — 936px clipped the tone-grid column, 820px turned
"Heard Hinglish" into "ard Hinglish".

**No blue anywhere.** The iOS app is black, white and warm off-white. Its only
colours are correction green `#21C165` and error red `#A04641`. An earlier
version used `#2B59FF` sampled from the website's *Android* card — wrong
product, and the user rejected it twice. Do not reintroduce it.

**Expand has a minimum input length.** `ok` returns "Not enough to rewrite".
Keep Expand inputs to roughly four words or more.

**edge-tts does not work in the sandbox.** Its WebSocket upgrade is refused by
the proxy. ElevenLabs' REST path works fine. Piper is the offline fallback.

## User preferences, learned the hard way

- No Hindi sentences. English only. This was rejected explicitly and strongly.
- Show the product being *used* — type a wrong sentence, tap, watch it get
  fixed. Not abstract feature montages. Rejected three videos before this
  landed.
- iPhone only. No Google Play or Android reference in any frame.
- The offer is **2,000 AI words**, not 5,000.
