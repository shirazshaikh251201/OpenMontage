import { Composition } from "remotion";
import { Scene, calculateMetadata, SceneProps } from "./Composition";
import { SplitMeme, calculateSplitMetadata, SplitProps } from "./SplitMeme";
import { ChatMock, calculateChatMetadata, ChatProps } from "./ChatMock";

const fallback = {
  video: "", videoDurationInFrames: 300, captions: [], zooms: [], audio: null, fps: 30,
  hook: { text: "", durationInFrames: 66 },
  cta: { durationInFrames: 120, wordmark: "", line: "", store: "", icon: "" },
} as unknown as SceneProps;

export const Root: React.FC = () => (
  <>
  <Composition
    id="ViralEngine"
    component={Scene}
    durationInFrames={600}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={fallback}
    calculateMetadata={calculateMetadata}
  />
  <Composition
    id="SplitMeme"
    component={SplitMeme}
    durationInFrames={600}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{} as unknown as SplitProps}
    calculateMetadata={calculateSplitMetadata}
  />
  <Composition
    id="ChatMock"
    component={ChatMock}
    durationInFrames={600}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={{} as unknown as ChatProps}
    calculateMetadata={calculateChatMetadata}
  />
  </>
);
