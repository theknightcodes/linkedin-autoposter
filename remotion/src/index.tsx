import React from "react";
import { Composition, registerRoot } from "remotion";
import { PostCard, PostCardProps } from "./PostCard";

// Default props used for Remotion Studio preview
const defaultProps: PostCardProps = {
  headline: "Most engineers misuse LLM context — here's the fix",
  insight:
    "Truncate from the middle, never the end. Keep system prompt + last 3 turns intact.",
  topic: "ai_tips",
  author: "Principal Data & AI Architect",
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PostCard"
      component={PostCard}
      durationInFrames={1}
      fps={30}
      // 1200x627 — LinkedIn recommended OG image size
      width={1200}
      height={627}
      defaultProps={defaultProps}
    />
  );
};

registerRoot(RemotionRoot);
