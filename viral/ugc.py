#!/usr/bin/env python3
"""Creator / AI-avatar ad: a talking head opens, then the app demo plays.

    python viral/ugc.py --presenter raw/creator/hook1.mp4 \
        --recording "raw/v2/1 grammar-three.mov" --slug ugc-grammar

The presenter clip drives everything: its own voice is the narration (no TTS),
its words become the captions, and its first sentence decides how long the face
fills the screen before cutting to the phone. After the cut the face stays on
screen in a bubble while the demo plays under the rest of what they say.
Works the same for a real creator's selfie video or an AI-avatar render.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viral import pipeline as pl  # noqa: E402
from viral.steps import beats as beats_mod  # noqa: E402
from viral.steps import sound as sound_mod  # noqa: E402
from viral.steps import voice as voice_mod  # noqa: E402


def duration(p: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True, check=True).stdout.strip())


def run(presenter: Path, recording: Path, slug: str, out_dir: Path, intro_s: float | None,
        cta_line: str, scale: float) -> Path:
    fps, W, H = pl.FPS, pl.W, pl.H
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    pub = pl.ENGINE / "public"

    # 1 ── presenter: conform video, keep voice separately ------------------
    face = pub / f"{slug}_presenter.mp4"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(presenter),
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
           "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(face)])
    voice = work / "presenter.wav"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(presenter), "-vn", "-ac", "2", "-ar", "48000",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-y", str(voice)])
    # 2 ── captions from the presenter's real speech, one page-group per sentence
    words = voice_mod.word_timings(voice)
    # avatar renders run past the last word (Intone adds ~2.5s); end shortly
    # after the speech so the demo doesn't sit under silence
    body = min(duration(voice), (words[-1]["endMs"] / 1000 + 0.8) if words else duration(voice))
    for f in (face, voice):
        tmp = f.with_name(f.stem + "_trim" + f.suffix)
        pl.sh(["ffmpeg", "-v", "error", "-i", str(f), "-t", f"{body:.3f}", "-c", "copy", "-y", str(tmp)])
        tmp.replace(f)
    line = 0
    for w in words:
        w["line"] = line
        if re.search(r"[.!?]$", w["text"].strip()):
            line += 1
    first_end = next((w["endMs"] / 1000 for w in words if w["line"] > 0 or w is words[-1]), 3.0)
    first_end = next((w["endMs"] / 1000 for w in words if re.search(r"[.!?]$", w["text"].strip())), first_end)
    intro = intro_s if intro_s is not None else min(max(first_end + 0.15, 1.5), body - 3.0)
    print(f"  presenter {presenter.name}: {body:.1f}s, face full-screen for {intro:.1f}s")

    # 3 ── demo fills exactly the rest of what they say ---------------------
    demo_s = body - intro
    plan = beats_mod.fit_to_duration(beats_mod.plan_segments(recording), demo_s)
    plan = beats_mod.cap_duration(plan, demo_s)
    analysis = beats_mod.analyse(recording, plan)
    footage = pub / f"{slug}_footage.mp4"
    got = pl.normalise(recording, footage, plan, "crop=1170:2080:0:452", demo_s)
    print(f"  demo {recording.name}: {analysis['source_duration']}s -> {got:.1f}s")

    # 4 ── sound: their voice over a ducked bed, bed carries the end card ---
    cta_s = 3.5
    total = body + cta_s
    beats_out = [round(intro + b["t_out"], 3) for b in analysis["beats"] if b["t_out"] < demo_s - 0.3]
    bed = sound_mod.design(work / "bed.wav", total, beats_out + [round(body, 3)], typing_runs=None,
                           bpm=120, style="punchy", music_gain=0.4)
    track = pub / f"{slug}_audio.mp3"
    sound_mod.mix_with_voice(voice, bed, track, total)

    props = {
        "video": footage.name,
        "videoDurationInFrames": int(math.floor(body * fps)),
        "presenter": {"src": face.name, "introFrames": int(round(intro * fps))},
        "hook": {"text": "", "durationInFrames": 0},
        "captions": words,
        "zooms": [],
        "audio": track.name,
        "cta": {"durationInFrames": int(cta_s * fps), "wordmark": "Type Better",
                "line": cta_line, "store": "on the App Store", "icon": "app_icon_1024.png"},
        "fps": fps,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale)
    print(f"  rendered: {out}  ({total:.1f}s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Talking head + app demo -> one creator-style ad.")
    ap.add_argument("--presenter", required=True, type=Path, help="selfie / avatar clip WITH speech")
    ap.add_argument("--recording", required=True, type=Path, help="screen recording of the app")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--intro", type=float, help="seconds of full-screen face (default: first sentence)")
    ap.add_argument("--cta-line", default="Start free — 2,000 AI words.")
    ap.add_argument("--out", type=Path, default=pl.ROOT / "out")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    run(a.presenter, a.recording, a.slug, a.out, a.intro, a.cta_line, a.scale)


if __name__ == "__main__":
    main()
