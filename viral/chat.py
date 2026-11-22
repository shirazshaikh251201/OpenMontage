#!/usr/bin/env python3
"""Chat mock-up video: drawn in code, no recording and no generated footage.

    python viral/chat.py --spec grammar-surprise

A spec is a few lines of text: who messages, the bad reply, the tool, the real
corrected text Type Better produces, headlines. The script works out timing
from the text itself (how long it takes to type), marks which words the fix
changes, builds the sound (keystrokes, tap, reveal) and renders the
ChatMock composition.

The `fixed` text must be copied from the real app's output — the ad has to
show what the product actually does.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral import pipeline as pl  # noqa: E402
from viral.steps import sound as sound_mod  # noqa: E402
from viral.steps import voice as voice_mod  # noqa: E402

FPS = 30
CHARS_PER_SEC = 18.0      # brisk but readable typing


def tokens(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text)


def diff_tokens(draft: str, fixed: str) -> tuple[list[dict], list[dict]]:
    """Mark the words the fix changes: red in the draft, green in the result."""
    a, b = tokens(draft), tokens(fixed)
    aw = [(i, t) for i, t in enumerate(a) if not t.isspace()]
    bw = [(i, t) for i, t in enumerate(b) if not t.isspace()]
    hit_a, hit_b = set(), set()
    # a full stop added at the end isn't one of "the mistakes": compare words
    # without trailing punctuation so only real changes get marked
    key = lambda w: w.rstrip(".,!?;:")  # noqa: E731
    sm = difflib.SequenceMatcher(a=[key(t) for _, t in aw], b=[key(t) for _, t in bw], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            hit_a.update(aw[k][0] for k in range(i1, i2))
            hit_b.update(bw[k][0] for k in range(j1, j2))
    return ([{"t": t, "hit": i in hit_a} for i, t in enumerate(a)],
            [{"t": t, "hit": i in hit_b} for i, t in enumerate(b)])


def run(spec_path: Path, out_dir: Path, scale: float) -> Path:
    spec = json.loads(spec_path.read_text())
    slug = spec.get("slug", spec_path.stem)
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    pub = pl.ENGINE / "public"
    f = lambda s: int(round(s * FPS))  # noqa: E731

    if spec.get("mode") == "voice":
        return run_voice(spec, slug, work, pub, out_dir, scale)

    # timeline, in seconds
    messages = []
    cps = spec.get("type_speed", CHARS_PER_SEC)
    if spec.get("cold_open"):
        # open mid-action: the chat is already there and typing is under way
        # (prefill = characters already typed on frame 1), never an idle screen
        for m in spec.get("incoming", []):
            messages.append({"from": "them", "text": m, "frame": 0})
        type_start = 0.1 - spec.get("prefill", 0) / cps
    else:
        t = 0.6
        for m in spec.get("incoming", []):
            messages.append({"from": "them", "text": m, "frame": f(t)})
            t += 0.9
        type_start = t + 0.3
    type_end = type_start + len(spec["draft"]) / cps
    tap = type_end + spec.get("pause", 0.9)          # beat to let viewers spot the mistakes
    fix = tap + spec.get("working_seconds", 0.6)     # the app is fast; keep the wait short
    send = fix + spec.get("hold_fixed", 1.6)         # read the corrected text in the field
    messages.append({"from": "me", "text": spec["fixed"], "frame": f(send)})
    end = send + 1.0
    if spec.get("reply"):
        messages.append({"from": "them", "text": spec["reply"], "frame": f(send + 1.0)})
        end = send + 2.4
    body = end

    draft_tokens, fixed_tokens = diff_tokens(spec["draft"], spec["fixed"])
    headlines = [{"text": spec["hook"], "fromFrame": 0, "toFrame": f(tap)}]
    if spec.get("wait"):
        headlines.append({"text": spec["wait"], "fromFrame": f(tap), "toFrame": f(fix)})
    else:
        headlines[0]["toFrame"] = f(fix)
    headlines.append({"text": spec["after"], "check": True, "fromFrame": f(fix), "toFrame": f(body)})

    cta_s = spec.get("cta_seconds", 3.0)
    total = body + cta_s
    track = pub / f"{slug}_audio.mp3"
    sound_mod.design(track, total, [round(tap, 3), round(fix, 3), round(send, 3)],
                     typing_runs=[(max(0.0, type_start), type_end)], bpm=spec.get("bpm", 118),
                     style=spec.get("music_style", "calm"), music_gain=0.45)

    props = {
        "contact": spec.get("contact", "Priya"),
        "tool": spec.get("tool", "Fix grammar"),
        "messages": messages,
        "draft": spec["draft"],
        "draftTokens": draft_tokens,
        "fixedTokens": fixed_tokens,
        "typeStart": f(type_start), "typeEnd": f(type_end),
        "tapFrame": f(tap), "fixFrame": f(fix), "sendFrame": f(send),
        "bodyFrames": f(body),
        "headlines": headlines,
        "audio": track.name,
        "cta": {"durationInFrames": f(cta_s), "wordmark": "Type Better",
                "line": spec.get("cta_line", "Start free — 2,000 AI words."),
                "store": spec.get("store_line", "on the App Store and Google Play"),
                "icon": "app_icon_1024.png"},
        "fps": FPS,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale, composition_id="ChatMock")
    print(f"  rendered: {out}  ({total:.1f}s)")
    return out


def run_voice(spec: dict, slug: str, work: Path, pub: Path, out_dir: Path, scale: float) -> Path:
    """Cold open on the dictation panel, already listening: a messy spoken line,
    words appearing as they're said, a 0.5s clean-up, the clean text lands with
    a jolt, gets sent. No typing, no idle first second."""
    import wave

    import numpy as np

    f = lambda s_: int(round(s_ * FPS))  # noqa: E731
    vpath = work / "voice.wav"
    vdur = voice_mod.speak_elevenlabs(spec["voice_text"], work / "voice_raw.wav", voice=spec.get("voice_id"))
    # tighten slow dramatic deliveries so the payoff lands inside ~6s
    tempo = spec.get("voice_speed", 1.0)
    pl.sh(["ffmpeg", "-v", "error", "-i", str(work / "voice_raw.wav"), "-af", f"atempo={tempo}",
           "-y", str(vpath)])
    vdur = vdur / tempo
    v0 = 0.15                                    # speech starts on the first beat
    # Whisper drops "um"/"uh", which are the point of this video, so show the
    # script's own words, timed across the span Whisper heard speech in
    heard = voice_mod.word_timings(vpath, offset_s=v0)
    s0 = heard[0]["startMs"] / 1000 if heard else v0
    s1 = heard[-1]["endMs"] / 1000 if heard else v0 + vdur
    script = spec["voice_text"].split()
    weights = [len(w) + 2 for w in script]
    tot, acc, spoken = sum(weights), 0, []
    for i, w in enumerate(script):
        spoken.append({"text": (" " if i else "") + w, "frame": f(s0 + (s1 - s0) * acc / tot)})
        acc += weights[i]
    tap = v0 + vdur + 0.25
    fix = tap + spec.get("working_seconds", 0.5)
    send = fix + spec.get("hold_fixed", 1.8)
    messages = [{"from": "them", "text": m, "frame": 0} for m in spec.get("incoming", [])]
    messages.append({"from": "me", "text": spec["fixed"], "frame": f(send)})
    end = send + 1.0
    if spec.get("reply"):
        messages.append({"from": "them", "text": spec["reply"], "frame": f(send + 0.9)})
        end = send + 2.2
    body = end
    _, fixed_tokens = diff_tokens(spec["voice_text"], spec["fixed"])
    headlines = [{"text": spec["hook"], "fromFrame": 0, "toFrame": f(fix)}]
    if spec.get("outro") and body - fix > 2.8:
        headlines.append({"text": spec["after"], "check": True, "fromFrame": f(fix), "toFrame": f(body - 1.6)})
        headlines.append({"text": spec["outro"], "fromFrame": f(body - 1.6), "toFrame": f(body)})
    else:
        headlines.append({"text": spec["after"], "check": True, "fromFrame": f(fix), "toFrame": f(body)})

    cta_s = spec.get("cta_seconds", 2.5)
    total = body + cta_s
    # trailer-style bed: a low impact on frame 1, tension to the fix, payoff
    sig = sound_mod.suspense_bed(total, fix)
    n = len(sig)
    m = int(1.4 * sound_mod.SR)
    tt = np.arange(m) / sound_mod.SR
    boom = 0.9 * np.sin(2 * np.pi * (48 + 60 * np.exp(-9 * tt)) * tt) * np.exp(-2.6 * tt)
    sig[:m] += boom[: min(m, n)]
    sig = np.tanh(sig * 1.05)
    pcm = (np.stack([sig, sig], axis=1) * 0.85 * 32767).astype(np.int16)
    bed = work / "bed.wav"
    with wave.open(str(bed), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sound_mod.SR)
        w.writeframes(pcm.tobytes())
    vtrack = work / "voice_track.wav"
    ms = int(v0 * 1000)
    pl.sh(["ffmpeg", "-v", "error", "-i", str(vpath), "-filter_complex",
           f"[0:a]aresample=48000,adelay={ms}|{ms},loudnorm=I=-15:TP=-1.5:LRA=11,apad,atrim=0:{total:.3f}[o]",
           "-map", "[o]", "-ar", "48000", "-ac", "2", "-y", str(vtrack)])
    track = pub / f"{slug}_audio.mp3"
    sound_mod.mix_with_voice(vtrack, bed, track, total, bed_gain=0.4)

    props = {
        "mode": "voice", "spokenWords": spoken, "jolt": True,
        "contact": spec.get("contact", "Priya"),
        "tool": spec.get("tool", "Voice"),
        "messages": messages,
        "draft": "", "draftTokens": [], "fixedTokens": fixed_tokens,
        "typeStart": f(fix), "typeEnd": f(fix),
        "tapFrame": f(tap), "fixFrame": f(fix), "sendFrame": f(send),
        "bodyFrames": f(body),
        "headlines": headlines,
        "audio": track.name,
        "cta": {"durationInFrames": f(cta_s), "wordmark": "Type Better",
                "line": spec.get("cta_line", "Start free — 2,000 AI words."),
                "store": spec.get("store_line", "on the App Store and Google Play"),
                "icon": "app_icon_1024.png"},
        "fps": FPS,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale, composition_id="ChatMock")
    print(f"  rendered: {out}  ({total:.1f}s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Chat mock-up video from a text spec.")
    ap.add_argument("--spec", required=True, nargs="+")
    ap.add_argument("--out", type=Path, default=pl.ROOT / "out")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    for s in a.spec:
        sp = Path(s)
        if not sp.exists():
            sp = pl.ROOT / "viral" / "chats" / f"{s}.json"
        run(sp, a.out, a.scale)


if __name__ == "__main__":
    main()
