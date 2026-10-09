import { useState } from 'react';
import { useApp } from './context';
import { Button, Modal, Notice } from './ui';
import { errorMessage, label } from './api';
import type { Candidate, Evidence, Span } from './types';

const definitions: {
  name: string;
  title: string;
  options?: (string | [string, string])[];
  type?: string;
  required?: boolean;
}[] = [
  {
    name: 'doc_type',
    title: 'Document type',
    required: true,
    options: [['', 'Choose type'], 'invoice', 'dispatch', 'delivery', 'correspondence', 'other'],
  },
  { name: 'invoice_ref', title: 'Invoice reference' },
  { name: 'po_ref', title: 'Purchase order' },
  { name: 'sku', title: 'SKU for this case line' },
  { name: 'quantity', title: 'Quantity for this SKU' },
  {
    name: 'unit',
    title: 'Quantity unit',
    options: [['', 'Not applicable'], 'cases', 'units', 'kg', 'pallets'],
  },
  { name: 'page', title: 'Source page', type: 'number', required: true },
  {
    name: 'qualification',
    title: 'Delivery qualification',
    options: [
      ['unspecified', 'Not established / not applicable'],
      ['full_count', 'SKU quantity explicitly confirmed'],
      ['subject_to_count', 'Subject to count'],
      ['pallets_only', 'Pallet count only'],
      ['short_noted', 'Shortage noted'],
    ],
  },
  { name: 'reviewer', title: 'Reviewer name', required: true },
  { name: 'notes', title: 'Evidence notes', type: 'textarea' },
];
export function EvidenceReview({
  document: initial,
  caseId: initialCaseId,
  next = false,
}: {
  document: Evidence;
  caseId: string;
  next?: boolean;
}) {
  const { api, cases, refresh, setDialog, toast, url } = useApp();
  const [doc, setDoc] = useState(initial),
    [caseId, setCaseId] = useState(initialCaseId),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [progress, setProgress] = useState(''),
    [verified, setVerified] = useState(false),
    [highlight, setHighlight] = useState<Span | null>(null),
    [candidateIndex, setCandidateIndex] = useState('');
  function initialValues(d: Evidence, id: string) {
    const existing = d.mappings.find((m) => m.case_id === id),
      claim = cases.find((c) => c.id === id);
    const candidate = d.candidates.find(
      (r) =>
        claim &&
        r.fields.sku === claim.sku &&
        (!r.fields.invoice_ref || r.fields.invoice_ref === claim.invoice_ref),
    );
    const meta = existing?.confirmed
      ? existing.meta
      : { ...d.meta, ...candidate?.fields, page: candidate?.page || 1 };
    const fields = Object.fromEntries(definitions.map((f) => [f.name, String(meta[f.name] ?? '')]));
    fields.page ||= '1';
    fields.qualification ||= 'unspecified';
    fields.reviewer = existing?.reviewed_by || d.reviewed_by || '';
    return {
      fields,
      sourceIds: existing?.confirmed
        ? existing.meta.source_span_ids || []
        : candidate?.span_ids || [],
      version: existing?.reviewed_at || '',
    };
  }
  const [values, setValues] = useState(() => initialValues(initial, initialCaseId));
  const fields = values.fields,
    page = Number(fields.page),
    validPage = Number.isInteger(page) && page >= 1 && page <= doc.pages;
  const sourcePage = doc.extraction_pages.find((p) => p.page === page);
  const src = url(`documents/${doc.id}/file`);
  function change(name: string, value: string) {
    setValues((v) => ({
      ...v,
      fields: { ...v.fields, [name]: value },
      sourceIds:
        name === 'page' ? v.sourceIds.filter((id) => id.startsWith(`${value}:`)) : v.sourceIds,
    }));
    setVerified(false);
    if (name === 'page') setHighlight(null);
  }
  function chooseCandidate(candidate: Candidate, index: string) {
    setCandidateIndex(index);
    setValues((v) => ({
      ...v,
      fields: { ...v.fields, ...candidate.fields, page: String(candidate.page) },
      sourceIds: candidate.span_ids,
    }));
    setVerified(false);
    setHighlight(null);
  }
  async function runOCR() {
    if (!validPage) {
      setError(`Choose a page from 1 to ${doc.pages}.`);
      return;
    }
    setBusy(true);
    setError('');
    setProgress('Reading this page locally…');
    try {
      const result = await api<{ empty: boolean }>(`documents/${doc.id}/ocr`, { page });
      const updated = await api<Evidence>(`documents/${doc.id}`);
      setDoc(updated);
      setVerified(false);
      setHighlight(null);
      setProgress(
        result.empty
          ? 'No readable text detected. Manual review is available.'
          : 'OCR suggestions ready. Verify before confirming.',
      );
    } catch (e) {
      setError(errorMessage(e));
      setProgress('');
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Review a case line"
      sub={doc.filename}
      wide
      locked={busy}
      close={() => setDialog(null)}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!validPage) {
            setError(`Choose a page from 1 to ${doc.pages}.`);
            return;
          }
          setBusy(true);
          setError('');
          try {
            await api(`documents/${doc.id}/review`, {
              ...fields,
              case_id: caseId,
              verified,
              mapping_version: values.version,
              source_span_ids: values.sourceIds,
            });
            await refresh();
            setDialog(next ? { kind: 'matches' } : null);
            toast('This case line saved. Other line reviews unchanged.');
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset disabled={busy} className="m-0 border-0 p-0 min-w-0">
          <div className="modal-body">
            <div className="preview-layout">
              <div>
                <div className="document-preview">
                  {doc.mime === 'application/pdf' || doc.mime.startsWith('image/') ? (
                    <div className="source-page">
                      {validPage && (
                        <img
                          src={
                            doc.mime === 'application/pdf'
                              ? url(`documents/${doc.id}/preview?page=${page}`)
                              : src
                          }
                          alt={
                            doc.mime === 'application/pdf'
                              ? `Original PDF source page ${page}`
                              : 'Original source image'
                          }
                        />
                      )}
                      <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">
                        {highlight?.bbox && (
                          <rect
                            x={highlight.bbox[0] * 1000}
                            y={highlight.bbox[1] * 1000}
                            width={(highlight.bbox[2] - highlight.bbox[0]) * 1000}
                            height={(highlight.bbox[3] - highlight.bbox[1]) * 1000}
                            className="ocr-box"
                          />
                        )}
                      </svg>
                    </div>
                  ) : (
                    <pre>{doc.extracted_text}</pre>
                  )}
                </div>
                <a className="btn small mt-3" href={src} target="_blank" rel="noopener">
                  Open original
                </a>
                <div className="source-controls">
                  {(doc.mime === 'application/pdf' || doc.mime.startsWith('image/')) && (
                    <Button type="button" small onClick={() => void runOCR()}>
                      Read this page with OCR
                    </Button>
                  )}
                  <span className="metadata" role="status">
                    {progress}
                  </span>
                </div>
                <h3>Source text · page {fields.page}</h3>
                {sourcePage ? (
                  <>
                    <p className="metadata">
                      {sourcePage.method === 'local_ocr'
                        ? 'Local OCR — unverified. Select a line to highlight its position.'
                        : 'PDF/text layer — unverified. Inspect the referenced page to verify the text.'}
                    </p>
                    <div className="span-list">
                      {sourcePage.spans.map((s) => (
                        <button
                          type="button"
                          key={s.id}
                          className={`span-line ${s.confidence < 0.9 ? 'uncertain' : ''} ${highlight?.id === s.id ? 'selected' : ''}`}
                          aria-pressed={highlight?.id === s.id}
                          onClick={() => setHighlight(s)}
                        >
                          {s.text}
                          {sourcePage.method === 'local_ocr' && (
                            <small>{Math.round(s.confidence * 100)}% model score</small>
                          )}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="metadata">
                    No extracted text on this page. Run OCR or inspect the original manually.
                  </p>
                )}
                <p className="metadata mt-4">Original SHA-256: {doc.sha256}</p>
              </div>
              <div>
                <Notice>
                  Review is saved only for the selected deduction line. Other SKUs sharing this
                  original retain their own evidence.
                </Notice>
                <div className="field mb-4">
                  <label htmlFor="candidate">Extracted line suggestion</label>
                  <select
                    id="candidate"
                    value={candidateIndex}
                    onChange={(e) => {
                      const index = e.target.value;
                      setCandidateIndex(index);
                      if (index !== '') chooseCandidate(doc.candidates[Number(index)], index);
                    }}
                  >
                    <option value="">Keep entered fields</option>
                    {doc.candidates.map((c, i) => (
                      <option key={i} value={i}>
                        Page {c.page} · {c.fields.sku || 'Header'} · {c.fields.quantity || '?'}{' '}
                        {c.fields.unit || ''} ·{' '}
                        {c.method === 'local_ocr'
                          ? `${Math.round(c.confidence * 100)}% model score`
                          : 'Text layer'}
                      </option>
                    ))}
                  </select>
                  <small>Model score is not a guarantee. Every suggestion needs review.</small>
                </div>
                <div className="form-grid">
                  <div className="field">
                    <label htmlFor="review-case">Deduction line *</label>
                    <select
                      id="review-case"
                      required
                      value={caseId}
                      onChange={(e) => {
                        const id = e.target.value;
                        setCaseId(id);
                        setValues(initialValues(doc, id));
                        setVerified(false);
                        setHighlight(null);
                        setCandidateIndex('');
                        setError('');
                      }}
                    >
                      <option value="">Choose a case line</option>
                      {cases.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.claim_ref} / {c.line_ref} · {c.sku || 'SKU missing'}
                        </option>
                      ))}
                    </select>
                  </div>
                  {definitions.map((f) => (
                    <div className={`field ${f.type === 'textarea' ? 'full' : ''}`} key={f.name}>
                      <label htmlFor={`review-${f.name}`}>
                        {f.title}
                        {f.required && ' *'}
                      </label>
                      {f.options ? (
                        <select
                          id={`review-${f.name}`}
                          required={f.required}
                          value={fields[f.name] || ''}
                          onChange={(e) => change(f.name, e.target.value)}
                        >
                          {f.options.map((o) => {
                            const [v, t] = Array.isArray(o) ? o : [o, label(o)];
                            return (
                              <option key={v} value={v}>
                                {t}
                              </option>
                            );
                          })}
                        </select>
                      ) : f.type === 'textarea' ? (
                        <textarea
                          id={`review-${f.name}`}
                          maxLength={2000}
                          value={fields[f.name] || ''}
                          onChange={(e) => change(f.name, e.target.value)}
                        />
                      ) : (
                        <input
                          id={`review-${f.name}`}
                          type={f.type || 'text'}
                          required={f.required}
                          {...(f.name === 'page' ? { min: 1, max: doc.pages, step: 1 } : {})}
                          value={fields[f.name] || ''}
                          onChange={(e) => change(f.name, e.target.value)}
                        />
                      )}
                    </div>
                  ))}
                  <label className="check-label field full">
                    <input
                      type="checkbox"
                      required
                      checked={verified}
                      onChange={(e) => setVerified(e.target.checked)}
                    />
                    I checked this SKU, quantity, unit and source page against the original.
                    Delivery qualification reflects the actual receipt.
                  </label>
                </div>
                <p className="inline-error" role="alert">
                  {error}
                </p>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <Button primary type="submit">
              {busy ? 'Working…' : next ? 'Confirm & review next match' : 'Save this line review'}
            </Button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
