import React from "react";
import { AbsoluteFill } from "remotion";

// Topic → accent color mapping (matches TOPIC_CATEGORIES in config.py)
const TOPIC_COLORS: Record<string, string> = {
  ai_tips: "#6366f1",              // indigo
  claude_features: "#f59e0b",      // amber
  copilot_tricks: "#10b981",       // emerald
  data_engineering_ai: "#3b82f6",  // blue
  lessons_learned: "#ec4899",      // pink
};

const TOPIC_LABELS: Record<string, string> = {
  ai_tips: "AI Tips & Tricks",
  claude_features: "Claude Features",
  copilot_tricks: "GitHub Copilot",
  data_engineering_ai: "Data Engineering + AI",
  lessons_learned: "Lessons Learned",
};

export interface PostCardProps {
  headline: string;
  insight: string;
  topic: string;
  author?: string;
}

export const PostCard: React.FC<PostCardProps> = ({
  headline,
  insight,
  topic,
  author = "Principal Data & AI Architect",
}) => {
  const accent = TOPIC_COLORS[topic] ?? "#6366f1";
  const topicLabel = TOPIC_LABELS[topic] ?? topic;

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%)",
        fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        padding: "72px 80px",
        justifyContent: "space-between",
      }}
    >
      {/* Grid pattern overlay */}
      <AbsoluteFill
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.04) 1px, transparent 0)",
          backgroundSize: "40px 40px",
          pointerEvents: "none",
        }}
      />

      {/* Glow accent */}
      <div
        style={{
          position: "absolute",
          top: -120,
          right: -80,
          width: 480,
          height: 480,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}22 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* Top: Topic badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div
          style={{
            background: `${accent}22`,
            border: `1.5px solid ${accent}66`,
            borderRadius: 8,
            padding: "8px 20px",
            color: accent,
            fontSize: 22,
            fontWeight: 600,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {topicLabel}
        </div>
      </div>

      {/* Middle: Headline */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 32,
          paddingTop: 48,
          paddingBottom: 48,
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            width: 56,
            height: 4,
            borderRadius: 2,
            background: accent,
          }}
        />

        <div
          style={{
            color: "#ffffff",
            fontSize: headline.length > 60 ? 52 : 64,
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.02em",
            maxWidth: "85%",
          }}
        >
          {headline}
        </div>

        {insight ? (
          <div
            style={{
              color: "rgba(255,255,255,0.65)",
              fontSize: 28,
              lineHeight: 1.55,
              maxWidth: "78%",
              fontWeight: 400,
            }}
          >
            {insight}
          </div>
        ) : null}
      </div>

      {/* Bottom: Author + brand */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid rgba(255,255,255,0.08)",
          paddingTop: 28,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {/* Avatar circle */}
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "50%",
              background: `linear-gradient(135deg, ${accent}, ${accent}88)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 22,
              fontWeight: 700,
            }}
          >
            D
          </div>
          <div>
            <div style={{ color: "#fff", fontSize: 22, fontWeight: 600 }}>
              Dhamodharan Palanisamy
            </div>
            <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 18 }}>
              {author}
            </div>
          </div>
        </div>

        {/* LinkedIn wordmark area */}
        <div
          style={{
            color: "rgba(255,255,255,0.25)",
            fontSize: 18,
            fontWeight: 500,
            letterSpacing: "0.08em",
          }}
        >
          linkedin-autoposter
        </div>
      </div>
    </AbsoluteFill>
  );
};
