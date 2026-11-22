import React from "react";
import {
  AbsoluteFill,
  Audio,
  CalculateMetadataFunction,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { ACCENT, CREAM, Cta, FontFaces, INK, SANS, SceneProps } from "./Composition";

// ---------------------------------------------------------------------------
// CHAT MOCK — the whole video is drawn in code: no screen recording, no
// generated footage. A generic chat screen (deliberately not WhatsApp's look
// or branding) and a simplified Type Better keyboard play out one scripted
// moment: a message arrives, a bad reply is typed, one tap fixes it, it is
// sent. Every hook, language or skit line is a new video from a text file.
//
// The corrected text must be real Type Better output copied from the app, so
// the ad shows what the product actually does.
// ---------------------------------------------------------------------------

export interface Token {
  t: string;
  /** draft: a word the fix changes (red underline); fixed: a changed word (green) */
  hit?: boolean;
}

export interface ChatMessage {
  from: "them" | "me";
  text: string;
  frame: number;
}

export interface SpokenWord {
  text: string;
  frame: number;
}

export interface ChatProps {
  /** "voice": the scene opens on Type Better's dictation panel already listening */
  mode?: "type" | "voice";
  spokenWords?: SpokenWord[];
  /** frame the fix lands with a jolt (crash zoom + shake + flash) on the phone */
  jolt?: boolean;
  contact: string;
  tool: string;
  messages: ChatMessage[];
  draft: string;
  draftTokens: Token[];
  fixedTokens: Token[];
  typeStart: number;
  typeEnd: number;
  tapFrame: number;
  fixFrame: number;
  sendFrame: number;
  bodyFrames: number;
  headlines: { text: string; check?: boolean; fromFrame: number; toFrame: number }[];
  audio?: string | null;
  cta: SceneProps["cta"];
  fps: number;
}

const RED = "#C2413A";
const PHONE_X = 60;
const PHONE_Y = 360;
const PHONE_W = 960;
const PHONE_H = 1500;
const HEADER_H = 128;
const KEYBOARD_H = 560;
const TOOLBAR_H = 96;
const WALL = "#EFE9E1";
const ME_BUBBLE = "#D9F5E2";

/* ------------------------------- headline ------------------------------- */

const Headline: React.FC<{ headlines: ChatProps["headlines"]; fps: number }> = ({ headlines, fps }) => {
  const frame = useCurrentFrame();
  const h = headlines.find((x) => frame >= x.fromFrame && frame < x.toFrame);
  if (!h) return null;
  // the opening headline is fully on screen from frame 1: no fade-in on the hook
  const s = h.fromFrame === 0 ? 1 : spring({ frame: frame - h.fromFrame, fps, config: { damping: 200, mass: 0.5, stiffness: 240 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 60,
        right: 60,
        height: PHONE_Y - 20,
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
              fontSize: 40,
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

/* -------------------------------- bubbles -------------------------------- */

const Bubble: React.FC<{ m: ChatMessage; fps: number }> = ({ m, fps }) => {
  const frame = useCurrentFrame();
  // messages already in the chat at the cold open don't animate in
  const s = m.frame === 0 ? 1 : spring({ frame: frame - m.frame, fps, config: { damping: 16, mass: 0.6, stiffness: 200 } });
  const me = m.from === "me";
  return (
    <div style={{ display: "flex", justifyContent: me ? "flex-end" : "flex-start", margin: "10px 26px" }}>
      <div
        style={{
          maxWidth: 680,
          background: me ? ME_BUBBLE : "#fff",
          borderRadius: 30,
          borderBottomRightRadius: me ? 8 : 30,
          borderBottomLeftRadius: me ? 30 : 8,
          padding: "20px 28px",
          fontFamily: SANS,
          fontWeight: 500,
          fontSize: 38,
          lineHeight: 1.3,
          color: INK,
          boxShadow: "0 2px 6px rgba(11,11,16,0.08)",
          transform: `scale(${0.85 + 0.15 * s}) translateY(${(1 - s) * 30}px)`,
          transformOrigin: me ? "bottom right" : "bottom left",
          opacity: Math.min(1, s * 1.5),
        }}
      >
        {m.text}
        {me ? <span style={{ color: ACCENT, fontSize: 28, marginLeft: 12 }}>✓✓</span> : null}
      </div>
    </div>
  );
};

/* ------------------------------- input field ------------------------------ */

const InputField: React.FC<{ p: ChatProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  const caret = Math.floor(frame / 15) % 2 === 0;
  let content: React.ReactNode = null;

  if (p.mode === "voice" && frame < p.fixFrame) {
    content = null;
  } else if (frame < p.typeStart || frame >= p.sendFrame) {
    content = null;
  } else if (frame < p.typeEnd) {
    const n = Math.floor(interpolate(frame, [p.typeStart, p.typeEnd], [0, p.draft.length], { extrapolateRight: "clamp" }));
    content = p.draft.slice(0, n);
  } else if (frame < p.fixFrame) {
    // typed: the words the fix will change get a red squiggle
    content = p.draftTokens.map((tk, i) => (
      <span
        key={i}
        style={
          tk.hit
            ? { textDecoration: "underline wavy", textDecorationColor: RED, textUnderlineOffset: 8, textDecorationThickness: 3 }
            : undefined
        }
      >
        {tk.t}
      </span>
    ));
  } else {
    const glow = interpolate(frame, [p.fixFrame, p.fixFrame + 40], [1, 0.35], { extrapolateRight: "clamp" });
    content = p.fixedTokens.map((tk, i) => (
      <span key={i} style={tk.hit ? { background: `rgba(33,193,101,${0.32 * glow})`, borderRadius: 8 } : undefined}>
        {tk.t}
      </span>
    ));
  }

  const working = frame >= p.tapFrame && frame < p.fixFrame;
  const shimmer = working ? 0.35 + 0.25 * Math.sin((frame - p.tapFrame) / 3) : 0;
  const empty = content === null || content === "";

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 18, padding: "16px 22px", background: WALL }}>
      <div style={{ fontSize: 54, color: "#8a8a92", lineHeight: "70px", width: 40, textAlign: "center" }}>+</div>
      <div
        style={{
          flex: 1,
          minHeight: 78,
          background: "#fff",
          borderRadius: 40,
          padding: "16px 28px",
          fontFamily: SANS,
          fontWeight: 500,
          fontSize: 38,
          lineHeight: 1.32,
          color: INK,
          position: "relative",
          overflow: "hidden",
          boxShadow: working ? `0 0 0 4px rgba(33,193,101,${shimmer})` : "none",
        }}
      >
        {empty ? (
          <span style={{ color: "#a3a3aa" }}>{p.mode === "voice" && frame < p.fixFrame ? "Listening…" : "Message"}</span>
        ) : (
          content
        )}
        {!working && frame < p.sendFrame && frame >= p.typeStart ? (
          <span style={{ display: "inline-block", width: 4, height: 44, background: ACCENT, marginLeft: 2, verticalAlign: "-8px", opacity: caret ? 1 : 0 }} />
        ) : null}
      </div>
      <div
        style={{
          width: 78,
          height: 78,
          borderRadius: "50%",
          background: ACCENT,
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 36,
          transform: `scale(${frame >= p.sendFrame - 6 && frame < p.sendFrame + 4 ? 0.85 : 1})`,
        }}
      >
        ➤
      </div>
    </div>
  );
};

/* -------------------------------- toolbar --------------------------------- */

const Toolbar: React.FC<{ p: ChatProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  const tools = [p.tool, ...["Fix grammar", "Tone", "Shorten", "Reply"].filter((t) => t !== p.tool)].slice(0, 3);
  const pressed = frame >= p.tapFrame - 4 && frame < p.tapFrame + 6;
  const working = frame >= p.tapFrame && frame < p.fixFrame;
  const done = frame >= p.fixFrame && frame < p.sendFrame;
  return (
    <div
      style={{
        height: TOOLBAR_H,
        background: "#D5D8DE",
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "0 20px",
        fontFamily: SANS,
        fontWeight: 600,
        fontSize: 30,
      }}
    >
      <span style={{ fontSize: 36, marginRight: 4 }}>✦</span>
      {done ? (
        <span style={{ color: ACCENT, fontSize: 32 }}>✓ Applied</span>
      ) : working ? (
        <span style={{ color: INK, opacity: 0.75 }}>✦ Fixing…</span>
      ) : (
        tools.map((t, i) => (
          <span
            key={t}
            style={{
              padding: "12px 24px",
              borderRadius: 999,
              background: i === 0 ? INK : "#fff",
              color: i === 0 ? CREAM : INK,
              transform: i === 0 && pressed ? "scale(0.9)" : "none",
              boxShadow: i === 0 && pressed ? `0 0 0 8px rgba(33,193,101,0.35)` : "none",
            }}
          >
            {t}
          </span>
        ))
      )}
    </div>
  );
};

/* -------------------------------- keyboard -------------------------------- */

const ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];

const Keyboard: React.FC<{ p: ChatProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  let active = "";
  if (frame >= p.typeStart && frame < p.typeEnd) {
    const n = Math.floor(interpolate(frame, [p.typeStart, p.typeEnd], [0, p.draft.length]));
    active = (p.draft[Math.max(0, n - 1)] || "").toLowerCase();
  }
  const key = (label: string, w: number, on = false, dark = false) => (
    <div
      key={label + w}
      style={{
        width: w,
        height: 96,
        borderRadius: 14,
        background: on ? "#9BA0A8" : dark ? "#AEB3BB" : "#fff",
        boxShadow: "0 2px 0 rgba(0,0,0,0.25)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: SANS,
        fontWeight: 500,
        fontSize: label.length > 1 ? 30 : 42,
        color: INK,
        transform: on ? "translateY(-6px) scale(1.08)" : "none",
      }}
    >
      {label}
    </div>
  );
  return (
    <div style={{ height: KEYBOARD_H - TOOLBAR_H, background: "#D5D8DE", padding: "16px 10px 0" }}>
      {ROWS.map((r, i) => (
        <div key={r} style={{ display: "flex", justifyContent: "center", gap: 10, marginBottom: 14 }}>
          {i === 2 ? key("⇧", 120, false, true) : null}
          {[...r].map((c) => key(c, 84, c === active))}
          {i === 2 ? key("⌫", 120, false, true) : null}
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "center", gap: 10 }}>
        {key("123", 140, false, true)}
        {key("space", 520, active === " ")}
        {key("return", 220, false, true)}
      </div>
    </div>
  );
};

/* ---------------------------- dictation panel ---------------------------- */

// Shown instead of the keyboard while Type Better listens: what is being said
// appears word by word, then "Cleaning up…" before the clean text is inserted.
const DictationPanel: React.FC<{ p: ChatProps }> = ({ p }) => {
  const frame = useCurrentFrame();
  const words = (p.spokenWords ?? []).filter((w) => frame >= w.frame);
  const last = (p.spokenWords ?? []).slice(-1)[0];
  const speaking = words.length > 0 && last && frame < last.frame + 12;
  const cleaning = frame >= p.tapFrame;
  const bars = Array.from({ length: 38 }, (_, i) => {
    const amp = speaking ? 0.35 + 0.65 * Math.abs(Math.sin(frame / 3.1 + i * 0.9) * Math.cos(frame / 5.3 + i * 0.37)) : 0.08;
    return Math.max(6, amp * 110);
  });
  return (
    <div style={{ height: KEYBOARD_H, background: "#F2F2F4", padding: "22px 30px", fontFamily: SANS, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
        <span style={{ background: "#fff", borderRadius: 999, padding: "10px 26px", fontWeight: 600, fontSize: 28, color: INK }}>Dictate</span>
        <span style={{ fontWeight: 500, fontSize: 28, color: "#9a9aa2" }}>Translate</span>
        <span style={{ marginLeft: "auto", fontWeight: 500, fontSize: 26, color: "#6b6b73" }}>✦ Type Better</span>
      </div>
      <div style={{ textAlign: "center", marginTop: 22, fontWeight: 600, fontSize: 30, color: cleaning ? INK : RED }}>
        {cleaning ? "✦ Cleaning up…" : "● Listening"}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 7, height: 130, marginTop: 10, opacity: cleaning ? 0.25 : 1 }}>
        {bars.map((h, i) => (
          <div key={i} style={{ width: 9, height: h, borderRadius: 6, background: INK }} />
        ))}
      </div>
      <div
        style={{
          flex: 1,
          marginTop: 8,
          fontSize: 46,
          lineHeight: 1.25,
          fontWeight: 600,
          color: INK,
          textAlign: "center",
          opacity: cleaning ? 0.35 : 1,
        }}
      >
        {words.map((w) => w.text).join("")}
      </div>
    </div>
  );
};

/* ---------------------------------- scene --------------------------------- */

export const ChatMock: React.FC<ChatProps> = (p) => {
  const frame = useCurrentFrame();
  const shown = p.messages.filter((m) => frame >= m.frame);
  const pop = 1;
  const d = frame - p.fixFrame;
  const jz = !p.jolt || d < 0 ? 1 : d < 3 ? interpolate(d, [0, 3], [1, 1.07]) : d < 18 ? interpolate(d, [3, 18], [1.07, 1]) : 1;
  const sh = p.jolt && d >= 0 && d < 12 ? (12 - d) / 12 : 0;
  const flash = p.jolt && d >= 0 && d < 4 ? interpolate(d, [0, 4], [0.7, 0]) : 0;
  return (
    <AbsoluteFill style={{ background: CREAM }}>
      <FontFaces />
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}

      <Sequence from={0} durationInFrames={p.bodyFrames} name="chat">
        <AbsoluteFill>
          <div
            style={{
              position: "absolute",
              left: PHONE_X,
              top: PHONE_Y,
              width: PHONE_W,
              height: PHONE_H,
              borderRadius: 56,
              overflow: "hidden",
              background: WALL,
              boxShadow: "0 30px 80px rgba(11,11,16,0.22)",
              display: "flex",
              flexDirection: "column",
              transform: `translate(${sh * 16 * Math.sin(d * 2.9)}px, ${sh * 10 * Math.cos(d * 3.4)}px) scale(${pop * jz})`,
            }}
          >
            {/* header */}
            <div
              style={{
                height: HEADER_H,
                background: "#F7F7F5",
                display: "flex",
                alignItems: "center",
                gap: 22,
                padding: "0 30px",
                borderBottom: "1px solid #e4e0da",
                flex: "none",
              }}
            >
              <span style={{ fontSize: 50, color: "#8a8a92" }}>‹</span>
              <div
                style={{
                  width: 76,
                  height: 76,
                  borderRadius: "50%",
                  background: "#E6DCD3",
                  color: INK,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: SANS,
                  fontWeight: 600,
                  fontSize: 36,
                }}
              >
                {p.contact.slice(0, 1).toUpperCase()}
              </div>
              <div style={{ fontFamily: SANS }}>
                <div style={{ fontWeight: 600, fontSize: 38, color: INK }}>{p.contact}</div>
                <div style={{ fontWeight: 500, fontSize: 26, color: "#8a8a92" }}>online</div>
              </div>
            </div>

            {/* messages, bottom-aligned */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", paddingBottom: 12, overflow: "hidden" }}>
              {shown.map((m, i) => (
                <Bubble key={i} m={m} fps={p.fps} />
              ))}
            </div>

            <div style={{ flex: "none" }}>
              <InputField p={p} />
              {p.mode === "voice" && frame < p.fixFrame ? (
                <DictationPanel p={p} />
              ) : (
                <>
                  <Toolbar p={p} />
                  <Keyboard p={p} />
                </>
              )}
            </div>
          </div>

          <Headline headlines={p.headlines} fps={p.fps} />
          <AbsoluteFill style={{ background: "#fff", opacity: flash, pointerEvents: "none" }} />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={p.bodyFrames} durationInFrames={p.cta.durationInFrames} name="cta">
        <Cta cta={p.cta} fps={p.fps} />
      </Sequence>
    </AbsoluteFill>
  );
};

export const calculateChatMetadata: CalculateMetadataFunction<ChatProps> = async ({ props }) => ({
  durationInFrames: (props.bodyFrames ?? 0) + (props.cta?.durationInFrames ?? 0) || 600,
  fps: props.fps ?? 30,
  width: 1080,
  height: 1920,
});
