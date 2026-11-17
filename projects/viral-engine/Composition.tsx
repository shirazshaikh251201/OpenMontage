import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Caption, createTikTokStyleCaptions, TikTokPage } from "@remotion/captions";

// ---------------------------------------------------------------------------
// VIRAL ENGINE — one composition, driven entirely by props.json.
//
// Nothing here is specific to a single video. The Python pipeline hands it:
//   - a speed-ramped screen recording
//   - detected beat times (where to punch in)
//   - word-level captions from the narration
//   - a hook, a CTA, an audio track
// Swap the props, get a different video. That is what makes 100/month work.
// ---------------------------------------------------------------------------

// Sampled from the iOS app itself. The product has NO blue anywhere — the
// only colour it uses is the correction green on an applied fix, and a muted
// red on a struck-through error. Everything else is black / white / warm off-white.
const CREAM = "#F6F0EC";   // the app's own warm off-white
const INK = "#0B0B10";     // app icon, headlines
const ACCENT = "#21C165";  // the ✓Applied tick — "this got fixed"
const ERROR = "#A04641";   // strikethrough on an error

const SERIF = "'TB Playfair', Georgia, serif";
const SANS = "'TB Inter', system-ui, sans-serif";

const fontFace = (family: string, file: string, weight: number) =>
  `@font-face{font-family:'${family}';font-style:normal;font-weight:${weight};font-display:block;src:url(${staticFile(
    `fonts/${file}.woff2`
  )}) format('woff2');}`;

const FontFaces: React.FC = () => (
  <style
    dangerouslySetInnerHTML={{
      __html: [
        fontFace("TB Playfair", "playfair500", 500),
        fontFace("TB Playfair", "playfair600", 600),
        fontFace("TB Inter", "inter500", 500),
        fontFace("TB Inter", "inter600", 600),
      ].join(""),
    }}
  />
);

export interface Hook {
  /** Big line that must land in the first 2 seconds. */
  text: string;
  sub?: string;
  durationInFrames: number;
}

export interface ZoomBeat {
  /** seconds into the composition */
  t: number;
  scale: number;
}

export interface FeatureLabel {
  text: string;
  index: number;
  count: number;
  fromFrame: number;
  toFrame: number;
}

export interface Presenter {
  /** Talking-head clip in public/ (creator or AI avatar), audio stripped. */
  src: string;
  /** Frames the presenter fills the screen before cutting to the demo. */
  introFrames: number;
}

export interface SceneProps {
  /** Matches the recording's appearance; light footage gets a light band and dark text. */
  theme?: "dark" | "light";
  /** Creator / avatar ad: presenter opens full-frame, then sits in a bubble over the demo. */
  presenter?: Presenter;
  /** Section markers for multi-feature promos. Omit for single-clip videos. */
  labels?: FeatureLabel[];
  video: string;
  videoDurationInFrames: number;
  hook: Hook;
  captions: Caption[];
  zooms: ZoomBeat[];
  audio?: string | null;
  cta: {
    durationInFrames: number;
    wordmark: string;
    line: string;
    store: string;
    icon: string;
  };
  fps: number;
}

/* ------------------------------ hook card ------------------------------ */

const HookCard: React.FC<{ hook: Hook; fps: number }> = ({ hook, fps }) => {
  const frame = useCurrentFrame();
  // No fade-in: frame 1 already carries the message. A hook that fades is a
  // hook that lost its first 6 frames.
  const pop = spring({ frame, fps, config: { damping: 200, mass: 0.5, stiffness: 220 } });
  const out = interpolate(
    frame,
    [hook.durationInFrames - 7, hook.durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 700,
          background: `linear-gradient(180deg, ${CREAM} 0%, ${CREAM} 68%, ${CREAM}00 100%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 150,
          left: 64,
          right: 64,
          textAlign: "center",
          transform: `scale(${0.96 + pop * 0.04})`,
        }}
      >
        <div
          style={{
            fontFamily: SERIF,
            fontWeight: 600,
            fontSize: 92,
            lineHeight: 1.0,
            letterSpacing: "-0.02em",
            color: INK,
            whiteSpace: "pre-line",
          }}
        >
          {hook.text}
        </div>
        {hook.sub ? (
          <div
            style={{
              marginTop: 24,
              fontFamily: SANS,
              fontWeight: 500,
              fontSize: 36,
              color: INK,
              opacity: 0.62,
            }}
          >
            {hook.sub}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/* ---------------------------- feature label ---------------------------- */

// Names the feature on screen in a multi-feature promo. Sits on an ink band at
// the very top, which also covers the chat app's own notice text.
const FeatureLabelLayer: React.FC<{ labels: FeatureLabel[]; fps: number; light?: boolean }> = ({ labels, fps, light }) => {
  const frame = useCurrentFrame();
  const label = labels.find((l) => frame >= l.fromFrame && frame < l.toFrame);
  if (!label) return null;
  const enter = spring({
    frame: frame - label.fromFrame,
    fps,
    config: { damping: 200, mass: 0.5, stiffness: 220 },
  });
  return (
    <AbsoluteFill>

      <div
        style={{
          position: "absolute",
          top: 44,
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: enter,
          transform: `translateY(${(1 - enter) * -16}px)`,
        }}
      >
        <div
          style={{
            fontFamily: SANS,
            fontWeight: 600,
            fontSize: 26,
            letterSpacing: "0.14em",
            color: ACCENT,
          }}
        >
          {label.index} / {label.count}
        </div>
        <div
          style={{
            marginTop: 8,
            fontFamily: SERIF,
            fontWeight: 600,
            fontSize: 74,
            lineHeight: 1.05,
            letterSpacing: "-0.02em",
            color: light ? INK : CREAM,
          }}
        >
          {label.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------- top band -------------------------------- */

// Ink band behind labels and captions. Covers the chat's old history (missed
// calls, deleted-message chips) and gives the text a clean ground.
const TopBand: React.FC<{ height: number; light?: boolean }> = ({ height, light }) => {
  const c = light ? CREAM : INK;
  return (
  <AbsoluteFill>
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height,
        background: `linear-gradient(180deg, ${c} 0%, ${c} 80%, ${c}00 100%)`,
      }}
    />
  </AbsoluteFill>
  );
};

/* ---------------------------- karaoke captions ---------------------------- */

const CaptionLayer: React.FC<{
  pages: TikTokPage[];
  fps: number;
  withLabels: boolean;
  /** creator ads: lower third while the presenter is full-frame, then the band */
  presenterIntroFrames?: number;
  light?: boolean;
}> = ({ pages, fps, withLabels, presenterIntroFrames, light }) => {
  const frame = useCurrentFrame();
  const ms = (frame / fps) * 1000;
  const page = pages.find((p) => ms >= p.startMs && ms < p.startMs + p.durationMs);
  if (!page) return null;
  const inkText =
    Boolean(light) && !(presenterIntroFrames !== undefined && frame < presenterIntroFrames);

  const enter = spring({
    frame: frame - (page.startMs / 1000) * fps,
    fps,
    config: { damping: 200, mass: 0.4, stiffness: 240 },
  });

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          // Sits in the ink band at the top of the frame. The redesigned
          // recordings have a real conversation above the message field (the
          // incoming message gives the reply its context), so the chat area is
          // no longer blank. The top ~400px only holds old history (missed
          // calls, date chips), which the band covers. Never put captions over
          // the keyboard or the message being fixed.
          top:
            presenterIntroFrames !== undefined && frame < presenterIntroFrames
              ? 1260
              : withLabels
              ? 236
              : 150,
          left: 56,
          // leave room for the presenter bubble in the top-right corner
          right: presenterIntroFrames !== undefined && frame >= presenterIntroFrames ? 330 : 56,
          textAlign: "center",
          transform: `translateY(${(1 - enter) * 18}px) scale(${0.96 + enter * 0.04})`,
        }}
      >
        <span
          style={{
            fontFamily: SANS,
            fontWeight: 600,
            fontSize: 62,
            lineHeight: 1.18,
            // on the light band: ink text with a cream stroke; over the
            // presenter's face or dark footage: white text with an ink stroke
            color: inkText ? INK : "#FFFFFF",
            WebkitTextStroke: `14px ${inkText ? CREAM : INK}`,
            paintOrder: "stroke",
          }}
        >
          {page.tokens.map((t, i) => {
            const active = ms >= t.fromMs && ms < t.toMs;
            return (
              <span key={i} style={{ whiteSpace: "pre", color: active ? ACCENT : inkText ? INK : "#FFFFFF" }}>
                {t.text}
              </span>
            );
          })}
        </span>
      </div>
    </AbsoluteFill>
  );
};

/* ------------------------------ the footage ------------------------------ */

const Footage: React.FC<{ src: string; zooms: ZoomBeat[]; fps: number }> = ({ src, zooms, fps }) => {
  const frame = useCurrentFrame();
  const t = frame / fps;

  // Punch in briefly on each detected beat, then ease back. This is the
  // "editor noticed something happened" move, applied automatically.
  let scale = 1.0;
  for (const z of zooms) {
    const d = t - z.t;
    if (d >= -0.18 && d <= 1.25) {
      const p =
        d < 0
          ? interpolate(d, [-0.18, 0], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
          : interpolate(d, [0, 0.35, 1.25], [1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      scale = Math.max(scale, 1 + (z.scale - 1) * p);
    }
  }

  return (
    <AbsoluteFill style={{ background: INK, overflow: "hidden" }}>
      <OffthreadVideo
        src={staticFile(src)}
        style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})` }}
        muted
      />
    </AbsoluteFill>
  );
};

/* ------------------------------- presenter ------------------------------- */

// Full-frame talking head for the hook, then a round bubble in the top band so
// the face stays on screen while the demo plays.
const PresenterFull: React.FC<{ src: string }> = ({ src }) => (
  <AbsoluteFill style={{ background: INK }}>
    <OffthreadVideo src={staticFile(src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </AbsoluteFill>
);

const PresenterBubble: React.FC<{ src: string; startFrom: number; fps: number }> = ({ src, startFrom, fps }) => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps, config: { damping: 200, mass: 0.5, stiffness: 220 } });
  const size = 250;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: 70,
          right: 44,
          width: size,
          height: size,
          borderRadius: "50%",
          overflow: "hidden",
          border: `6px solid ${CREAM}`,
          boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
          transform: `scale(${0.6 + s * 0.4})`,
          opacity: s,
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFrom}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    </AbsoluteFill>
  );
};

/* --------------------------------- CTA --------------------------------- */

const Cta: React.FC<{ cta: SceneProps["cta"]; fps: number }> = ({ cta, fps }) => {
  const frame = useCurrentFrame();
  const s = spring({ frame, fps, config: { damping: 13, mass: 0.7, stiffness: 160 } });
  const fade = (a: number, b: number) =>
    interpolate(frame, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill
      style={{ background: CREAM, alignItems: "center", justifyContent: "center", flexDirection: "column" }}
    >
      <Img
        src={staticFile(cta.icon)}
        style={{
          width: 272,
          height: 272,
          borderRadius: 61,
          transform: `scale(${0.86 + s * 0.14})`,
          opacity: Math.min(1, s * 1.6),
          marginTop: -70,
        }}
      />
      <div
        style={{
          marginTop: 48,
          fontFamily: SERIF,
          fontWeight: 600,
          fontSize: 96,
          letterSpacing: "-0.02em",
          color: INK,
          opacity: fade(6, 18),
          transform: `translateY(${(1 - fade(6, 18)) * 20}px)`,
        }}
      >
        {cta.wordmark}
      </div>
      <div style={{ marginTop: 26, fontFamily: SANS, fontWeight: 600, fontSize: 38, color: ACCENT, opacity: fade(16, 30) }}>
        {cta.line}
      </div>
      <div
        style={{
          marginTop: 36,
          fontFamily: SANS,
          fontWeight: 500,
          fontSize: 29,
          letterSpacing: "0.04em",
          color: INK,
          opacity: 0.5 * fade(28, 44),
        }}
      >
        {cta.store}
      </div>
    </AbsoluteFill>
  );
};

/* -------------------------------- scene -------------------------------- */

export const Scene: React.FC<SceneProps> = ({
  video, videoDurationInFrames, hook, captions, zooms, audio, cta, fps, labels, presenter, theme,
}) => {
  const light = theme === "light";
  const intro = presenter?.introFrames ?? 0;
  const pages = useMemo(() => {
    // Page each script line on its own, so a page never ends with the first
    // word of the next sentence.
    const byLine = new Map<number, Caption[]>();
    for (const c of captions ?? []) {
      const line = (c as Caption & { line?: number }).line ?? 0;
      byLine.set(line, [...(byLine.get(line) ?? []), c]);
    }
    return [...byLine.keys()]
      .sort((a, b) => a - b)
      .flatMap(
        (line) =>
          createTikTokStyleCaptions({
            captions: byLine.get(line)!,
            // ~1.2s per page keeps 3-5 words on screen: readable at thumb
            // distance, still fast enough to feel native.
            combineTokensWithinMilliseconds: 1200,
          }).pages
      );
  }, [captions]);

  return (
    <AbsoluteFill style={{ background: INK }}>
      <FontFaces />
      {audio ? <Audio src={staticFile(audio)} /> : null}

      <Sequence from={intro} durationInFrames={videoDurationInFrames - intro} name="footage">
        <Footage src={video} zooms={zooms ?? []} fps={fps} />
      </Sequence>

      {presenter ? (
        <Sequence from={0} durationInFrames={intro} name="presenter">
          <PresenterFull src={presenter.src} />
        </Sequence>
      ) : null}

      <Sequence from={intro} durationInFrames={videoDurationInFrames - intro} name="band">
        <TopBand height={labels?.length ? 430 : 360} light={light} />
      </Sequence>

      {labels?.length ? (
        <Sequence from={0} durationInFrames={videoDurationInFrames} name="labels">
          <FeatureLabelLayer labels={labels} fps={fps} light={light} />
        </Sequence>
      ) : null}

      {hook.durationInFrames > 0 ? (
        <Sequence from={0} durationInFrames={hook.durationInFrames} name="hook">
          <HookCard hook={hook} fps={fps} />
        </Sequence>
      ) : null}

      <Sequence from={0} durationInFrames={videoDurationInFrames} name="captions">
        <CaptionLayer
          pages={pages}
          fps={fps}
          withLabels={Boolean(labels?.length)}
          presenterIntroFrames={presenter ? intro : undefined}
          light={light}
        />
      </Sequence>

      {presenter ? (
        <Sequence from={intro} durationInFrames={videoDurationInFrames - intro} name="presenter-bubble">
          <PresenterBubble src={presenter.src} startFrom={intro} fps={fps} />
        </Sequence>
      ) : null}

      <Sequence from={videoDurationInFrames} durationInFrames={cta.durationInFrames} name="cta">
        <Cta cta={cta} fps={fps} />
      </Sequence>
    </AbsoluteFill>
  );
};

export const calculateMetadata: CalculateMetadataFunction<SceneProps> = async ({ props }) => ({
  durationInFrames: (props.videoDurationInFrames ?? 0) + (props.cta?.durationInFrames ?? 0) || 600,
  fps: props.fps ?? 30,
  width: 1080,
  height: 1920,
});
