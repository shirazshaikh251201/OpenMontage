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

    # timeline, in seconds
    t = 0.6
    messages = []
    for m in spec.get("incoming", []):
        messages.append({"from": "them", "text": m, "frame": f(t)})
        t += 0.9
    type_start = t + 0.3
    type_end = type_start + len(spec["draft"]) / CHARS_PER_SEC
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
                     typing_runs=[(type_start, type_end)], bpm=spec.get("bpm", 118),
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
