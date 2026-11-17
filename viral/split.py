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
    for i, seg in enumerate(spec["segments"]):
        rec = pl.ROOT / seg["recording"]
        plan = beats_mod.cap_duration(beats_mod.plan_segments(rec), spec.get("max_segment_seconds", 7.0))
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
        a, b, c = cursor, cursor + fix, cursor + dur
        headlines.append({"text": seg["before"], "fromFrame": round(a * fps), "toFrame": round(b * fps)})
        headlines.append({"text": seg["after"], "check": True, "fromFrame": round(b * fps), "toFrame": round(c * fps)})
        beat_times += [round(cursor + x["t_out"], 3) for x in beats]
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
    reaction = pub / f"{slug}_reaction.mp4"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(reaction_src), "-an",
           "-vf", f"scale=1080:-2,crop=1080:{REACTION_H}:0:(ih-{REACTION_H})/2.6,fps={fps}",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(reaction)])
    reaction_frames = int(math.floor(float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(reaction)],
        capture_output=True, text=True, check=True).stdout) * fps))

    cta_s = spec.get("cta_seconds", 3.5)
    total = cursor + cta_s
    track = pub / f"{slug}_audio.mp3"
    sound_mod.design(track, total, beat_times + [round(cursor, 3)], typing_runs=None,
                     bpm=spec.get("bpm", 120), style=spec.get("music_style", "punchy"), music_gain=0.55)

    props = {
        "phone": phone.name, "phoneWidth": PHONE_W, "phoneHeight": PHONE_H,
        "reaction": reaction.name, "reactionFrames": reaction_frames,
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
