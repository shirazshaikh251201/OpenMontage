#!/usr/bin/env python3
"""Multi-feature promo: several recordings cut into one video.

    python viral/promo.py --promo all-features

`pipeline.py` turns ONE recording into one video. A promo walks through
several features, so each segment is its own recording with its own narration,
conformed with the same speed policy and crop, then joined. Every segment is
only as long as its narration needs (or its natural compressed length, if
longer), a feature label marks each section, and the closing line plays over
the end card instead of leaving it silent.
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

GAP = 0.18      # between narration lines
LEAD = 0.25     # before the first line of a segment
TAIL = 0.5      # breathing room after the last line of a segment


def run(promo_path: Path, out_dir: Path, scale: float) -> Path:
    promo = json.loads(promo_path.read_text())
    slug = promo.get("slug", promo_path.stem)
    work = out_dir / slug
    work.mkdir(parents=True, exist_ok=True)
    pub = pl.ENGINE / "public"
    pub.mkdir(parents=True, exist_ok=True)
    fps = pl.FPS
    print(f"\n  promo     {promo['name']}")

    parts, vo_segs, offsets, beat_times, labels = [], [], [], [], []
    cursor = 0.0
    for i, seg in enumerate(promo["segments"]):
        rec = pl.ROOT / seg["recording"]
        if seg.get("start"):
            # skip a bad opening (e.g. the iOS "Allow Paste" prompt in Reply)
            cut = work / f"src_{i}.mp4"
            pl.sh(["ffmpeg", "-v", "error", "-ss", str(seg["start"]), "-i", str(rec),
                   "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-y", str(cut)])
            rec = cut
        vo = voice_mod.narrate(seg["script"], work / f"vo_{i}")
        needed = LEAD + sum(v["duration"] for v in vo) + GAP * (len(vo) - 1) + TAIL
        plan = beats_mod.fit_to_duration(beats_mod.plan_segments(rec), needed)
        # keep the pace: no section longer than the cap, unless its narration needs it
        cap = max(needed, promo.get("max_segment_seconds", 99.0))
        plan = beats_mod.cap_duration(plan, cap)
        analysis = beats_mod.analyse(rec, plan)
        part = work / f"seg_{i}.mp4"
        dur = pl.normalise(rec, part, plan, promo.get("crop"), needed)
        # whole frames only, so label/caption timing matches the joined file
        dur = math.floor(dur * fps) / fps

        t = cursor + LEAD
        for v in vo:
            offsets.append(round(t, 3))
            t += v["duration"] + GAP
        vo_segs += vo
        beat_times += [round(cursor + b["t_out"], 3) for b in analysis["beats"]
                       if 0.4 < b["t_out"] < dur - 0.3]
        labels.append({"text": seg["label"], "from": cursor, "to": cursor + dur})
        parts.append(part)
        print(f"  [{i + 1}/{len(promo['segments'])}] {seg['label']:<8} "
              f"{rec.name}: {analysis['source_duration']}s -> {dur:.2f}s")
        cursor += dur

    # join -----------------------------------------------------------------
    footage = pub / f"{slug}_footage.mp4"
    inputs = [x for p in parts for x in ("-i", str(p))]
    graph = "".join(f"[{i}:v]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
    pl.sh(["ffmpeg", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]",
           "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-y", str(footage)])
    body = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(footage)],
        capture_output=True, text=True, check=True).stdout.strip())
    body_frames = int(math.floor(body * fps))

    # closing line plays over the end card ----------------------------------
    cta_vo = voice_mod.narrate([promo["cta_script"]], work / "vo_cta")
    cta_s = max(promo.get("cta_seconds", 4.5), cta_vo[0]["duration"] + 0.9)
    cta_frames = int(math.ceil(cta_s * fps))
    total = (body_frames + cta_frames) / fps

    all_vo = vo_segs + cta_vo
    all_off = offsets + [round(body + 0.35, 3)]
    vo = voice_mod.assemble_vo(all_vo, all_off, total, work / "narration.wav")
    hook_s = promo.get("hook_seconds", 2.2)
    # the hook card already shows the first line; a caption under it repeats it
    captions = [c for c in voice_mod.captions_for(vo_segs, offsets, work)
                if c["startMs"] >= hook_s * 1000]

    bed = sound_mod.design(work / "bed.wav", total, beat_times + [round(body, 3)],
                           typing_runs=None, bpm=promo.get("bpm", 120),
                           style=promo.get("music_style", "punchy"), music_gain=0.45)
    track = pub / f"{slug}_audio.mp3"
    sound_mod.mix_with_voice(vo, bed, track, total)

    n = len(labels)
    props = {
        "video": footage.name,
        "videoDurationInFrames": body_frames,
        "hook": {"text": promo["hook"], "sub": promo.get("hook_sub"),
                 "durationInFrames": int(hook_s * fps)},
        "captions": captions,
        "zooms": [{"t": t, "scale": promo.get("zoom", 1.0)} for t in beat_times],
        "labels": [{"text": lb["text"], "index": i + 1, "count": n,
                    "fromFrame": int(round(max(lb["from"], hook_s if i == 0 else lb["from"]) * fps)),
                    "toFrame": int(round(lb["to"] * fps))}
                   for i, lb in enumerate(labels)],
        "audio": track.name,
        "cta": {"durationInFrames": cta_frames,
                "wordmark": promo.get("wordmark", "Type Better"),
                "line": promo.get("cta_line", "Start free — 2,000 AI words."),
                "store": promo.get("store_line", "on the App Store"),
                "icon": "app_icon_1024.png"},
        "fps": fps,
    }
    out = out_dir / f"{slug}.mp4"
    pl.render(props, out, scale)
    print(f"  rendered: {out}  ({total:.1f}s)\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Several recordings -> one feature promo.")
    ap.add_argument("--promo", required=True)
    ap.add_argument("--out", type=Path, default=pl.ROOT / "out")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    pp = Path(a.promo)
    if not pp.exists():
        pp = pl.ROOT / "viral" / "promos" / f"{a.promo}.json"
    if not pp.exists():
        raise SystemExit(f"promo not found: {a.promo}")
    run(pp, a.out, a.scale)


if __name__ == "__main__":
    main()
