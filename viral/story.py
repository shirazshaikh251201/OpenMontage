#!/usr/bin/env python3
"""Creator-story ad: face → full-screen phone demo with voice-over → face.

    python viral/story.py --avatar raw/avatar/story.mp4 --vo raw/avatar/story-b.mp3 \
        --recording "raw/v3/2 professional.mov" --slug story-question-every-word

The shape of the Grammarly creator ads: the creator says the relatable hook to
camera, the video cuts to the phone doing the fix while she keeps talking, and
it comes back to her for the recommendation. The avatar clip holds both of her
on-camera lines (hook, then outro) with a gap between them; the split is found
from the speech itself. The middle line is a separate voice-over.
"""

from __future__ import annotations

import argparse
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


def run(avatar: Path, vo: Path, recording: Path, slug: str, out_dir: Path, scale: float,
        first_line_s: float | None = None) -> Path:
    fps, W, H = pl.FPS, pl.W, pl.H
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    pub = pl.ENGINE / "public"

    # avatar: conform the picture, keep its voice separately
    face = pub / f"{slug}_presenter.mp4"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(avatar),
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
           "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(face)])
    face_audio = work / "face.wav"
    pl.sh(["ffmpeg", "-v", "error", "-i", str(avatar), "-vn", "-ac", "2", "-ar", "48000", "-y", str(face_audio)])

    # split the two on-camera lines at the pause between them. The longest
    # pause can fall inside the hook ("…every word? | Because, same."), so
    # when the hook line's length is known, take the pause nearest to it.
    words = voice_mod.word_timings(face_audio)
    gaps = [(words[i + 1]["startMs"] - words[i]["endMs"], i) for i in range(len(words) - 1)]
    if first_line_s:
        big = [g for g in gaps if g[0] >= 250] or gaps
        _, k = min(big, key=lambda g: abs(words[g[1]]["endMs"] / 1000 - first_line_s))
    else:
        _, k = max(gaps)
    a_end = words[k]["endMs"] / 1000
    c_start = words[k + 1]["startMs"] / 1000
    c_end = words[-1]["endMs"] / 1000
    p1 = a_end + 0.3
    vo_len = duration(vo)
    mid = vo_len + 0.6
    c0 = max(0.0, c_start - 0.2)
    p2 = (c_end + 0.6) - c0
    body = p1 + mid + p2
    print(f"  hook 0-{p1:.1f}s | demo {mid:.1f}s | outro {p2:.1f}s (clip {c0:.1f}s on)")

    # middle: the phone, fitted to the voice-over
    plan = beats_mod.fit_to_duration(beats_mod.plan_segments(recording), mid)
    plan = beats_mod.cap_duration(plan, mid)
    footage = pub / f"{slug}_footage.mp4"
    pl.normalise(recording, footage, plan, "crop=1170:2080:0:452", mid)

    # one narration track: her hook, the voice-over, her outro
    narration = work / "narration.wav"
    ms = lambda s: int(s * 1000)  # noqa: E731
    graph = (
        f"[0:a]atrim=0:{p1:.3f},asetpts=PTS-STARTPTS[a];"
        f"[1:a]aresample=48000,adelay={ms(p1 + 0.2)}|{ms(p1 + 0.2)}[b];"
        f"[0:a]atrim={c0:.3f}:{c_end + 0.6:.3f},asetpts=PTS-STARTPTS,adelay={ms(p1 + mid)}|{ms(p1 + mid)}[c];"
        f"[a][b][c]amix=inputs=3:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{body:.3f}[out]"
    )
    pl.sh(["ffmpeg", "-v", "error", "-i", str(face_audio), "-i", str(vo), "-filter_complex", graph,
           "-map", "[out]", "-ar", "48000", "-ac", "2", "-y", str(narration)])

    caps = voice_mod.fix_brand(voice_mod.word_timings(narration))
    line = 0
    for w in caps:
        w["line"] = line
        if re.search(r"[.!?]$", w["text"].strip()):
            line += 1

    cta_s = 3.0
    total = body + cta_s
    bed = sound_mod.design(work / "bed.wav", total, [round(p1, 3), round(p1 + mid, 3), round(body, 3)],
                           typing_runs=None, bpm=112, style="calm", music_gain=0.35)
    track = pub / f"{slug}_audio.mp3"
    sound_mod.mix_with_voice(narration, bed, track, total)

    props = {
        "video": footage.name,
        "videoDurationInFrames": int(math.floor(body * fps)),
        "presenter": {"src": face.name, "introFrames": int(round(p1 * fps)),
                      "outroFrom": int(round((p1 + mid) * fps)),
                      "outroStartFrom": int(round(c0 * fps)), "showBubble": False},
        "captionStyle": "caps",
        "hook": {"text": "", "durationInFrames": 0},
        "captions": caps,
        "zooms": [],
        "audio": track.name,
        "cta": {"durationInFrames": int(cta_s * fps), "wordmark": "Type Better",
                "line": "Start free — 2,000 AI words.", "store": "on the App Store and Google Play",
                "icon": "app_icon_1024.png"},
        "fps": fps,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale)
    print(f"  rendered: {out}  ({total:.1f}s)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Creator-story ad: face, phone demo, face.")
    ap.add_argument("--avatar", required=True, type=Path, help="clip with both on-camera lines")
    ap.add_argument("--vo", required=True, type=Path, help="voice-over for the phone demo")
    ap.add_argument("--recording", required=True, type=Path)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, default=pl.ROOT / "out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--first-line-seconds", type=float,
                    help="length of the hook line's audio, to find the split between the two lines")
    a = ap.parse_args()
    run(a.avatar, a.vo, a.recording, a.slug, a.out, a.scale, a.first_line_seconds)


if __name__ == "__main__":
    main()
