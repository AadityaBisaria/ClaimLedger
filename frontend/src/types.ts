export type Workspace = 'demo' | 'live';
export type Currency = 'GBP' | 'USD' | 'CAD' | 'EUR';
export type View = 'queue' | 'documents' | 'credits' | 'guide';
export type Fields = Record<string, string>;
export interface Assessment {
  readiness: 'ready' | 'conflict' | 'missing';
  checks: { label: string; passed: boolean; detail: string }[];
  quantities: Record<string, string>;
  deadline_warning: boolean;
}
export interface Claim {
  id: string;
  workspace: Workspace;
  retailer: string;
  supplier_account: string;
  claim_ref: string;
  line_ref: string;
  invoice_ref: string;
  po_ref: string;
  sku: string;
  description: string;
  amount_cents: number;
  currency: Currency;
  claimed_qty: string;
  unit: string;
  claim_date: string;
  deadline: string;
  deadline_source: string;
  owner: string;
  notes: string;
  status: 'open' | 'submitted' | 'approved' | 'rejected' | 'accepted' | 'credited';
  disputed_cents: number;
  approved_cents: number;
  credited_cents: number;
  submission_ref: string;
  submitted_at: string;
  followup_date: string;
  source_json: string;
  version: number;
  assessment: Assessment;
  overdue: boolean;
}
export interface Span {
  id: string;
  text: string;
  confidence: number;
  bbox: [number, number, number, number] | null;
}
export interface Candidate {
  fields: Fields;
  page: number;
  method: string;
  confidence: number;
  span_ids: string[];
}
export interface EvidenceMeta {
  [key: string]: string | number | string[] | undefined;
  source_span_ids?: string[];
}
export interface Evidence {
  id: string;
  filename: string;
  mime: string;
  size: number;
  sha256: string;
  extracted_text: string;
  extraction_status: string;
  pages: number;
  meta: EvidenceMeta;
  reviewed_by: string;
  reviewed_at: string;
  confirmed?: boolean;
  candidates: Candidate[];
  extraction_pages: { page: number; method: string; spans: Span[] }[];
  mappings: {
    case_id: string;
    meta: EvidenceMeta;
    reviewed_by: string;
    reviewed_at: string;
    confirmed: boolean;
  }[];
}
export interface Match {
  document_id: string;
  filename: string;
  case_id: string;
  claim_ref: string;
  line_ref: string;
  sku: string;
  reason: string;
  candidate: Candidate;
}
export interface Credit {
  id: string;
  claim_id: string;
  claim_ref: string;
  retailer: string;
  credit_ref: string;
  amount_cents: number;
  currency: Currency;
  credit_date: string;
  source: string;
  voided_at: string;
  void_reason: string;
}
export interface Detail {
  case: Claim;
  assessment: Assessment;
  documents: Evidence[];
  events: { id: string; action: string; created_at: string; detail: unknown }[];
  exports: { id: string; kind: string; created_at: string; current: boolean }[];
  credits: Credit[];
}
export interface ImportPreview {
  headers: string[];
  mapping: Fields;
  fields: string[];
  required: string[];
  errors: string[];
  count: number;
  new_count: number;
  duplicates: number;
  preview: Claim[];
}
export interface FilePayload {
  filename: string;
  data: string;
}
export type Api = <T>(path: string, body?: unknown) => Promise<T>;
