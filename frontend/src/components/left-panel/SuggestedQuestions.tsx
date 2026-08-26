"use client";
import { useState } from "react";
import { SECTION_LABEL } from "./shared";
import type { SuggestedQuestion } from "@/lib/types";

type TierKey = NonNullable<SuggestedQuestion["tier"]>;

/** Fixed presentation order: Easy → Medium → Hard → Very hard. */
const TIER_GROUPS: { key: TierKey; label: string; color: string }[] = [
  { key: "easy", label: "Easy", color: "#4ade80" },
  { key: "medium", label: "Medium", color: "#facc15" },
  { key: "hard", label: "Hard", color: "#fb923c" },
  { key: "very_complex", label: "Very hard", color: "#f87171" },
];

/** Progressive disclosure (F2): Easy starts open, every later tier collapsed. */
const INITIAL_OPEN: Record<TierKey, boolean> = {
  easy: true,
  medium: false,
  hard: false,
  very_complex: false,
};

const QUESTION_BUTTON: React.CSSProperties = {
  width: "100%",
  textAlign: "left",
  padding: "10px 12px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--color-border-subtle)",
  background: "var(--color-paper-3)",
  color: "var(--color-ink)",
  marginBottom: "var(--space-2)",
  transition:
    "transform var(--dur-fast) var(--ease-out), border-color var(--dur-fast)",
};

/** Subtle "this is what you last ran" treatment (F3). Token-based, so it
 *  re-resolves correctly under [data-theme="dark"]. */
const QUESTION_ACTIVE: React.CSSProperties = {
  borderColor: "var(--color-accent)",
  background:
    "color-mix(in srgb, var(--color-accent) 9%, var(--color-paper-3))",
};

const TIER_HEADER_BUTTON: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
  width: "100%",
  textAlign: "left",
  padding: "3px 2px",
  margin: "0 0 6px",
  background: "transparent",
  border: "none",
  cursor: "pointer",
};

const COUNT_CHIP: React.CSSProperties = {
  fontSize: "10px",
  fontWeight: 600,
  fontFamily: "var(--font-mono)",
  color: "var(--color-ink-dim)",
  background: "var(--color-paper-3)",
  border: "1px solid var(--color-border-subtle)",
  borderRadius: "var(--radius-sm)",
  padding: "1px 7px",
  lineHeight: 1.4,
};

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      aria-hidden="true"
      focusable="false"
      style={{
        flexShrink: 0,
        color: "var(--color-ink-faint)",
        transform: open ? "rotate(90deg)" : "rotate(0deg)",
        transition: "transform var(--dur-fast) var(--ease-out)",
      }}
    >
      <polyline
        points="3.5,2 6.5,5 3.5,8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** One suggested-question button, shared by tiered + demo lists. Keeps the
 *  last-clicked question highlighted (F3); ids/ask flow unchanged (F4). */
function QuestionButton({
  item,
  isLoading,
  isActive,
  onAsk,
}: {
  item: SuggestedQuestion;
  isLoading: boolean;
  isActive: boolean;
  onAsk: (id: string, question: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onAsk(item.id, item.question)}
      disabled={isLoading}
      aria-current={isActive ? "true" : undefined}
      style={{
        ...QUESTION_BUTTON,
        cursor: isLoading ? "not-allowed" : "pointer",
        opacity: isLoading ? 0.55 : 1,
        ...(isActive ? QUESTION_ACTIVE : {}),
      }}
      onMouseEnter={(e) => {
        if (!isLoading && !isActive) {
          e.currentTarget.style.transform = "translateY(-1px)";
          e.currentTarget.style.borderColor = "var(--color-accent-dim)";
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        if (!isActive) {
          e.currentTarget.style.borderColor = "var(--color-border-subtle)";
        }
      }}
    >
      {!item.tier && (
        <span
          style={{
            display: "block",
            fontSize: "10px",
            fontWeight: 600,
            color: "var(--color-accent)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: "3px",
          }}
        >
          {item.category}
        </span>
      )}
      <span style={{ display: "block", fontSize: "12.5px", lineHeight: 1.45 }}>
        {item.question}
      </span>
    </button>
  );
}

/**
 * Curated questions. When any question carries a tier (dataset mode), the
 * list splits into four collapsible sections in fixed order — each header
 * shows the tier name + count and toggles independently. Demo mode (no tiers
 * anywhere) renders exactly one unlabeled list as before. Visible from first
 * paint (demo questions load without choosing a dataset).
 */
export default function SuggestedQuestions({
  questions,
  isLoading,
  onAsk,
}: {
  questions: SuggestedQuestion[];
  isLoading: boolean;
  onAsk: (q: string) => void;
}) {
  // Component state only (no persistence): which tier sections are expanded,
  // and which question the user last asked (F3).
  const [openTiers, setOpenTiers] = useState<Record<TierKey, boolean>>(INITIAL_OPEN);
  const [activeId, setActiveId] = useState<string | null>(null);

  const hasTiers = questions.some((q) => q.tier);

  const handleAsk = (id: string, question: string) => {
    setActiveId(id);
    onAsk(question);
  };

  if (questions.length === 0) return null;

  return (
    <div
      style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={SECTION_LABEL}>Suggested Analysis</div>

      {hasTiers ? (
        TIER_GROUPS.map((group) => {
          const items = questions.filter((q) => q.tier === group.key);
          if (items.length === 0) return null; // skip empty tiers entirely

          const isOpen = openTiers[group.key];
          const sectionId = `suggested-tier-${group.key}`;
          return (
            <div key={group.key} style={{ marginBottom: "var(--space-3)" }}>
              <button
                type="button"
                onClick={() =>
                  setOpenTiers((prev) => ({
                    ...prev,
                    [group.key]: !prev[group.key],
                  }))
                }
                aria-expanded={isOpen}
                aria-controls={sectionId}
                style={TIER_HEADER_BUTTON}
              >
                <Chevron open={isOpen} />
                <span
                  style={{
                    fontSize: "9.5px",
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: group.color,
                    background: `color-mix(in srgb, ${group.color} 12%, transparent)`,
                    padding: "2px 8px",
                    borderRadius: "var(--radius-sm)",
                  }}
                >
                  {group.label}
                </span>
                <span style={COUNT_CHIP}>{items.length}</span>
              </button>
              <div id={sectionId} hidden={!isOpen}>
                {items.map((item) => (
                  <QuestionButton
                    key={item.id}
                    item={item}
                    isLoading={isLoading}
                    isActive={activeId === item.id}
                    onAsk={handleAsk}
                  />
                ))}
              </div>
            </div>
          );
        })
      ) : (
        <div>
          {questions.map((item) => (
            <QuestionButton
              key={item.id}
              item={item}
              isLoading={isLoading}
              isActive={activeId === item.id}
              onAsk={handleAsk}
            />
          ))}
        </div>
      )}
    </div>
  );
}
