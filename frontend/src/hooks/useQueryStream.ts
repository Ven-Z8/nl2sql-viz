import { useCallback, useEffect, useRef, useState } from "react";
import { QueryWebSocket, type WsStatus } from "@/lib/ws";
import { fmtTime } from "@/lib/format";
import type { LogEntry } from "@/components/LogStream";
import type { PipelineStageState } from "@/components/PipelinePanel";
import type {
  Answer,
  ChartHint,
  HistoryItem,
  ProvenanceEntry,
  QueryEntry,
  ResultEventPayload,
  ResultRow,
} from "@/lib/types";

export type QueryPhase = "idle" | "loading" | "done" | "error";

/** Progress stages where the pipeline visibly corrects itself (Wave-3
 *  execute-inspect-refine loop + cost-gate tightening). Rendered with a
 *  distinct subtle treatment so users perceive the self-correction. */
const SELF_CORRECT_STAGES = new Set(["refine", "cost"]);

/** An inbound `clarify` event parked until the user picks an option. */
export interface PendingClarify {
  question: string;
  options: string[];
  threadId: string | null;
}

export interface ResultMeta {
  rowCount: number;
  executionTimeMs: number;
  cached: boolean;
  chartHint: ChartHint | null;
}

export interface StreamResult {
  title: string;
  rows: ResultRow[];
  sql: string;
  answer: Answer | null;
  queryType: string | null;
  meta: ResultMeta | null;
  /** Contract v2 — null on older payloads; AnswerCard renders as before. */
  provenance: ProvenanceEntry[] | null;
  /** Contract v2 — all synthesized result sets, final first. */
  queries: QueryEntry[];
  /** Contract v3 — threading fields mirrored off the inbound event.
   *  Null/false on pre-v3 payloads and legacy replaced results. */
  threadId: string | null;
  /** Contract v3 — 1-based turn within the thread. */
  turnIndex: number | null;
  /** Contract v3 — true ⇔ the client sent a thread_id on the query. */
  isFollowUp: boolean;
}

/** One follow-up question inside a thread card ("↳ what about 2019?"). */
export interface ThreadFollowUp {
  question: string;
  /** 1-based turn index reported by the backend. */
  turnIndex: number;
}

/**
 * One answer card in the conversation column — a topic plus every follow-up
 * morphed into it. `result` always holds that thread's LATEST result
 * ("last result per thread"); earlier turns survive only as follow-up chips.
 */
export interface ThreadSlot {
  /** Stable React key (synthetic for legacy null-thread slots). */
  key: string;
  threadId: string | null;
  /** The original topic question — the card headline never changes. */
  question: string;
  followUps: ThreadFollowUp[];
  result: StreamResult;
}

interface UseQueryStreamArgs {
  apiKey: string | null;
  connectionId: string | null;
  domain: string;
  focusTable?: string;
}

function completeActiveStages(
  setter: (fn: (prev: Record<string, PipelineStageState>) => Record<string, PipelineStageState>) => void
) {
  const now = Date.now();
  setter((prev) => {
    const next: Record<string, PipelineStageState> = {};
    for (const [k, v] of Object.entries(prev)) {
      next[k] =
        v.status === "active"
          ? { ...v, status: "done", durationMs: now - v.startedAt }
          : v;
    }
    return next;
  });
}

/**
 * Owns the query lifecycle end-to-end: WS connection + reconnection status,
 * progress/pipeline bookkeeping, activity log, result state, error banner
 * state, and query history. The WS contract lives in lib/ws.ts.
 */
export function useQueryStream({
  apiKey,
  connectionId,
  domain,
  focusTable,
}: UseQueryStreamArgs) {
  const [status, setStatus] = useState<WsStatus>("closed");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [pipeline, setPipeline] = useState<Record<string, PipelineStageState>>({});
  const [pipelineEverFired, setPipelineEverFired] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [phase, setPhase] = useState<QueryPhase>("idle");
  const [slots, setSlots] = useState<ThreadSlot[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  /** Thread awaiting a follow-up result; null while a NEW topic is loading. */
  const [loadingThreadId, setLoadingThreadId] = useState<string | null>(null);
  /** Optimistic header title for an in-flight new topic (cleared on result). */
  const [pendingTitle, setPendingTitle] = useState<string | null>(null);
  /** SQL streamed in before the first result of a brand-new topic lands. */
  const [draftSql, setDraftSql] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [pendingClarify, setPendingClarify] = useState<PendingClarify | null>(null);

  const wsRef = useRef<QueryWebSocket | null>(null);
  const isLoadingRef = useRef(false);
  // Mirrors pendingClarify for use inside runQuestion's guard without
  // adding it to the callback's dependency churn.
  const clarifyWaitRef = useRef(false);
  // Mirror of activeThreadId for runQuestion / the result handler.
  const activeThreadIdRef = useRef<string | null>(null);
  // Mirror of loadingThreadId for the inbound sql/result handlers.
  const loadingThreadIdRef = useRef<string | null>(null);
  /** The question most recently sent — headline/follow-up fallback when the
   *  result payload doesn't echo `query`. */
  const lastQuestionRef = useRef("");
  /** Synthetic keys for legacy slots without a backend thread id. */
  const slotSeqRef = useRef(0);

  /** Pipeline moved on (any downstream event) — the clarify pause is over. */
  const clearClarifyWait = useCallback(() => {
    clarifyWaitRef.current = false;
    setPendingClarify(null);
  }, []);

  // ── inbound event handling ─────────────────────────────────
  useEffect(() => {
    if (!apiKey || !connectionId) return;

    const handleEvent = (event: Record<string, unknown>) => {
      if (event.type === "clarify") {
        // Contract v2: pipeline paused; render options until the user picks.
        const rawOptions = Array.isArray(event.options) ? event.options : [];
        setPendingClarify({
          question: String(event.question ?? ""),
          options: rawOptions.map((o) => String(o)),
          threadId: event.thread_id == null ? null : String(event.thread_id),
        });
        clarifyWaitRef.current = true;
        setLogs((prev) => [
          ...prev.map((e) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          ),
          {
            time: fmtTime(),
            icon: "run" as const,
            text: `Clarification needed: ${String(event.question ?? "")}`,
            active: true,
          },
        ]);
        return;
      }

      if (event.type === "progress") {
        clearClarifyWait();
        const msg = event.message as string;
        const stage = event.stage as string | undefined;
        const tokens = (event as { tokens?: number }).tokens;
        if (stage) {
          const stamp = Date.now();
          setPipelineEverFired(true);
          setPipeline((prev) => {
            const next: Record<string, PipelineStageState> = {};
            for (const [k, v] of Object.entries(prev)) {
              next[k] =
                v.status === "active"
                  ? { ...v, status: "done", durationMs: stamp - v.startedAt }
                  : v;
            }
            next[stage] = {
              status: "active",
              detail: msg,
              startedAt: stamp,
              durationMs: 0,
              ...(tokens != null ? { tokens } : {}),
            };
            return next;
          });
        }
        setLogs((prev) => [
          ...prev.map((e) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          ),
          {
            time: fmtTime(),
            icon: "run" as const,
            text: msg,
            active: true,
            ...(stage && SELF_CORRECT_STAGES.has(stage)
              ? { tone: "selfcorrect" as const }
              : {}),
          },
        ]);
        return;
      }

      if (event.type === "sql") {
        clearClarifyWait();
        const rawSql = event.sql as string;
        // Route streamed SQL to its destination: an in-flight follow-up
        // updates its slot directly; a brand-new topic parks it as a draft.
        setDraftSql(null);
        if (loadingThreadIdRef.current) {
          const tid = loadingThreadIdRef.current;
          setSlots((prev) =>
            prev.map((s) =>
              s.threadId === tid ? { ...s, result: { ...s.result, sql: rawSql } } : s
            )
          );
        } else {
          setDraftSql(rawSql);
        }
        setLogs((prev) => [
          ...prev,
          {
            time: fmtTime(),
            icon: "sql" as const,
            text:
              rawSql.slice(0, 40) + (rawSql.length > 40 ? "…" : ""),
            active: false,
          },
        ]);
        return;
      }

      if (event.type === "result") {
        clearClarifyWait();
        setLogs((prev) =>
          prev.map((e) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          )
        );
        completeActiveStages(setPipeline);
        const payload = event as ResultEventPayload & Record<string, unknown>;
        const rows = payload.rows ?? [];

        // ── Contract v3 threading fields ──────────────────────
        const threadId =
          typeof payload.thread_id === "string" && payload.thread_id
            ? payload.thread_id
            : null;
        const turnIndex =
          typeof payload.turn_index === "number" ? payload.turn_index : null;
        const isFollowUp = payload.is_follow_up === true;
        // Pre-v3 backends omit all three — degrade to v2 "replace" semantics.
        const legacyPayload =
          payload.thread_id === undefined &&
          payload.turn_index === undefined &&
          payload.is_follow_up === undefined;

        const echoedQuestion =
          typeof payload.query === "string" && payload.query.trim()
            ? payload.query.trim()
            : lastQuestionRef.current;

        const builtResult: StreamResult = {
          title: echoedQuestion,
          rows,
          sql: payload.sql ?? "",
          answer: payload.answer ?? null,
          queryType:
            ((event.query_type as string | undefined) ?? null),
          provenance: Array.isArray(payload.provenance)
            ? payload.provenance
            : null,
          queries: Array.isArray(payload.queries) ? payload.queries : [],
          meta: {
            rowCount:
              typeof payload.row_count === "number"
                ? payload.row_count
                : rows.length,
            executionTimeMs:
              typeof payload.execution_time_ms === "number"
                ? payload.execution_time_ms
                : 0,
            cached: Boolean(payload.cached),
            chartHint: payload.chart_hint ?? null,
          },
          threadId,
          turnIndex,
          isFollowUp,
        };

        // ── Slot routing: morph vs append vs legacy replace ───
        setSlots((prevSlots) => {
          if (legacyPayload) {
            // v2 semantics: the panel holds exactly one answer card.
            slotSeqRef.current += 1;
            return [
              {
                key: `slot-${slotSeqRef.current}`,
                threadId: null,
                question: echoedQuestion,
                followUps: [],
                result: builtResult,
              },
            ];
          }

          if (isFollowUp && threadId) {
            const i = prevSlots.findIndex((s) => s.threadId === threadId);
            if (i >= 0) {
              // MORPH: same slot, same headline — new data replaces the old
              // and the question joins the follow-up chip list.
              const slot = prevSlots[i];
              const next = prevSlots.slice();
              next[i] = {
                ...slot,
                result: builtResult,
                followUps: [
                  ...slot.followUps,
                  {
                    question: echoedQuestion,
                    turnIndex: turnIndex ?? slot.followUps.length + 2,
                  },
                ],
              };
              return next;
            }
            // Defensive: follow-up for a thread we have no card for — append.
          }

          slotSeqRef.current += 1;
          return [
            ...prevSlots,
            {
              key: `slot-${slotSeqRef.current}`,
              threadId,
              question: echoedQuestion,
              followUps: [],
              result: builtResult,
            },
          ];
        });

        if (legacyPayload) {
          activeThreadIdRef.current = null;
          setActiveThreadId(null);
        } else if (threadId) {
          activeThreadIdRef.current = threadId;
          setActiveThreadId(threadId);
        }
        loadingThreadIdRef.current = null;
        setLoadingThreadId(null);
        setDraftSql(null);
        setPendingTitle(null);

        isLoadingRef.current = false;
        setIsLoading(false);
        setPhase("done");
        return;
      }

      if (event.type === "error") {
        clearClarifyWait();
        setLogs((prev) => [
          ...prev.map((e) =>
            e.active ? { ...e, active: false, icon: "done" as const } : e
          ),
          {
            time: fmtTime(),
            icon: "run" as const,
            text: `Error: ${event.message as string}`,
            active: false,
          },
        ]);
        completeActiveStages(setPipeline);
        loadingThreadIdRef.current = null;
        setLoadingThreadId(null);
        setDraftSql(null);
        setPendingTitle(null);
        setError(String(event.message ?? "Query failed"));
        isLoadingRef.current = false;
        setIsLoading(false);
        setPhase("error");
      }
    };

    const ws = new QueryWebSocket(apiKey, { onEvent: handleEvent });
    const unsubscribe = ws.subscribe(setStatus);
    ws.connect();
    wsRef.current = ws;

    return () => {
      unsubscribe();
      ws.close();
      wsRef.current = null;
      setStatus("closed");
    };
  }, [apiKey, connectionId]);

  // ── outbound ───────────────────────────────────────────────
  const runQuestion = useCallback(
    (
      rawQuestion: string,
      opts?: { continueThread?: boolean }
    ): boolean => {
      const question = rawQuestion.trim();
      if (
        !question ||
        isLoadingRef.current ||
        clarifyWaitRef.current || // pipeline paused on a clarify — answer it first
        !connectionId
      )
        return false;

      // Contract v3: continue the active thread unless the caller opts out
      // (continueThread:false) or there is nothing to continue. "New topic"
      // clears activeThreadId, so plain sends naturally start fresh after it.
      const continueThread =
        opts?.continueThread !== false && activeThreadIdRef.current != null;
      const threadId = continueThread ? activeThreadIdRef.current : null;

      // Reset per-query state (pipeline/logs are per-question; answer cards
      // persist as conversation slots and are only touched by results).
      setLogs([]);
      setPipeline({});
      setPipelineEverFired(false);
      setError(null);
      setDraftSql(null);
      clearClarifyWait();
      isLoadingRef.current = true;
      setIsLoading(true);
      setPhase("loading");
      lastQuestionRef.current = question;

      if (continueThread) {
        // Follow-up: its card morphs in place when the result lands.
        loadingThreadIdRef.current = threadId;
        setLoadingThreadId(threadId);
      } else {
        // New topic: optimistic header title; skeleton appears below cards.
        loadingThreadIdRef.current = null;
        setLoadingThreadId(null);
        setPendingTitle(question);
      }

      setHistory((prev) => [{ query: question, timestamp: fmtTime() }, ...prev]);

      const sent = wsRef.current?.sendQuery(question, {
        connectionId,
        domain,
        focusTable,
        threadId,
      });
      if (!sent) {
        loadingThreadIdRef.current = null;
        setLoadingThreadId(null);
        setPendingTitle(null);
        isLoadingRef.current = false;
        setIsLoading(false);
        setPhase("error");
        setError(
          "Not connected to the backend yet — the connection is still waking up. Try again in a few seconds."
        );
        return false;
      }
      return true;
    },
    [connectionId, domain, focusTable, clearClarifyWait]
  );

  /**
   * Contract v3 — explicit "New topic": clears the active thread so the next
   * question is sent WITHOUT thread_id (backend starts a fresh topic) and
   * appends as a new card. Existing cards stay on screen.
   */
  const startNewTopic = useCallback(() => {
    activeThreadIdRef.current = null;
    setActiveThreadId(null);
  }, []);

  /**
   * Answer the pending clarify (contract v2): send
   * { type:"clarification_response", choice } over the same socket and clear
   * local pause state. Server-side timeout (~120s) covers a dead socket —
   * we always clear so the UI never gets stuck on the card.
   */
  const respondClarify = useCallback(
    (choice: number) => {
      clearClarifyWait();
      wsRef.current?.sendClarificationResponse(choice);
    },
    [clearClarifyWait]
  );

  const dismissError = useCallback(() => setError(null), []);

  const clearHistory = useCallback(() => setHistory([]), []);

  const activeSlot =
    slots.find((s) => s.threadId === activeThreadId) ?? null;

  return {
    status,
    logs,
    pipeline,
    pipelineEverFired,
    isLoading,
    phase,
    /** One card per topic; follow-ups morph their slot in place (v3). */
    slots,
    /** Active conversation thread id (null after "New topic"). */
    activeThreadId,
    /** Turn count of the active thread (0 when no thread is active). */
    threadTurnCount: activeSlot
      ? (activeSlot.result.turnIndex ?? activeSlot.followUps.length + 1)
      : 0,
    /** Thread id whose card is awaiting a follow-up result (null → new topic loading or idle). */
    loadingThreadId,
    /** Optimistic header title while a new topic is in flight. */
    pendingTitle,
    /** SQL streamed in before a brand-new topic's first result arrives. */
    draftSql,
    error,
    dismissError,
    history,
    runQuestion,
    startNewTopic,
    clearHistory,
    pendingClarify,
    respondClarify,
  };
}
