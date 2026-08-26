"use client";

interface BannerProps {
  tone: "info" | "error";
  message: string;
  onDismiss?: () => void;
}

/** Inline status banner used for retry notices and dismissible errors. */
export default function Banner({ tone, message, onDismiss }: BannerProps) {
  const isError = tone === "error";
  return (
    <div
      role={isError ? "alert" : "status"}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "10px 14px",
        borderRadius: "var(--radius-md)",
        border: `1px solid ${isError ? "var(--color-danger)" : "var(--color-accent-dim)"}`,
        background: isError
          ? "color-mix(in srgb, var(--color-danger) 8%, transparent)"
          : "var(--color-accent-dim)",
        fontSize: "12.5px",
        lineHeight: 1.5,
        color: isError ? "var(--color-danger)" : "var(--color-accent)",
        fontWeight: 500,
        animation: "fade-up var(--dur-fast) var(--ease-out) both",
      }}
    >
      <span style={{ flexShrink: 0 }} aria-hidden>
        {isError ? "⚠" : "◈"}
      </span>
      <span style={{ flex: 1 }}>{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "inherit",
            fontSize: "13px",
            padding: "2px 6px",
            borderRadius: "var(--radius-sm)",
            flexShrink: 0,
            fontFamily: "var(--font-mono)",
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}
