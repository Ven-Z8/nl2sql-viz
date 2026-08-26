import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "@/lib/config";
import type {
  CatalogItem,
  SuggestedQuestion,
  SuggestedTier,
  UploadedDataset,
} from "@/lib/types";

const TIERS: SuggestedTier[] = ["easy", "medium", "hard", "very_complex"];

interface UseWorkspaceArgs {
  enabled: boolean;
  apiKey: string | null;
  /** Called whenever a mutating endpoint returns a fresh connection_id. */
  onConnectionId: (id: string, label?: string) => void;
  /** focus_table handed out by the demo session. */
  initialFocusTable?: string;
}

type Body = Record<string, unknown>;

async function getJson(path: string): Promise<Body> {
  const resp = await fetch(apiUrl(path));
  if (!resp.ok) throw new Error(`GET ${path} failed (${resp.status})`);
  return (await resp.json()) as Body;
}

async function postForm(path: string, fields: Record<string, string | File>): Promise<Body> {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  const resp = await fetch(apiUrl(path), { method: "POST", body: form });
  const body = (await resp.json().catch(() => ({}))) as Body & { detail?: string };
  if (!resp.ok) throw new Error(body.detail ?? `Request failed (${resp.status})`);
  return body;
}

function safeHost(dsnOrUrl: string): string {
  try {
    return new URL(dsnOrUrl).host;
  } catch {
    return dsnOrUrl.slice(0, 32);
  }
}

/**
 * Owns everything catalog/workspace shaped: domains, samples, datasets,
 * suggested questions, the active dataset identity, and the four mutating
 * flows (CSV upload, sample load, dataset load, bring-your-own DSN).
 *
 * First-paint story (F7): curated demo questions are fetched immediately so
 * the landing state is never an empty shell — no dataset load required.
 */
export function useWorkspace({
  enabled,
  apiKey,
  onConnectionId,
  initialFocusTable,
}: UseWorkspaceArgs) {
  const [domains, setDomains] = useState<{ id: string; name: string }[]>([]);
  const [samples, setSamples] = useState<CatalogItem[]>([]);
  const [datasets, setDatasets] = useState<CatalogItem[]>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<SuggestedQuestion[]>([]);
  const [datasetName, setDatasetName] = useState("Postgres Workspace");
  const [activeDomain, setActiveDomain] = useState("general");
  const [focusTable, setFocusTable] = useState<string | undefined>(undefined);
  const [uploadedDataset, setUploadedDataset] = useState<UploadedDataset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Adopt the demo session's focus_table once it arrives.
  useEffect(() => {
    if (initialFocusTable) setFocusTable(initialFocusTable);
  }, [initialFocusTable]);

  // One-shot catalog fetch — independent requests must not kill each other.
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const load = async () => {
      const [questionsRes, domainsRes, samplesRes, datasetsRes] =
        await Promise.allSettled([
          getJson("/api/demo/questions"),
          getJson("/api/domains"),
          getJson("/api/samples"),
          getJson("/api/datasets"),
        ]);
      if (cancelled) return;

      if (questionsRes.status === "fulfilled") {
        const body = questionsRes.value as unknown as {
          dataset?: string;
          questions?: SuggestedQuestion[];
        };
        if (body.dataset) setDatasetName(body.dataset);
        if (Array.isArray(body.questions)) setSuggestedQuestions(body.questions);
      }
      if (domainsRes.status === "fulfilled") {
        const body = domainsRes.value as unknown as {
          domains?: { id: string; name: string }[];
        };
        if (Array.isArray(body.domains)) setDomains(body.domains);
      }
      if (samplesRes.status === "fulfilled") {
        const body = samplesRes.value as unknown as { samples?: CatalogItem[] };
        if (Array.isArray(body.samples)) setSamples(body.samples);
      }
      if (datasetsRes.status === "fulfilled") {
        const body = datasetsRes.value as unknown as { datasets?: CatalogItem[] };
        if (Array.isArray(body.datasets)) setDatasets(body.datasets);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const requireKey = useCallback((): string => {
    if (!apiKey) {
      throw new Error(
        "Not connected yet — the demo session is still starting. Try again in a moment."
      );
    }
    return apiKey;
  }, [apiKey]);

  const adoptFrom = useCallback(
    (body: Body, fallbackLabel?: string) => {
      const connectionId = body.connection_id as string | undefined;
      if (connectionId) onConnectionId(connectionId, fallbackLabel);
    },
    [onConnectionId]
  );

  const runMutation = useCallback(async (fn: () => Promise<void>) => {
    setUploading(true);
    setUploadError(null);
    try {
      await fn();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const uploadCsv = useCallback(
    (file: File, domain: string) =>
      runMutation(async () => {
        if (!file) return;
        const key = requireKey();
        const body = await postForm("/api/upload", {
          api_key: key,
          domain,
          file,
        });
        const tableName = String(body.table_name ?? "");
        setUploadedDataset({
          table_name: tableName,
          row_count: Number(body.row_count ?? 0),
          columns: (body.columns as string[]) ?? [],
          domain: String(body.domain ?? domain),
        });
        setActiveDomain(String(body.domain ?? domain));
        const label = tableName.replace(/^upload_/, "");
        setDatasetName(label);
        adoptFrom(body, label);
      }),
    [adoptFrom, requireKey, runMutation]
  );

  const loadSample = useCallback(
    (sampleId: string) =>
      runMutation(async () => {
        const key = requireKey();
        const body = await postForm(`/api/samples/${encodeURIComponent(sampleId)}/load`, {
          api_key: key,
        });
        const tableName = String(body.table_name ?? "");
        const label = tableName.replace(/^upload_/, "");
        setUploadedDataset({
          table_name: tableName,
          row_count: Number(body.row_count ?? 0),
          columns: (body.columns as string[]) ?? [],
          domain: String(body.domain ?? ""),
        });
        setActiveDomain(String(body.domain ?? ""));
        setDatasetName(label);
        adoptFrom(body, label);
        const questions = (body.questions as string[] | undefined) ?? [];
        if (questions.length > 0) {
          setSuggestedQuestions(
            questions.map((q, i) => ({
              id: `sample-q-${i}`,
              question: q,
              category: String(body.domain ?? ""),
            }))
          );
        }
      }),
    [adoptFrom, requireKey, runMutation]
  );

  const loadDataset = useCallback(
    (datasetId: string) =>
      runMutation(async () => {
        const key = requireKey();
        const body = await postForm(`/api/datasets/${encodeURIComponent(datasetId)}/load`, {
          api_key: key,
        });
        const name = String(body.name ?? "Dataset");
        setActiveDomain(String(body.domain ?? ""));
        setDatasetName(name);
        setUploadedDataset(null);
        // Echo the dataset's focus hub back on queries — without it the
        // schema scope widens to every table in the shared database.
        setFocusTable(String(body.focus_table ?? "") || undefined);
        adoptFrom(body, name);
        const grouped = (body.questions ?? {}) as Record<string, string[]>;
        const tiered = TIERS.flatMap((tier) =>
          (grouped[tier] ?? []).map((q) => ({ q, tier }))
        );
        setSuggestedQuestions(
          tiered.map(({ q, tier }, i) => ({
            id: `ds-q-${i}`,
            question: q,
            category: String(body.domain ?? ""),
            tier,
          }))
        );
      }),
    [adoptFrom, requireKey, runMutation]
  );

  const connectDsn = useCallback(
    (dsn: string) =>
      runMutation(async () => {
        const trimmed = dsn.trim();
        if (!trimmed) return;
        const key = requireKey();
        const resp = await fetch(apiUrl("/api/connections"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: key, dsn: trimmed }),
        });
        const body = (await resp.json().catch(() => ({}))) as Body & { detail?: string };
        if (!resp.ok || !body.connection_id) {
          throw new Error(body.detail ?? "Connection failed");
        }
        setDatasetName("Connected Database");
        setUploadedDataset(null);
        setFocusTable(undefined);
        // Contract: POST /api/connections → { connection_id }.
        onConnectionId(String(body.connection_id), safeHost(trimmed));
      }),
    [onConnectionId, requireKey, runMutation]
  );

  return {
    domains,
    samples,
    datasets,
    suggestedQuestions,
    datasetName,
    activeDomain,
    setActiveDomain,
    focusTable,
    uploadedDataset,
    uploading,
    uploadError,
    uploadCsv,
    loadSample,
    loadDataset,
    connectDsn,
  };
}
