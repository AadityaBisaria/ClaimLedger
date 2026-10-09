import { useEffect, useState } from 'react';
import { Upload } from 'lucide-react';
import { useApp } from './context';
import { Button, Empty, Form, Header, Modal, Notice } from './ui';
import { errorMessage, filePayload, label } from './api';
import type { Evidence, Match } from './types';

export function Documents() {
  const { api, setDialog, review } = useApp();
  const [data, setData] = useState<{ documents: Evidence[]; matches: Match[] } | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    Promise.all([
      api<{ documents: Evidence[] }>('documents'),
      api<{ matches: Match[] }>('documents/matches'),
    ])
      .then(([d, m]) => {
        if (alive) setData({ ...d, ...m });
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      });
    return () => {
      alive = false;
    };
  }, [api]);
  return (
    <>
      <Header
        eye="Source records"
        title="Evidence library"
        sub="Share originals across SKUs. Keep each line’s review independent."
      >
        <Button onClick={() => setDialog({ kind: 'matches' })}>
          Suggested matches ({data?.matches.length ?? '…'})
        </Button>
        <Button primary onClick={() => setDialog({ kind: 'upload' })}>
          <Upload size={16} />
          Bulk upload
        </Button>
      </Header>
      {error && <Notice tone="error">{error}</Notice>}
      {!data && !error && (
        <p className="loading" role="status">
          Loading evidence…
        </p>
      )}
      {data && (
        <div className="surface">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {['ORIGINAL', 'EXTRACTED LINES', 'CASE REVIEWS', ''].map((t, i) => (
                    <th key={i}>{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.documents.length ? (
                  data.documents.map((d) => (
                    <tr key={d.id}>
                      <td>
                        {d.filename}
                        <span className="secondary">
                          {d.pages} page(s) · {Math.ceil(d.size / 1024)} KB
                        </span>
                      </td>
                      <td>
                        {d.candidates.length}
                        <span className="secondary">{label(d.extraction_status)}</span>
                      </td>
                      <td>{d.mappings.filter((m) => m.confirmed).length} confirmed line(s)</td>
                      <td>
                        <Button small onClick={() => void review(d.id)}>
                          Review line
                        </Button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4}>
                      <Empty title="No documents yet">
                        Upload invoices, dispatch records and delivery receipts together.
                      </Empty>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
export function Matches() {
  const { api, setDialog, review } = useApp();
  const [rows, setRows] = useState<Match[] | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    api<{ matches: Match[] }>('documents/matches')
      .then((r) => {
        if (alive) setRows(r.matches);
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      });
    return () => {
      alive = false;
    };
  }, [api]);
  return (
    <Modal
      title="Suggested evidence matches"
      sub={`${rows?.length ?? '…'} unconfirmed suggestions. Exact references only; no automatic approvals.`}
      wide
      close={() => setDialog(null)}
    >
      <div className="modal-body">
        {error && <Notice tone="error">{error}</Notice>}
        {rows === null && !error && <p role="status">Loading suggestions…</p>}
        {rows?.length === 0 && (
          <Notice>
            No unconfirmed exact matches. Upload evidence, run OCR where needed, or link an original
            manually.
          </Notice>
        )}
        {rows?.map((r, i) => (
          <div className="evidence-card" key={`${r.document_id}-${r.case_id}-${i}`}>
            <div>
              <strong>{r.filename}</strong>
              <span className="secondary">
                {r.claim_ref} / {r.line_ref} · {r.sku} · page {r.candidate.page}
              </span>
              <span className="secondary">{r.reason}</span>
            </div>
            <Button small onClick={() => void review(r.document_id, r.case_id, true)}>
              Review line
            </Button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
export function LinkExisting({ caseId }: { caseId: string }) {
  const { api, review, setDialog } = useApp();
  const [docs, setDocs] = useState<Evidence[] | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    api<{ documents: Evidence[] }>('documents')
      .then((r) => {
        if (alive) setDocs(r.documents);
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      });
    return () => {
      alive = false;
    };
  }, [api]);
  return (
    <Modal
      title="Link an existing document"
      sub="Review the original, then confirm the link."
      close={() => setDialog(null)}
    >
      <div className="modal-body">
        {error && <Notice tone="error">{error}</Notice>}
        {!docs && !error && <p role="status">Loading originals…</p>}
        {docs?.length === 0 && (
          <Empty title="Your library is empty">Upload a document first.</Empty>
        )}
        {docs?.map((d) => (
          <div className="evidence-card" key={d.id}>
            <strong>{d.filename}</strong>
            <Button small onClick={() => void review(d.id, caseId)}>
              Review & link
            </Button>
          </div>
        ))}
      </div>
    </Modal>
  );
}
interface UploadResult {
  filename: string;
  id?: string;
  ok: boolean;
  detail: string;
}
export function UploadDialog({ caseId = '' }: { caseId?: string }) {
  const { api, refresh, setDialog, review } = useApp();
  const [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(''),
    [results, setResults] = useState<UploadResult[] | null>(null);
  return (
    <Modal
      title={results ? 'Upload results' : 'Bulk upload evidence'}
      sub={
        results
          ? 'Review the suggested matches before confirming evidence.'
          : 'Select up to 50 originals · PDF, PNG, JPEG or TXT · 10 MB per file.'
      }
      locked={busy}
      close={() => setDialog(null)}
    >
      {results ? (
        <div className="modal-body">
          {results.map((r, i) => (
            <div className="evidence-card" key={i}>
              <div>
                <strong>{r.filename}</strong>
                <span className="secondary">{r.detail}</span>
              </div>
              {r.ok ? (
                <Button small onClick={() => void review(r.id!, caseId)}>
                  Review
                </Button>
              ) : (
                <span className="pill danger">Failed</span>
              )}
            </div>
          ))}
          <Notice>
            Uploads and OCR never confirm evidence automatically. For multi-page scans, run OCR on
            each relevant source page in the review screen.
          </Notice>
          <Button primary onClick={() => setDialog({ kind: 'matches' })}>
            Review suggested matches
          </Button>
        </div>
      ) : (
        <Form
          submit="Upload documents"
          onBusy={setBusy}
          onSubmit={async (p, form) => {
            const files = Array.from(
              (form.elements.namedItem('files') as HTMLInputElement).files || [],
            );
            if (!files.length) throw new Error('Choose a file first.');
            if (files.length > 50 || files.reduce((s, f) => s + f.size, 0) > 100 * 1024 * 1024)
              throw new Error('Choose at most 50 files totalling no more than 100 MB.');
            const out: UploadResult[] = [];
            for (let i = 0; i < files.length; i++) {
              const f = files[i];
              setProgress(`Saving ${i + 1}/${files.length}: ${f.name}`);
              try {
                const r = await api<{ id: string; duplicate: boolean; matches: Match[] }>(
                  'documents',
                  { ...(await filePayload(f)), case_id: caseId },
                );
                let ocr = '';
                if (p.ocr === 'on') {
                  const d = await api<Evidence>(`documents/${r.id}`);
                  if (d.extraction_status === 'manual_review') {
                    setProgress(`Reading ${f.name} locally…`);
                    try {
                      const result = await api<{ empty: boolean }>(`documents/${r.id}/ocr`, {
                        page: 1,
                      });
                      ocr = result.empty ? 'No text detected' : 'OCR suggestions ready';
                    } catch (e) {
                      ocr = `Saved; OCR failed: ${errorMessage(e)}`;
                    }
                  }
                }
                out.push({
                  filename: f.name,
                  id: r.id,
                  ok: true,
                  detail: `${r.duplicate ? 'Already saved' : 'Saved'} · ${ocr || `${r.matches.length} suggested match(es)`}`,
                });
              } catch (e) {
                out.push({ filename: f.name, ok: false, detail: errorMessage(e) });
              }
            }
            setResults(out);
            setProgress('');
            await refresh();
          }}
        >
          <div className="dropzone field full">
            <label htmlFor="upload-file">Choose documents</label>
            <input
              id="upload-file"
              name="files"
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              required
            />
            <p>
              Originals stay unchanged. Each file is saved independently; failures do not discard
              successful uploads.
            </p>
          </div>
          <label className="check-label field full">
            <input name="ocr" type="checkbox" />
            Run local OCR on image files and the first page of scans after upload.
          </label>
          <p className="metadata full" role="status">
            {progress}
          </p>
        </Form>
      )}
    </Modal>
  );
}
