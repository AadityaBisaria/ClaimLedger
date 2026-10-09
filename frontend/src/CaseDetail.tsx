import { ArrowLeft, Upload } from 'lucide-react';
import { Badge, Button, Header, Notice, Panel } from './ui';
import { label, money } from './api';
import type { Detail } from './types';
export type CaseAction =
  | 'edit'
  | 'draft'
  | 'final'
  | 'upload'
  | 'link'
  | 'request'
  | 'submit'
  | 'accept'
  | 'decision'
  | 'credit'
  | 'followup';

const evidenceOrigins: Record<string, string> = {
  invoice: 'From your finance or ERP team: what your company billed.',
  dispatch: 'From your warehouse or 3PL: dispatch note, ASN, bill of lading, or shipment export.',
  delivery:
    'From the retailer portal/receiving team, carrier, or 3PL: a POD, receipt, or EDI receiving record naming the SKU quantity.',
};
export function CaseDetail({
  detail: d,
  back,
  action,
  review,
  unlink,
  url,
}: {
  detail: Detail;
  back: () => void;
  action: (a: CaseAction) => void;
  review: (id: string) => void;
  unlink: (id: string) => void;
  url: (path: string) => string;
}) {
  const c = d.case,
    a = d.assessment,
    closed = !['open', 'submitted'].includes(c.status);
  return (
    <>
      <button className="back inline-flex gap-2 items-center" onClick={back}>
        <ArrowLeft size={14} />
        Back to work queue
      </button>
      <Header
        eye={c.retailer}
        title={`Deduction ${c.claim_ref}`}
        sub={`${c.description || c.sku} · Line ${c.line_ref}`}
      >
        <Button disabled={c.status !== 'open'} onClick={() => action('edit')}>
          Edit case
        </Button>
        <Button disabled={closed} onClick={() => action('draft')}>
          Draft packet
        </Button>
        <Button
          primary
          disabled={a.readiness !== 'ready' || closed}
          onClick={() => action('final')}
        >
          Review & export
        </Button>
      </Header>
      <div className="tag-row">
        <Badge claim={{ ...c, assessment: a }} />
        <span className="pill">
          {c.currency} · {c.unit}
        </span>
      </div>
      {a.deadline_warning && (
        <Notice tone="warning">
          <strong>Deadline unconfirmed</strong>Check the retailer procedure and record the source.
          No statutory or retailer deadline is assumed.
        </Notice>
      )}
      <div className="split">
        <div>
          <Panel>
            <div className="detail-header">
              <h2>Evidence checks</h2>
              <span className="metadata">Single SKU · single shipment</span>
            </div>
            {a.checks.map((x, i) => (
              <div key={i} className={`check ${x.passed ? 'pass' : 'fail'}`}>
                <span className="check-icon">{x.passed ? '✓' : '!'}</span>
                <div>
                  {x.label}
                  <small>{x.detail}</small>
                </div>
              </div>
            ))}
            {Object.keys(a.quantities).length > 0 && (
              <Notice>
                <strong>Reviewed quantities · {c.unit}</strong>
                {Object.entries(a.quantities)
                  .map(([k, v]) => `${label(k)}: ${v}`)
                  .join(' / ')}
              </Notice>
            )}
          </Panel>
          <Panel>
            <div className="detail-header">
              <h2>Source documents</h2>
              <div className="actions">
                <Button onClick={() => action('link')}>Link existing</Button>
                <Button onClick={() => action('upload')}>
                  <Upload size={15} />
                  Upload
                </Button>
              </div>
            </div>
            <p className="text-sm text-muted">
              This is the supplier’s workspace. Upload records your company holds, or link them
              after obtaining them from the relevant operational party. Reference matches are
              suggestions; review the original before confirming fields.
            </p>
            {d.documents.length ? (
              d.documents.map((doc) => (
                <div className="evidence-card" key={doc.id}>
                  <div>
                    <strong>{doc.filename}</strong>
                    <span className="secondary">
                      {label(String(doc.meta.doc_type || 'unclassified'))} ·{' '}
                      {doc.confirmed && doc.reviewed_by
                        ? `Confirmed by ${doc.reviewed_by}`
                        : 'Suggested · review required'}
                    </span>
                    {evidenceOrigins[String(doc.meta.doc_type)] && (
                      <span className="secondary">
                        {evidenceOrigins[String(doc.meta.doc_type)]}
                      </span>
                    )}
                  </div>
                  <div className="actions">
                    <Button small onClick={() => review(doc.id)}>
                      Review
                    </Button>
                    <button
                      className="link-btn"
                      aria-label={`Unlink ${doc.filename}`}
                      onClick={() => unlink(doc.id)}
                    >
                      Unlink
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <Notice tone="warning">
                Upload the invoice, dispatch record and a receipt that substantiates SKU quantities.
              </Notice>
            )}
            <Button onClick={() => action('request')}>Missing evidence request</Button>
          </Panel>
          <Panel>
            <h2>Packet history</h2>
            {d.exports.length ? (
              d.exports.map((e) => (
                <div className="evidence-card" key={e.id}>
                  <div>
                    <strong>{e.kind === 'final' ? 'Reviewed packet' : 'Draft packet'}</strong>
                    <span className="secondary">
                      {e.created_at} ·{' '}
                      {e.current ? 'Matches current evidence' : 'Evidence changed since export'}
                    </span>
                  </div>
                  <div className="actions">
                    <a className="btn small" href={url(`exports/${e.id}/pdf`)}>
                      PDF
                    </a>
                    <a className="btn small" href={url(`exports/${e.id}/zip`)}>
                      ZIP + originals
                    </a>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">
                Exports are snapshots. Changing evidence requires a new reviewed packet before
                submission.
              </p>
            )}
          </Panel>
        </div>
        <div>
          <Panel>
            <div className="eyebrow">Deduction value</div>
            <p className="amount-big money !text-ink">{money(c.amount_cents, c.currency)}</p>
            <dl className="key-value">
              {[
                ['Invoice', c.invoice_ref],
                ['Purchase order', c.po_ref],
                ['SKU', c.sku],
                ['Alleged shortage', `${c.claimed_qty || 'Unknown'} ${c.unit}`],
                ['Supplier account', c.supplier_account],
                ['Owner', c.owner],
                ['Deadline', c.deadline],
                ['Deadline source', c.deadline_source],
                ['Follow-up', c.followup_date],
                ['Submission reference', c.submission_ref],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v || 'Not entered'}</dd>
                </div>
              ))}
            </dl>
            <hr className="divider" />
            {(
              [
                ['Disputed', c.disputed_cents],
                ['Approved', c.approved_cents],
                ['Credited', c.credited_cents],
              ] as const
            ).map(([k, v]) => (
              <div className="flow-status" key={k}>
                {k} <strong>{money(v, c.currency)}</strong>
              </div>
            ))}
            <div className="actions mt-4">
              {c.status === 'open' && (
                <>
                  <Button primary onClick={() => action('submit')}>
                    Record submission
                  </Button>
                  <Button onClick={() => action('accept')}>Accept deduction</Button>
                </>
              )}
              {c.status === 'submitted' && (
                <Button primary onClick={() => action('decision')}>
                  Record decision
                </Button>
              )}
              {c.status === 'approved' && (
                <Button primary onClick={() => action('credit')}>
                  Record credit
                </Button>
              )}
              <Button onClick={() => action('followup')}>Notes & follow-up</Button>
            </div>
            <p className="text-sm text-muted">
              Record submission only after submitting through the retailer’s channel.
            </p>
          </Panel>
          <Panel>
            <h2>Activity trail</h2>
            <ul className="timeline">
              {d.events.slice(0, 20).map((e) => (
                <li key={e.id}>
                  {e.action}
                  <time>{e.created_at}</time>
                  <details>
                    <summary>Details</summary>
                    <pre className="source-text">{JSON.stringify(e.detail, null, 2)}</pre>
                  </details>
                </li>
              ))}
            </ul>
            <details>
              <summary>Original import record</summary>
              <pre className="source-text">{c.source_json}</pre>
            </details>
          </Panel>
        </div>
      </div>
    </>
  );
}
