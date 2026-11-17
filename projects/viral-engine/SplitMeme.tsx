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

export const SplitMeme: React.FC<SplitProps> = ({
  phone, phoneWidth, phoneHeight, reaction, reactionFrames, bodyFrames, headlines, audio, cta, fps,
}) => {
  const frame = useCurrentFrame();
  const left = (1080 - phoneWidth) / 2;
  const reactionTop = TOP + phoneHeight + 28;
  const pop = interpolate(frame, [0, 8], [0.96, 1], { extrapolateRight: "clamp" });
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
            <Loop durationInFrames={reactionFrames}>
              <OffthreadVideo
                src={staticFile(reaction)}
                muted
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </Loop>
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
