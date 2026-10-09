import { Plus, Upload } from 'lucide-react';
import { Badge, Button, CurrencySelect, Empty, Header, Metric } from './ui';
import { money } from './api';
import type { Claim, Currency } from './types';

export type Filter = 'all' | 'ready' | 'missing' | 'submitted';
export function Queue({
  cases,
  currency,
  setCurrency,
  search,
  setSearch,
  filter,
  setFilter,
  openCase,
  newCase,
  importCases,
}: {
  cases: Claim[];
  currency: Currency;
  setCurrency: (c: Currency) => void;
  search: string;
  setSearch: (s: string) => void;
  filter: Filter;
  setFilter: (f: Filter) => void;
  openCase: (id: string) => void;
  newCase: () => void;
  importCases: () => void;
}) {
  const cc = cases.filter((c) => c.currency === currency);
  const open = cc.filter((c) => ['open', 'submitted'].includes(c.status));
  const rows = cc.filter(
    (c) =>
      [c.claim_ref, c.retailer, c.invoice_ref, c.po_ref, c.sku, c.description]
        .join(' ')
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (filter === 'all' ||
        (filter === 'ready' && c.status === 'open' && c.assessment.readiness === 'ready') ||
        (filter === 'missing' && c.status === 'open' && c.assessment.readiness !== 'ready') ||
        c.status === filter),
  );
  return (
    <>
      <Header
        eye="Deductions & recovery"
        title="Your work queue"
        sub="Find the evidence. Resolve the deduction. Account for the credit."
      >
        <Button onClick={newCase}>
          <Plus size={16} />
          New case
        </Button>
        <Button primary onClick={importCases}>
          <Upload size={16} />
          Import deductions
        </Button>
      </Header>
      <div className="stats">
        <Metric
          featured
          title={`Open deductions · ${currency}`}
          value={money(
            open.reduce((s, c) => s + c.amount_cents, 0),
            currency,
          )}
          sub={`${open.length} cases to resolve`}
        />
        <Metric
          title="Ready for review"
          value={cc.filter((c) => c.status === 'open' && c.assessment.readiness === 'ready').length}
          sub="Evidence checks complete"
        />
        <Metric
          title={`Awaiting credit · ${currency}`}
          value={money(
            cc.reduce((s, c) => s + c.approved_cents - c.credited_cents, 0),
            currency,
          )}
          sub="Approved, not yet credited"
        />
        <Metric
          title={`Credits recorded · ${currency}`}
          value={money(
            cc.reduce((s, c) => s + c.credited_cents, 0),
            currency,
          )}
          sub="Confirmed by the operator"
        />
      </div>
      <div className="surface">
        <div className="toolbar">
          <div className="tabs" role="group" aria-label="Filter deductions">
            {(
              [
                ['all', 'All cases'],
                ['ready', 'Ready'],
                ['missing', 'Needs work'],
                ['submitted', 'Submitted'],
              ] as const
            ).map(([v, t]) => (
              <button
                key={v}
                className={`tab ${filter === v ? 'active' : ''}`}
                aria-pressed={filter === v}
                onClick={() => setFilter(v)}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="actions">
            <CurrencySelect value={currency} onChange={setCurrency} />
            <input
              className="search"
              aria-label="Search cases"
              placeholder="Search case, retailer, invoice…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {['CASE / PRODUCT', 'RETAILER', 'DEDUCTION', 'NEXT ACTION', 'DEADLINE'].map((t) => (
                  <th key={t}>{t}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length ? (
                rows.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <button className="link-btn" onClick={() => openCase(c.id)}>
                        {c.claim_ref} <span className="metadata">/ {c.line_ref}</span>
                      </button>
                      <span className="secondary">
                        {c.description || c.sku || 'Product not entered'}
                      </span>
                    </td>
                    <td>
                      {c.retailer}
                      <span className="secondary">{c.invoice_ref || 'Invoice missing'}</span>
                    </td>
                    <td className="money">{money(c.amount_cents, c.currency)}</td>
                    <td>
                      <Badge claim={c} />
                      {c.followup_date && (
                        <span className="secondary">Follow-up {c.followup_date}</span>
                      )}
                    </td>
                    <td>
                      <span className={c.overdue ? 'text-danger' : ''}>
                        {c.deadline || 'Unconfirmed'}
                      </span>
                      {c.overdue && (
                        <span className="secondary text-danger">Past entered deadline</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>
                    <Empty title="No matching deductions">
                      Import a file, create a case, or change the currency and filters.
                    </Empty>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="table-footer">
          <span>
            {rows.length} cases · {currency} · Saved locally
          </span>
          <span>Approval and credits are tracked separately</span>
        </div>
      </div>
    </>
  );
}
