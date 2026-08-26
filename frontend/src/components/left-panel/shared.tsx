import type { CSSProperties } from "react";
import type { CatalogItem } from "@/lib/types";

export const SECTION_LABEL: CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--color-ink-faint)",
  textTransform: "uppercase",
  letterSpacing: "0.1em",
  marginBottom: "var(--space-3)",
};

export const TAB: CSSProperties = {
  flex: 1,
  padding: "7px 0",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "transparent",
  fontSize: "12px",
  fontWeight: 600,
  cursor: "pointer",
  transition: "background var(--dur-fast) var(--ease-out), color var(--dur-fast)",
};

/** Card used for both sample datasets and relational databases. */
export function DatasetCard({
  item,
  disabled,
  onLoad,
}: {
  item: CatalogItem;
  disabled: boolean;
  onLoad: (id: string) => void;
}) {
  return (
    <button
      key={item.id}
      onClick={() => onLoad(item.id)}
      disabled={disabled}
      style={{
        width: "100%",
        textAlign: "left",
        padding: "10px 12px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border-subtle)",
        background: "var(--color-paper-3)",
        color: "var(--color-ink)",
        marginBottom: "var(--space-2)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        transition: "border-color var(--dur-fast) var(--ease-out)",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            "var(--color-accent-dim)";
        }
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.borderColor =
          "var(--color-border-subtle)";
      }}
    >
      <span style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "2px" }}>
        {item.name}
      </span>
      <span
        style={{
          display: "block",
          fontSize: "11px",
          color: "var(--color-ink-dim)",
          lineHeight: 1.4,
        }}
      >
        {item.description}
      </span>
      <span
        style={{
          display: "inline-block",
          marginTop: "4px",
          fontSize: "10px",
          fontWeight: 600,
          color: "var(--color-accent)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontFamily: "var(--font-mono)",
        }}
      >
        {item.domain} · load →
      </span>
    </button>
  );
}

export const DOMAIN_SELECT: CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: "var(--radius-md)",
  background: "var(--color-paper-3)",
  border: "1px solid var(--color-border)",
  color: "var(--color-ink)",
  fontSize: "12px",
  fontFamily: "inherit",
  outline: "none",
};
