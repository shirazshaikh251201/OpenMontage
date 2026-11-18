"""Narration + word-level caption timings.

The key architectural point, and the thing most "auto-caption" tutorials get
wrong for this use case: **the screen recordings are silent.** There is no
speech in them to transcribe. So captions cannot come from the recording.

Instead:

    script line -> Piper TTS -> narration.wav -> Whisper -> word timestamps

We transcribe our *own generated narration*. That gives word-level timings
that are exact against the audio we are actually going to play, which is what
`@remotion/captions` needs to drive karaoke-style captions.

TTS provider is pluggable. Piper runs locally and free, which is what makes
100 videos/month viable; swap in ElevenLabs for hero pieces by setting
TB_TTS=elevenlabs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

PIPER_MODEL = Path.home() / ".piper" / "models" / "en_US-ryan-high.onnx"


def _wav_duration(p: Path) -> float:
    with wave.open(str(p), "rb") as w:
        return w.getnframes() / w.getframerate()


def speak_piper(text: str, out: Path, model: Path = PIPER_MODEL) -> float:
    """Local, free, offline TTS. Returns duration in seconds."""
    if not model.exists():
        raise FileNotFoundError(
            f"Piper voice model missing: {model}\n"
            "  pip install piper-tts\n"
            "  curl -sL -o ~/.piper/models/en_US-ryan-high.onnx "
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx\n"
            "  (and the matching .onnx.json)"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", "-m", "piper", "--model", str(model), "--output-file", str(out)],
        input=text.encode(), check=True, capture_output=True,
    )
    return _wav_duration(out)


def speak_edge(text: str, out: Path, voice: str | None = None, rate: str = "+8%") -> float:
    """Microsoft Edge neural TTS — free, no API key, far more natural than Piper.

    Default voice is Indian English, matching the app's primary market.

    NOTE: edge-tts streams audio over a WebSocket to
    `speech.platform.bing.com`. Behind an HTTPS-inspecting proxy the TLS
    handshake can be fixed (add the proxy CA to certifi's store) but the WSS
    upgrade itself may still be refused, which surfaces as
    `NoAudioReceived`. That is a network-path limitation, not a config error —
    it works on a normal machine. Falls back to Piper so a render never dies
    on it.
    """
    import asyncio

    import edge_tts

    voice = voice or os.environ.get("TB_EDGE_VOICE", "en-IN-PrabhatNeural")
    out.parent.mkdir(parents=True, exist_ok=True)
    mp3 = out.with_suffix(".mp3")

    async def _go() -> None:
        await edge_tts.Communicate(text, voice, rate=rate).save(str(mp3))

    asyncio.run(_go())
    if not mp3.exists() or mp3.stat().st_size == 0:
        raise RuntimeError("edge-tts returned no audio")
    # normalise to wav so the rest of the pipeline sees one format
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-ar", "22050",
                    "-ac", "1", "-y", str(out)], check=True, capture_output=True)
    mp3.unlink(missing_ok=True)
    return _wav_duration(out)


ELEVEN_CACHE = Path.home() / ".cache" / "typebetter-tts"


def _eleven_voice_id(api_key: str, wanted: str) -> str:
    """Accept either a raw voice_id or a human voice name, and resolve it.

    Resolving by name means a concept file can say "Rachel" and keep working
    across accounts, instead of hardcoding an opaque id that may not exist.
    """
    import json as _json
    import urllib.request

    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        voices = _json.load(r)["voices"]
    w = wanted.lower().strip()
    for v in voices:
        if v["voice_id"] == wanted:
            return wanted
    # ElevenLabs names carry descriptor suffixes ("Liam - Energetic, Social
    # Media Creator"), so match the leading name too rather than demanding
    # the whole string.
    for v in voices:
        name = v["name"].lower()
        if name == w or name.split(" - ")[0].strip() == w:
            return v["voice_id"]
    for v in voices:
        if w in v["name"].lower():
            return v["voice_id"]
    names = "\n    ".join(sorted(v["name"] for v in voices))
    raise ValueError(
        f"ElevenLabs voice {wanted!r} is not on this account. Available:\n    {names}")


def speak_elevenlabs(text: str, out: Path, voice: str | None = None) -> float:
    """ElevenLabs TTS — the quality ceiling, and the only provider that costs money.

    Billed per character, so every result is cached by a hash of
    (text, voice, model). Re-rendering the same concept — which happens
    constantly while iterating on captions, music or pacing — then costs
    nothing. Only genuinely new narration is ever charged.

    Deliberately does NOT fall back to Piper. If you asked for the paid voice,
    silently substituting the synthetic one risks publishing a video that
    sounds wrong; failing loudly is the safer error.
    """
    import hashlib
    import json as _json
    import urllib.error
    import urllib.request

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set.\n"
            "  Set it in the environment, then re-run with TB_TTS=elevenlabs.")
    voice = voice or os.environ.get("TB_ELEVEN_VOICE", "Liam")
    # multilingual_v2 is the quality ceiling; turbo_v2_5 is ~half the credits
    # and good enough for volume. Switch with TB_ELEVEN_MODEL.
    model = os.environ.get("TB_ELEVEN_MODEL", "eleven_multilingual_v2")

    out.parent.mkdir(parents=True, exist_ok=True)
    ELEVEN_CACHE.mkdir(parents=True, exist_ok=True)
    stamp = hashlib.sha256(f"{text}|{voice}|{model}".encode()).hexdigest()[:16]
    cached = ELEVEN_CACHE / f"{stamp}.wav"

    if not cached.exists():
        # a 20-char ElevenLabs voice id can be used directly, skipping the
        # voice-list lookup (which is slow and has timed out through the proxy)
        import re as _re
        vid = voice if _re.fullmatch(r"[A-Za-z0-9]{20}", voice or "") else _eleven_voice_id(key, voice)
        body = _json.dumps({
            "text": text,
            "model_id": model,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                               "style": 0.0, "use_speaker_boost": True},
        }).encode()
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
            "?output_format=mp3_44100_128",
            data=body,
            headers={"xi-api-key": key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = r.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise RuntimeError(f"ElevenLabs HTTP {exc.code}: {detail}") from exc
        mp3 = cached.with_suffix(".mp3")
        mp3.write_bytes(audio)
        # normalise to the one format the rest of the pipeline expects
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-ar", "22050",
                        "-ac", "1", "-y", str(cached)], check=True, capture_output=True)
        mp3.unlink(missing_ok=True)

    shutil.copyfile(cached, out)
    return _wav_duration(out)


def speak(text: str, out: Path) -> float:
    """Dispatch on TB_TTS.

    elevenlabs — best quality. Costs credits; cached so reruns are free.
    edge       — free Microsoft neural voices. Needs a WebSocket path out.
    piper      — fully local and offline. Always works. More synthetic.
    """
    provider = os.environ.get("TB_TTS", "piper").lower()
    if provider in ("eleven", "elevenlabs"):
        return speak_elevenlabs(text, out)
    if provider == "edge":
        try:
            return speak_edge(text, out)
        except Exception as exc:  # noqa: BLE001 - any failure should degrade, not stop
            print(f"      edge-tts unavailable ({type(exc).__name__}); using Piper")
            return speak_piper(text, out)
    if provider == "piper":
        return speak_piper(text, out)
    raise ValueError(
        f"TTS provider {provider!r} not wired. Options: elevenlabs, edge, piper.")


def narrate(lines: list[str], workdir: Path) -> list[dict]:
    """One wav per script line, so each line can be pinned to its own beat."""
    workdir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, line in enumerate(lines):
        p = workdir / f"vo_{i:02d}.wav"
        dur = speak(line, p)
        out.append({"index": i, "text": line, "path": str(p), "duration": round(dur, 3)})
    return out


def assemble_vo(segments: list[dict], offsets: list[float], total: float, out: Path) -> Path:
    """Place each narration line at its assigned time on one timeline."""
    inputs, filters, labels = [], [], []
    for i, (seg, off) in enumerate(zip(segments, offsets)):
        inputs += ["-i", seg["path"]]
        ms = int(off * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    graph = ";".join(filters) + ";" + "".join(labels) + \
        f"amix=inputs={len(segments)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total}[out]"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", *inputs, "-filter_complex", graph,
         "-map", "[out]", "-ar", "48000", "-ac", "2", "-y", str(out)],
        check=True, capture_output=True,
    )
    return out


# --------------------------------------------------------------------------
# Word-level captions
# --------------------------------------------------------------------------

def word_timings(audio: Path, offset_s: float = 0.0, model_size: str = "base.en") -> list[dict]:
    """Transcribe with word timestamps -> @remotion/captions `Caption[]` shape.

    faster-whisper (CTranslate2) rather than openai-whisper: 4x quicker on CPU
    for the same model, which matters when this runs per video. whisper.cpp via
    @remotion/install-whisper-cpp is the alternative if you want the toolchain
    entirely inside Node.
    """
    import numpy as np
    from faster_whisper import WhisperModel

    # Decode to 16 kHz mono float32 ourselves and hand Whisper the array.
    # faster-whisper's own loader goes through PyAV, whose `metadata_errors`
    # kwarg was dropped in recent versions — decoding here sidesteps that
    # version coupling entirely.
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio),
         "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    samples = np.frombuffer(pcm, dtype=np.float32)

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(samples, word_timestamps=True, vad_filter=False)

    captions: list[dict] = []
    for seg in segments:
        for w in (seg.words or []):
            captions.append({
                "text": w.word,
                "startMs": round((w.start + offset_s) * 1000),
                "endMs": round((w.end + offset_s) * 1000),
                "timestampMs": round(((w.start + w.end) / 2 + offset_s) * 1000),
                "confidence": round(float(w.probability), 3),
            })
    return captions


def fix_brand(words: list[dict]) -> list[dict]:
    """Whisper hears the app name as "Type, better" / "type better"; caption it right."""
    for i in range(len(words) - 1):
        a, b = words[i]["text"], words[i + 1]["text"]
        if a.strip().rstrip(",").lower() == "type" and b.strip().lower().startswith("better"):
            words[i]["text"] = a.replace(",", "").replace("type", "Type")
            words[i + 1]["text"] = b.replace("better", "Better")
    return words


def captions_for(vo_segments: list[dict], offsets: list[float], workdir: Path) -> list[dict]:
    """Word timings across every narration line, shifted onto the final timeline."""
    all_caps: list[dict] = []
    for n, (seg, off) in enumerate(zip(vo_segments, offsets)):
        # tag each word with its script line so caption pages never straddle
        # two lines (which showed the next sentence's first word early)
        all_caps.extend({**w, "line": n} for w in word_timings(Path(seg["path"]), offset_s=off))
    all_caps.sort(key=lambda c: c["startMs"])
    (workdir / "captions.json").write_text(json.dumps(all_caps, indent=1))
    return all_caps


if __name__ == "__main__":
    import sys

    # `python viral/steps/voice.py voices` -> what's on the ElevenLabs account
    if len(sys.argv) > 1 and sys.argv[1] == "voices":
        import json as _json
        import urllib.request
        _key = os.environ.get("ELEVENLABS_API_KEY")
        if not _key:
            raise SystemExit("ELEVENLABS_API_KEY is not set.")
        _req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": _key})
        with urllib.request.urlopen(_req, timeout=30) as _r:
            for _v in _json.load(_r)["voices"]:
                _lab = _v.get("labels") or {}
                _desc = ", ".join(f"{k}={x}" for k, x in _lab.items()) or "-"
                print(f"{_v['name']:<22} {_v['voice_id']}  {_desc}")
        raise SystemExit(0)

    wd = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vo_test")
    segs = narrate(["This is Type Better. Type it wrong, and one tap fixes it."], wd)
    print(json.dumps(segs, indent=2))
    caps = captions_for(segs, [0.0], wd)
    print(f"{len(caps)} words")
    print(json.dumps(caps[:8], indent=1))
