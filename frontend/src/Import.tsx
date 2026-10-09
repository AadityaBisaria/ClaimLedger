import { useState } from 'react';
import { useApp } from './context';
import { Button, Form, Modal, Notice, Select } from './ui';
import { errorMessage, filePayload, label, money } from './api';
import type { Fields, FilePayload, ImportPreview } from './types';

export function ImportDialog() {
  const { api, workspace, refresh, setDialog, toast, url } = useApp();
  const [step, setStep] = useState<'file' | 'mapping' | 'confirm'>('file'),
    [payload, setPayload] = useState<(FilePayload & { mapping?: Fields }) | null>(null),
    [preview, setPreview] = useState<ImportPreview | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  return (
    <Modal
      title={
        step === 'file'
          ? 'Import deductions'
          : step === 'mapping'
            ? 'Map and validate columns'
            : 'Review import'
      }
      sub={
        step === 'file'
          ? 'CSV or XLSX · up to 2,000 rows · maximum 5 MB'
          : step === 'mapping'
            ? `${payload?.filename} · ${preview?.count} rows · ${workspace.toUpperCase()} workspace`
            : `${preview?.new_count} new deductions · ${preview?.duplicates} duplicates skipped`
      }
      wide={step !== 'file'}
      locked={busy}
      close={() => setDialog(null)}
    >
      {step === 'file' && (
        <Form
          onBusy={setBusy}
          submit="Read file"
          onSubmit={async (_, form) => {
            const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0];
            if (!file) throw new Error('Choose a file first.');
            if (file.size > 5 * 1024 * 1024) throw new Error('Maximum import size is 5 MB.');
            const p = await filePayload(file);
            const r = await api<ImportPreview>('import/preview', p);
            setPayload(p);
            setPreview(r);
            setStep('mapping');
          }}
        >
          <div className="dropzone field full">
            <label htmlFor="import-file">Choose deduction export</label>
            <p>
              Required: retailer, claim reference, amount and currency. Dates: YYYY-MM-DD. Amounts:
              decimal point, no currency symbol.
            </p>
            <input id="import-file" name="file" type="file" accept=".csv,.xlsx" required />
          </div>
          <a className="btn full" href={url('template')}>
            Download template
          </a>
        </Form>
      )}
      {step === 'mapping' && preview && (
        <Form
          key={`mapping-${payload?.filename}`}
          onBusy={setBusy}
          submit="Validate rows"
          onSubmit={async (mapping) => {
            const p = { ...payload!, mapping };
            const r = await api<ImportPreview>('import/preview', p);
            setPayload(p);
            setPreview(r);
            setStep('confirm');
          }}
        >
          <div className="full">
            <Notice>
              No records are saved until you confirm the validated import. Optional unmapped fields
              stay blank.
            </Notice>
          </div>
          {preview.fields.map((k) => (
            <Select
              key={k}
              name={k}
              title={label(k)}
              options={[
                ['', 'Do not import'],
                ...preview.headers.map((h) => [h, h] as [string, string]),
              ]}
              value={payload?.mapping?.[k] || preview.mapping[k] || ''}
              required={preview.required.includes(k)}
            />
          ))}
        </Form>
      )}
      {step === 'confirm' && preview && (
        <>
          <div className="modal-body">
            {preview.errors.length ? (
              <Notice tone="error">
                <strong>Fix errors before importing</strong>
                {preview.errors.map((e, i) => (
                  <div key={i}>{e}</div>
                ))}
              </Notice>
            ) : (
              <Notice>
                All rows passed. Exact duplicates are skipped; existing cases are not overwritten.
              </Notice>
            )}
            <div className="import-preview">
              <table>
                <thead>
                  <tr>
                    {['CASE', 'RETAILER', 'INVOICE', 'AMOUNT'].map((t) => (
                      <th key={t}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((c, i) => (
                    <tr key={i}>
                      <td>{c.claim_ref}</td>
                      <td>{c.retailer}</td>
                      <td>{c.invoice_ref}</td>
                      <td>{money(c.amount_cents, c.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="metadata">First eight new rows shown. Every row was validated.</p>
            <p className="inline-error" role="alert">
              {error}
            </p>
          </div>
          <div className="modal-footer">
            <Button disabled={busy} onClick={() => setStep('mapping')}>
              Back to mapping
            </Button>
            <Button
              primary
              disabled={busy || !!preview.errors.length || !preview.new_count}
              onClick={async () => {
                setBusy(true);
                setError('');
                try {
                  const out = await api<ImportPreview>('import/commit', payload);
                  await refresh();
                  setDialog(null);
                  toast(
                    `${out.new_count} deductions imported; ${out.duplicates} duplicates skipped.`,
                  );
                } catch (e) {
                  setError(errorMessage(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? 'Importing…' : `Import ${preview.new_count} deductions`}
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
