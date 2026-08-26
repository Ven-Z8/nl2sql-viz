/**
 * Rendered instead of the whole app when the deployment was built without
 * NEXT_PUBLIC_API_URL. Honest failure: no silent localhost fallback.
 */
export default function SetupRequired() {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-paper)",
        padding: "var(--space-6)",
      }}
    >
      <div
        style={{
          maxWidth: "520px",
          width: "100%",
          border: "1px solid var(--color-border-subtle)",
          borderRadius: "var(--radius-lg)",
          background: "var(--color-paper-2)",
          padding: "var(--space-8) var(--space-8)",
          textAlign: "center",
        }}
      >
        <span
          style={{
            display: "inline-grid",
            placeItems: "center",
            width: "44px",
            height: "44px",
            borderRadius: "12px",
            background: "var(--color-accent-dim)",
            color: "var(--color-accent)",
            fontSize: "20px",
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            marginBottom: "var(--space-5)",
          }}
          aria-hidden
        >
          ◈
        </span>
        <h1
          style={{
            fontSize: "20px",
            fontWeight: 700,
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            margin: "0 0 var(--space-3)",
          }}
        >
          Setup required
        </h1>
        <p
          style={{
            fontSize: "13.5px",
            lineHeight: 1.65,
            color: "var(--color-ink-dim)",
            margin: "0 0 var(--space-5)",
          }}
        >
          This build of DataLens AI has no backend URL configured, so it can&apos;t
          reach a query engine. Set{" "}
          <code
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              color: "var(--color-ink)",
              background: "var(--color-paper-3)",
              padding: "2px 6px",
              borderRadius: "6px",
            }}
          >
            NEXT_PUBLIC_API_URL
          </code>{" "}
          to your API origin and rebuild:
        </p>
        <pre
          style={{
            textAlign: "left",
            fontSize: "12px",
            lineHeight: 1.7,
            fontFamily: "var(--font-mono)",
            color: "var(--color-ink-dim)",
            background: "var(--color-paper-3)",
            border: "1px solid var(--color-border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "12px 16px",
            overflowX: "auto",
            margin: "0",
          }}
        >
          {`NEXT_PUBLIC_API_URL=https://your-backend.example.com \\
  npm run build`}
        </pre>
      </div>
    </div>
  );
}
