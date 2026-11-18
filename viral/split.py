#!/usr/bin/env python3
"""Split-screen meme reel: headline on top, phone close-up, reaction clip below.

    python viral/split.py --spec grammar-tone-shorten

The format competitors (CleverType) run as paid Reels. The phone is cropped to
the message field + keyboard only — full width, so no keyboard text is ever
clipped — and an attention-holding reaction clip fills the bottom. There is no
narration; each section's headline switches from the problem ("Typing in a
hurry?") to the fix ("✓ Fix grammar in one tap.") on that section's biggest
on-screen change.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral import pipeline as pl  # noqa: E402
from viral.steps import beats as beats_mod  # noqa: E402
from viral.steps import sound as sound_mod  # noqa: E402
from viral.steps import voice as voice_mod  # noqa: E402

# Source rows 1120-2330 of a 1170x2532 iPhone recording: the message field,
# suggestion bar and keys, without the chat history or the globe/mic row.
PHONE_CROP = "crop=1170:1210:0:1120"
PHONE_W, PHONE_H = 960, 994
TOP = 340
REACTION_H = 1920 - (TOP + PHONE_H + 28)


def run(spec_path: Path, out_dir: Path, scale: float) -> Path:
    spec = json.loads(spec_path.read_text())
    slug = spec.get("slug", spec_path.stem)
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    pub = pl.ENGINE / "public"
    fps = pl.FPS

    parts, headlines, beat_times, cursor = [], [], [], 0.0
    voices: list[tuple[Path, float]] = []      # spoken lines and where they start
    for i, seg in enumerate(spec["segments"]):
        rec = pl.ROOT / seg["recording"]
        wait_out = None
        if spec.get("real_time"):
            # show how long it really takes: typing and the wait at 1x, only
            # idle air (before typing, after the result) trimmed
            plan = beats_mod.plan_segments(rec, typing_speed=1.0, dead_speed=2.5)
            # the app's own wait ("Generating Text") shows as a still screen, so
            # the plan would compress it; it is the thing viewers should see in
            # real time, so the longest still stretch before the fix plays at 1x
            src_beats = beats_mod.find_beats(rec)
            if src_beats:
                fix_src = max(src_beats, key=lambda x: x.strength).t
                still = [x for x in plan if x.speed > 1.0 and x.end <= fix_src + 0.05]
                if still:
                    long_ = [x for x in still if x.end - x.start >= 1.5] or still
                    wait = max(long_, key=lambda x: x.end)
                    # wait_seconds squeezes the app's wait to a set length (e.g.
                    # 0.5s so it reads as instant); otherwise it plays at 1x
                    # the spinner starts at the panel switch just before the still
                    # stretch, so the wait runs from that beat to the result
                    w0 = max([x.t for x in src_beats if wait.start - 2.0 < x.t < wait.start] or
                             [wait.start - 0.15]) + 0.15
                    ws = spec.get("wait_seconds")
                    wspeed = max(1.0, (wait.end - w0) / ws) if ws else 1.0
                    plan = beats_mod.retime(plan, w0, wait.end, round(wspeed, 4), "app working")
                    wait = next(x for x in plan if x.reason == "app working")
                    # output time where the wait starts = where "watch this" goes
                    wait_out = sum(x.out_duration for x in plan if x.end <= wait.start + 1e-6)
        else:
            plan = beats_mod.cap_duration(beats_mod.plan_segments(rec), spec.get("max_segment_seconds", 7.0))
        ranges = list(seg.get("real_ranges", []))
        voice_win = None
        if seg.get("voice"):
            # a spoken line over the app's "Listening" stretch: the recordings
            # are silent, so the viewer hears what was said into the app
            v = seg["voice"]
            vpath = work / f"voice_{i}.wav"
            vdur = voice_mod.speak_elevenlabs(v["text"], vpath, voice=v.get("voice_id"))
            w0, w1 = v["window"]
            ranges.append([w0, w1, max(0.25, (w1 - w0) / (vdur + 0.7))])
            voice_win = (w0, vpath)
        for r in ranges:
            # stretches that must play at 1x (or slower, given as a third value),
            # e.g. the bad sentence sitting on screen while the countdown runs
            # and viewers hunt for mistakes; a still screen can be slowed freely
            plan = beats_mod.retime(plan, r[0], r[1], r[2] if len(r) > 2 else 1.0, "hold for the viewer")
        if seg.get("tap_at") is not None:
            # source time of the tap: the "while it works" headline starts here
            wait_out = sum((min(x.end, seg["tap_at"]) - x.start) / x.speed
                           for x in plan if x.start < seg["tap_at"]) + 0.6
        for a_, b_ in seg.get("cut", []):
            # drop glitch frames from the recording (e.g. an app redraw flicker)
            plan = beats_mod.retime(plan, a_, b_, None, "cut")
        voice_out = None
        if voice_win:
            voice_out = sum((min(x.end, voice_win[0]) - x.start) / x.speed
                            for x in plan if x.start < voice_win[0]) + 0.3
            voices.append((voice_win[1], cursor + voice_out))
        analysis = beats_mod.analyse(rec, plan)
        part = work / f"phone_{i}.mp4"
        graph = beats_mod.build_filter(plan) + \
            f";[outv]{PHONE_CROP},scale={PHONE_W}:{PHONE_H},fps={fps}[final]"
        pl.sh(["ffmpeg", "-v", "error", "-i", str(rec), "-filter_complex", graph, "-map", "[final]",
               "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(part)])
        dur = math.floor(float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(part)],
            capture_output=True, text=True, check=True).stdout) * fps) / fps
        beats = [b for b in analysis["beats"] if 0.3 < b["t_out"] < dur - 0.3]
        # the fix lands on the section's strongest change
        fix = max(beats, key=lambda b: b["strength"])["t_out"] if beats else dur * 0.6
        if seg.get("fix_at") is not None:
            # the biggest change isn't always the fix (e.g. the keyboard switching
            # to "Listening"); fix_at pins it to a source time
            fix = sum((min(x.end, seg["fix_at"]) - x.start) / x.speed
                      for x in plan if x.start < seg["fix_at"])
        a, b, c = cursor, cursor + fix, cursor + dur
        before = seg["before"]
        if isinstance(before, list):
            # a sequence of headlines across the build-up (e.g. a countdown);
            # the last one is shown up to the tap, and the rest share the time before it
            seg = dict(seg)
            seg["before"] = before[-1]
            steps = before[:-1]
        else:
            steps = []
        if seg.get("wait"):
            # third headline while the app is working: from the tap to the fix
            if wait_out is not None:
                tap = max(0.5, wait_out - 0.6)
            else:
                taps = [x["t_out"] for x in beats if x["t_out"] < fix - 0.8]
                tap = taps[-1] if taps else max(0.5, fix - 2.5)
            t0 = a
            if voice_out is not None and seg.get("quote"):
                # hook until the speech starts, then what is being said
                headlines.append({"text": seg["before"], "fromFrame": round(a * fps),
                                  "toFrame": round((cursor + voice_out) * fps)})
                seg = dict(seg)
                seg["before"] = seg["quote"]
                t0 = cursor + voice_out
                steps = []
            if steps:
                span = (cursor + tap - a) / (len(steps) + 1)
                for k_, txt in enumerate(steps):
                    headlines.append({"text": txt, "fromFrame": round((a + k_ * span) * fps),
                                      "toFrame": round((a + (k_ + 1) * span) * fps)})
                t0 = a + len(steps) * span
            headlines.append({"text": seg["before"], "fromFrame": round(t0 * fps), "toFrame": round((cursor + tap) * fps)})
            headlines.append({"text": seg["wait"], "fromFrame": round((cursor + tap) * fps), "toFrame": round(b * fps)})
        else:
            headlines.append({"text": seg["before"], "fromFrame": round(a * fps), "toFrame": round(b * fps)})
        if seg.get("outro") and c - b > 2.6:
            # last beat before the end card: a question that earns comments
            o = c - 1.6
            headlines.append({"text": seg["after"], "check": True, "fromFrame": round(b * fps), "toFrame": round(o * fps)})
            headlines.append({"text": seg["outro"], "fromFrame": round(o * fps), "toFrame": round(c * fps)})
        else:
            headlines.append({"text": seg["after"], "check": True, "fromFrame": round(b * fps), "toFrame": round(c * fps)})
        beat_times += [round(cursor + x["t_out"], 3) for x in beats]
        reveal = cursor + fix
        print(f"  [{i + 1}/{len(spec['segments'])}] {rec.name}: {analysis['source_duration']}s -> {dur:.2f}s, fix at {fix:.2f}s")
        parts.append(part)
        cursor += dur

    phone = pub / f"{slug}_phone.mp4"
    inputs = [x for p in parts for x in ("-i", str(p))]
    pl.sh(["ffmpeg", "-v", "error", *inputs, "-filter_complex",
           "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]",
           "-map", "[v]", "-r", str(fps), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(phone)])
    body_frames = int(math.floor(cursor * fps))

    reaction_src = pl.ROOT / spec["reaction"]
    framing = pl.ROOT / "viral" / "stock" / "reaction_framing.json"
    if "reaction_y" not in spec and framing.exists():
        f = json.loads(framing.read_text()).get(reaction_src.stem, 0.38)
        f = f if isinstance(f, dict) else {"y": f}
        spec["reaction_y"] = f.get("y", 0.38)
        spec.setdefault("reaction_focus_x", f.get("focus_x", 0.5))
        spec.setdefault("reaction_focus_y", f.get("focus_y", 0.5))
    reaction = pub / f"{slug}_reaction.mp4"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(reaction_src), "-an",
           # reaction_y: where the subject's face sits, as a fraction of the
           # clip's height, so the wide strip keeps it in frame
           "-vf", f"scale=1080:-2,crop=1080:{REACTION_H}:0:"
                  f"'max(0,min(ih-{REACTION_H},ih*{spec.get('reaction_y', 0.38)}-{REACTION_H}/2))',fps={fps}",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(reaction)])
    reaction_frames = int(math.floor(float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(reaction)],
        capture_output=True, text=True, check=True).stdout) * fps))

    cta_s = spec.get("cta_seconds", 3.5)
    total = cursor + cta_s
    track = pub / f"{slug}_audio.mp3"
    bed_out = (work / "bed.wav") if voices else track
    if spec.get("music_style") == "suspense":
        import wave
        import numpy as np
        sig = sound_mod.suspense_bed(total, reveal)
        pcm = (np.stack([sig, sig], axis=1) * 0.85 * 32767).astype(np.int16)
        wav = work / "suspense.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sound_mod.SR)
            w.writeframes(pcm.tobytes())
        pl.sh(["ffmpeg", "-v", "error", "-i", str(wav), "-b:a", "192k", "-y", str(bed_out)])
    else:
        sound_mod.design(bed_out, total, beat_times + [round(cursor, 3)], typing_runs=None,
                         bpm=spec.get("bpm", 120), style=spec.get("music_style", "punchy"), music_gain=0.55)
    if voices:
        # lay the spoken lines on one track, then duck the music under them
        vt = work / "voices.wav"
        ins = [x for v_, _ in voices for x in ("-i", str(v_))]
        g = ";".join(f"[{k}:a]aresample=48000,adelay={int(t * 1000)}|{int(t * 1000)}[v{k}]"
                     for k, (_, t) in enumerate(voices))
        g += ";" + "".join(f"[v{k}]" for k in range(len(voices))) + \
            f"amix=inputs={len(voices)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.3f}[o]"
        pl.sh(["ffmpeg", "-v", "error", *ins, "-filter_complex", g, "-map", "[o]",
               "-ar", "48000", "-ac", "2", "-y", str(vt)])
        sound_mod.mix_with_voice(vt, bed_out, track, total)

    props = {
        "phone": phone.name, "phoneWidth": PHONE_W, "phoneHeight": PHONE_H,
        "reaction": reaction.name, "reactionFrames": reaction_frames,
        # the surprise lands on the last section's fix
        "revealFrame": round(reveal * fps),
        "reactionFocusX": spec.get("reaction_focus_x", 0.5),
        "reactionFocusY": spec.get("reaction_focus_y", 0.5),
        **({"surpriseAt": spec["surprise_at"]} if "surprise_at" in spec else {}),
        "bodyFrames": body_frames, "headlines": headlines, "audio": track.name,
        "cta": {"durationInFrames": int(cta_s * fps), "wordmark": "Type Better",
                "line": spec.get("cta_line", "Start free — 2,000 AI words."),
                "store": "on the App Store", "icon": "app_icon_1024.png"},
        "fps": fps,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale, composition_id="SplitMeme")
    print(f"  rendered: {out}  ({total:.1f}s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Split-screen meme reel.")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", type=Path, default=pl.ROOT / "out")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    sp = Path(a.spec)
    if not sp.exists():
        sp = pl.ROOT / "viral" / "splits" / f"{a.spec}.json"
    run(sp, a.out, a.scale)


if __name__ == "__main__":
    main()
