// Types mirrored from core/state.py. Hand-maintained for Day-2; in a
// longer-lived codebase these would be generated from the Pydantic
// schemas via openapi or a shared tool.

export type AgentName =
  | "orchestrator"
  | "normalizer"
  | "retriever"
  | "drafter"
  | "verifier";

export interface TraceEvent {
  timestamp: string; // ISO-8601
  agent: AgentName;
  event_type: string;
  payload: Record<string, unknown>;
  tokens_used: number;
  latency_ms: number;
}

export type CurrencyStatus =
  | "current"
  | "superseded"
  | "aging"
  | "unknown"
  | "withdrawn";

export interface Citation {
  key: string;
  doc_id: string;
  page: number;
  section_slug: string;
  chunk_text: string;
}

export interface CurrencyFlag {
  citation_key: string;
  status: CurrencyStatus;
  source_year: number;
  superseding_doc_id: string | null;
  note_id: string | null;
}

export type RefusalReason =
  | "out_of_medical_scope"
  | "corpus_silent"
  | "all_superseded_no_current"
  | "citations_unverifiable"
  | "patient_specific_request"
  | "retrieval_budget_exhausted"
  | "drafter_budget_exhausted"
  | "verifier_budget_exhausted"
  | "token_budget_exhausted"
  | "wall_clock_exhausted"
  | "normalizer_malformed";

export interface RetrievalHint {
  doc_id: string;
  page: number;
  section_slug: string;
  section_path: string;
  text_preview: string;
  year: number;
  source_type: string;
  score: number;
}

export interface FinalResponse {
  query_id: string;
  answer_markdown: string;
  citations: Citation[];
  currency_flags: CurrencyFlag[];
  disclaimer_id: string;
  refusal_reason: RefusalReason | null;
  from_cache?: boolean;
  cached_age_s?: number | null;
  retrieval_preview?: RetrievalHint[];
}

export interface QueryCreated {
  query_id: string;
  stream_url: string;
}

// Envelope returned from the server's SSE channel. `kind` tags the payload.
export type StreamEnvelope =
  | { kind: "trace"; payload: TraceEvent }
  | { kind: "final"; payload: FinalResponse }
  | { kind: "error"; payload: { error: string } };
