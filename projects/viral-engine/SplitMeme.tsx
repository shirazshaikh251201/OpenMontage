import React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Loop,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { ACCENT, CREAM, Cta, FontFaces, INK, SANS, SceneProps } from "./Composition";

// ---------------------------------------------------------------------------
// SPLIT MEME — the format CleverType runs as paid Reels: a headline on top, a
// tight crop of the phone (message field + keyboard only, full width) in a
// card, and an unrelated reaction clip filling the bottom to hold attention.
// No narration: the headline changes as each feature lands.
// ---------------------------------------------------------------------------

export interface Headline {
  text: string;
  /** show the green tick, as on a fix that just landed */
  check?: boolean;
  fromFrame: number;
  toFrame: number;
}

export interface SplitProps {
  phone: string;
  phoneWidth: number;
  phoneHeight: number;
  reaction: string;
  reactionFrames: number;
  /** frame the fix lands: the reaction crash-zooms here (the edited "surprise") */
  revealFrame?: number;
  /** where the face is in the strip, 0-1, so the zoom lands on it */
  reactionFocusX?: number;
  reactionFocusY?: number;
  /** seconds into the reaction clip where the animal is genuinely startled;
   *  when set, the clip is timed so that moment lands on revealFrame and the
   *  edited crash zoom is skipped */
  surpriseAt?: number;
  bodyFrames: number;
  headlines: Headline[];
  audio?: string | null;
  cta: SceneProps["cta"];
  fps: number;
}

const TOP = 340;

const HeadlineLayer: React.FC<{ headlines: Headline[]; fps: number }> = ({ headlines, fps }) => {
  const frame = useCurrentFrame();
  const h = headlines.find((x) => frame >= x.fromFrame && frame < x.toFrame);
  if (!h) return null;
  const s = spring({ frame: frame - h.fromFrame, fps, config: { damping: 200, mass: 0.5, stiffness: 240 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 60,
        right: 60,
        height: TOP - 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        opacity: s,
        transform: `translateY(${(1 - s) * 14}px)`,
      }}
    >
      <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 66, lineHeight: 1.12, color: INK, letterSpacing: "-0.01em" }}>
        {h.check ? (
          <span
            style={{
              display: "inline-flex",
              width: 62,
              height: 62,
              borderRadius: "50%",
              background: ACCENT,
              color: "#fff",
              fontSize: 42,
              alignItems: "center",
              justifyContent: "center",
              marginRight: 16,
              verticalAlign: "-6px",
            }}
          >
            ✓
          </span>
        ) : null}
        {h.text}
      </div>
    </div>
  );
};

// Calm part of the clip loops until the final play-through, which starts so the
// clip's own "startled" moment lands exactly on the fix; its last second then
// holds by looping until the end card.
const TimedReaction: React.FC<{
  src: string;
  clipFrames: number;
  surpriseFrame: number;
  revealFrame: number;
  bodyFrames: number;
}> = ({ src, clipFrames, surpriseFrame, revealFrame, bodyFrames }) => {
  const style = { width: "100%", height: "100%", objectFit: "cover" as const };
  const start = Math.max(0, revealFrame - surpriseFrame);
  const calm = Math.max(15, surpriseFrame - 20);
  const tail = Math.min(30, clipFrames);
  return (
    <>
      {start > 0 ? (
        <Sequence from={0} durationInFrames={start}>
          <Loop durationInFrames={calm}>
            <OffthreadVideo src={staticFile(src)} muted endAt={calm} style={style} />
          </Loop>
        </Sequence>
      ) : null}
      <Sequence from={start} durationInFrames={clipFrames}>
        <OffthreadVideo src={staticFile(src)} muted startFrom={Math.max(0, surpriseFrame - revealFrame)} style={style} />
      </Sequence>
      {start + clipFrames < bodyFrames ? (
        <Sequence from={start + clipFrames} durationInFrames={bodyFrames - start - clipFrames}>
          <Loop durationInFrames={tail}>
            <OffthreadVideo src={staticFile(src)} muted startFrom={clipFrames - tail} style={style} />
          </Loop>
        </Sequence>
      ) : null}
    </>
  );
};

export const SplitMeme: React.FC<SplitProps> = ({
  phone, phoneWidth, phoneHeight, reaction, reactionFrames, bodyFrames, headlines, audio, cta, fps,
  revealFrame, reactionFocusX, reactionFocusY, surpriseAt,
}) => {
  const frame = useCurrentFrame();
  const left = (1080 - phoneWidth) / 2;
  const reactionTop = TOP + phoneHeight + 28;
  const pop = interpolate(frame, [0, 8], [0.96, 1], { extrapolateRight: "clamp" });

  // Crash zoom on the fix: snap in over 3 frames, shake, hold, ease back.
  const real = surpriseAt !== undefined && revealFrame !== undefined;
  const r = real ? -999 : revealFrame ?? -999;
  const d = frame - r;
  const zoom =
    d < 0 ? 1 : d < 3 ? interpolate(d, [0, 3], [1, 1.75]) : d < 45 ? 1.75 : interpolate(d, [45, 60], [1.75, 1], { extrapolateRight: "clamp" });
  const shake = d >= 0 && d < 14 ? (14 - d) / 14 : 0;
  const sx = shake * 18 * Math.sin(d * 2.7);
  const sy = shake * 12 * Math.cos(d * 3.3);
  const flash = d >= 0 && d < 4 ? interpolate(d, [0, 4], [0.75, 0]) : 0;
  return (
    <AbsoluteFill style={{ background: CREAM }}>
      <FontFaces />
      {audio ? <Audio src={staticFile(audio)} /> : null}

      <Sequence from={0} durationInFrames={bodyFrames} name="body">
        <AbsoluteFill>
          <div
            style={{
              position: "absolute",
              top: reactionTop,
              left: 0,
              right: 0,
              bottom: 0,
              overflow: "hidden",
              background: INK,
            }}
          >
            {real ? (
              <TimedReaction
                src={reaction}
                clipFrames={reactionFrames}
                surpriseFrame={Math.round((surpriseAt as number) * fps)}
                revealFrame={revealFrame as number}
                bodyFrames={bodyFrames}
              />
            ) : (
            <Loop durationInFrames={reactionFrames}>
              <OffthreadVideo
                src={staticFile(reaction)}
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transformOrigin: `${(reactionFocusX ?? 0.5) * 100}% ${(reactionFocusY ?? 0.5) * 100}%`,
                  transform: `translate(${sx}px, ${sy}px) scale(${zoom})`,
                }}
              />
            </Loop>
            )}
            <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
          </div>

          <div
            style={{
              position: "absolute",
              top: TOP,
              left,
              width: phoneWidth,
              height: phoneHeight,
              borderRadius: 46,
              overflow: "hidden",
              boxShadow: "0 24px 60px rgba(11,11,16,0.22)",
              transform: `scale(${pop})`,
              background: INK,
            }}
          >
            <OffthreadVideo src={staticFile(phone)} muted style={{ width: "100%", height: "100%" }} />
          </div>

          <HeadlineLayer headlines={headlines} fps={fps} />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={bodyFrames} durationInFrames={cta.durationInFrames} name="cta">
        <Cta cta={cta} fps={fps} />
      </Sequence>
    </AbsoluteFill>
  );
};

export const calculateSplitMetadata: CalculateMetadataFunction<SplitProps> = async ({ props }) => ({
  durationInFrames: (props.bodyFrames ?? 0) + (props.cta?.durationInFrames ?? 0) || 600,
  fps: props.fps ?? 30,
  width: 1080,
  height: 1920,
});
