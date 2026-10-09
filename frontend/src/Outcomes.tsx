import { useEffect, useState } from 'react';
import { useApp } from './context';
import { Button, CurrencySelect, Empty, Header, Metric, Notice, Panel } from './ui';
import { errorMessage, money } from './api';
import type { Credit, Currency } from './types';

export function Outcomes({
  currency,
  setCurrency,
}: {
  currency: Currency;
  setCurrency: (c: Currency) => void;
}) {
  const { api, cases, openCase, setDialog } = useApp();
  const [credits, setCredits] = useState<Credit[] | null>(null),
    [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    api<{ credits: Credit[] }>('credits')
      .then((r) => {
        if (alive) setCredits(r.credits);
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      });
    return () => {
      alive = false;
    };
  }, [api]);
  const cc = cases.filter((c) => c.currency === currency),
    rows = credits?.filter((c) => c.currency === currency) || [];
  return (
    <>
      <Header
        eye="Close the loop"
        title="Credits & outcomes"
        sub="An approved dispute is not cash recovered."
      >
        <CurrencySelect value={currency} onChange={setCurrency} />
      </Header>
      <div className="stats">
        <Metric
          title={`Approved · ${currency}`}
          value={money(
            cc.reduce((s, c) => s + c.approved_cents, 0),
            currency,
          )}
        />
        <Metric
          featured
          title={`Credited · ${currency}`}
          value={money(
            rows.filter((c) => !c.voided_at).reduce((s, c) => s + c.amount_cents, 0),
            currency,
          )}
        />
        <Metric
          title="Awaiting credit"
          value={money(
            cc.reduce((s, c) => s + c.approved_cents - c.credited_cents, 0),
            currency,
          )}
        />
        <Metric
          title="Closed cases"
          value={cc.filter((c) => ['credited', 'rejected', 'accepted'].includes(c.status)).length}
        />
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {!credits && !error && (
        <p className="loading" role="status">
          Loading credits…
        </p>
      )}
      {credits && (
        <div className="surface">
          <div className="toolbar">
            <h2 className="!mb-0">Recorded credits</h2>
            <span className="metadata">Operator-confirmed retailer records</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {['CREDIT REFERENCE', 'CASE', 'AMOUNT', 'DATE / SOURCE', 'CORRECTION'].map(
                    (t) => (
                      <th key={t}>{t}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((c) => (
                    <tr key={c.id}>
                      <td>{c.credit_ref}</td>
                      <td>
                        <button className="link-btn" onClick={() => void openCase(c.claim_id)}>
                          {c.claim_ref}
                        </button>
                        <span className="secondary">{c.retailer}</span>
                      </td>
                      <td className="money">{money(c.amount_cents, c.currency)}</td>
                      <td>
                        {c.credit_date}
                        <span className="secondary">{c.source}</span>
                      </td>
                      <td>
                        {c.voided_at ? (
                          <>
                            <span className="pill closed">Reversed</span>
                            <span className="secondary">{c.void_reason}</span>
                          </>
                        ) : (
                          <Button small onClick={() => setDialog({ kind: 'reverse', id: c.id })}>
                            Correct entry
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5}>
                      <Empty title="No credits recorded">
                        Open an approved case and record the actual retailer credit.
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
export function Guide() {
  const { url } = useApp();
  return (
    <>
      <Header
        eye="Your first dispute"
        title="Start with the evidence"
        sub="A focused workbench for a small finance team."
      />
      <div className="steps">
        <div className="step">
          <div className="step-number">01 / CAPTURE</div>
          <h2>Bring in the deduction</h2>
          <p>
            Switch to Live for your own records. Import CSV or XLSX, map columns, and review errors.
            Repeat imports skip exact duplicates.
          </p>
          <a className="btn small" href={url('template')}>
            Download CSV template
          </a>
        </div>
        <div className="step">
          <div className="step-number">02 / INVESTIGATE</div>
          <h2>Review the originals</h2>
          <p>
            Confirm invoice, PO, SKU, unit and quantity against each original. Scans and images
            support local OCR, followed by human review. Pallet-only or subject-to-count receipts
            remain flagged.
          </p>
        </div>
        <div className="step">
          <div className="step-number">03 / RESOLVE</div>
          <h2>Submit, then reconcile</h2>
          <p>
            Export a reviewed PDF and ZIP. Submit through the retailer’s channel, record their
            reference and decision, then match actual credits separately.
          </p>
        </div>
      </div>
      <Panel className="mt-6">
        <h2>MVP scope</h2>
        <p className="text-sm text-muted">
          Single SKU, single shipment, full-delivery shortage disputes in GBP, CAD, USD and EUR. One
          invoice, dispatch and delivery receipt per case. Shared multi-SKU originals support
          independent case-line reviews. Split shipments, unit conversions, pricing and promotional
          claims still require manual investigation.
        </p>
        <h2 className="mt-5">What the checks establish</h2>
        <p className="text-sm text-muted">
          Ready means the entered evidence is consistent. It does not establish authenticity,
          liability or retailer acceptance. Check the retailer’s current requirements and record the
          deadline source.
        </p>
        <h2 className="mt-5">Local storage</h2>
        <p className="text-sm text-muted">
          Records and originals stay in the application’s data folder. There are no external AI
          calls, portal connections, messages or cloud backups. This local single-operator app has
          no accounts or encryption at rest. Protect your computer. Stop the app before backing up
          the entire data folder.
        </p>
        <h2 className="mt-5">Explore the demo</h2>
        <p className="text-sm text-muted">
          All Northfield Markets records are fictional. NF-1043 has complete evidence; NF-1042 has a
          pallet-only receipt; NF-1044 has a quantity mismatch; NF-1045 has a partial credit. Live
          starts empty.
        </p>
      </Panel>
    </>
  );
}
