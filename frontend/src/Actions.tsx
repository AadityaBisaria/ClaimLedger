import { useApp } from './context';
import { Field, Form, Modal, Notice, Select, Verify } from './ui';
import { money, today } from './api';
import type { Claim, Detail } from './types';
import type { CaseAction } from './CaseDetail';

export function EditCase({ claim: c }: { claim?: Claim }) {
  const { api, refresh, openCase, setDialog, toast } = useApp();
  return (
    <Modal
      title={c ? 'Edit deduction' : 'New deduction'}
      sub="One deduction line per case. Use exact retailer references."
      close={() => setDialog(null)}
    >
      <Form
        onSubmit={async (p) => {
          if (c) {
            await api(`cases/${c.id}/edit`, { ...p, version: c.version });
            await refresh();
          } else {
            const r = await api<{ id: string }>('cases', p);
            await refresh();
            await openCase(r.id);
          }
          setDialog(null);
          toast('Case saved.');
        }}
      >
        <Field name="retailer" title="Retailer" value={c?.retailer} required />
        <Field name="supplier_account" title="Supplier account" value={c?.supplier_account} />
        <Field name="claim_ref" title="Deduction reference" value={c?.claim_ref} required />
        <Field name="line_ref" title="Line reference" value={c?.line_ref || '1'} required />
        <Field name="invoice_ref" title="Invoice reference" value={c?.invoice_ref} />
        <Field name="po_ref" title="Purchase order" value={c?.po_ref} />
        <Field name="sku" title="SKU" value={c?.sku} />
        <Field name="description" title="Product description" value={c?.description} />
        <Field
          name="amount"
          title="Deduction amount"
          value={c ? String(c.amount_cents / 100) : ''}
          type="number"
          required
        />
        <Select
          name="currency"
          title="Currency"
          options={['GBP', 'USD', 'CAD', 'EUR']}
          value={c?.currency || 'GBP'}
        />
        <Field name="claimed_qty" title="Alleged shortage quantity" value={c?.claimed_qty} />
        <Select
          name="unit"
          title="Quantity unit"
          options={['cases', 'units', 'kg', 'pallets']}
          value={c?.unit || 'cases'}
        />
        <Field name="claim_date" title="Deduction date" type="date" value={c?.claim_date} />
        <Field name="deadline" title="Dispute deadline" type="date" value={c?.deadline} />
        <Field
          name="deadline_source"
          title="Deadline source / policy reference"
          value={c?.deadline_source}
        />
        <Field name="owner" title="Owner" value={c?.owner} />
        <Field name="notes" title="Notes" value={c?.notes} type="textarea" />
      </Form>
    </Modal>
  );
}
export function CaseActionDialog({ action, detail: d }: { action: CaseAction; detail: Detail }) {
  const { api, refresh, setDialog, toast } = useApp();
  const c = d.case;
  const titles: Partial<Record<CaseAction, string>> = {
    submit: 'Record retailer submission',
    decision: 'Record retailer decision',
    accept: 'Accept the deduction',
    credit: 'Record an actual credit',
    followup: 'Notes and follow-up',
    draft: 'Export draft packet',
    final: 'Review and export packet',
    request: 'Missing evidence request',
  };
  if (action === 'request') {
    const outstanding = d.assessment.checks.filter((x) => !x.passed);
    const targets = [
      outstanding.some((x) => x.label.startsWith('Invoice')) &&
        '• Finance / accounts receivable: invoice or ERP export showing this SKU and quantity.',
      outstanding.some((x) => x.label.startsWith('Dispatch')) &&
        '• Warehouse or 3PL: dispatch note, ASN, bill of lading, or shipment export.',
      outstanding.some((x) => x.label.startsWith('Delivery')) &&
        '• Retailer receiving/deductions team, carrier, or 3PL: proof of delivery, receipt, or EDI receiving record with the SKU quantity.',
    ].filter(Boolean);
    const text = `Subject: Evidence request — ${c.claim_ref} / ${c.invoice_ref}\n\nThis request supports a supplier dispute of a retailer deduction. Please provide the outstanding records for PO ${c.po_ref || '[PO]'}, SKU ${c.sku || '[SKU]'}:\n\n${targets.join('\n')}\n\nChecks still incomplete:\n${outstanding
      .map((x) => `• ${x.label}: ${x.detail}`)
      .join(
        '\n',
      )}\n\nWe need the SKU quantity and unit, with a receipt confirming the actual count. A pallet-only or subject-to-count signature may not establish the delivered quantity.\n\nDispute deadline: ${c.deadline || 'unconfirmed — please confirm the applicable deadline'}.\nThank you.`;
    return (
      <Modal
        title="Missing evidence request"
        sub="Copy and send through your usual channel. No messages are sent by this app."
        close={() => setDialog(null)}
      >
        <div className="modal-body">
          <div className="field">
            <label htmlFor="request-text">Draft request</label>
            <textarea id="request-text" defaultValue={text} rows={16} />
          </div>
        </div>
      </Modal>
    );
  }
  const packet = action === 'draft' || action === 'final';
  return (
    <Modal
      title={titles[action] || 'Update case'}
      sub={
        packet
          ? 'Saved as a snapshot. No submission is sent.'
          : 'Changes are recorded in the activity trail.'
      }
      close={() => setDialog(null)}
    >
      <Form
        submit={packet ? 'Generate packet' : 'Save'}
        onSubmit={async (p) => {
          if (packet) {
            const r = await api<{ id: string }>(`cases/${c.id}/export`, {
              kind: action,
              reviewer: p.reviewer,
              verified: p.verified === 'on',
            });
            await refresh();
            setDialog({ kind: 'export', id: r.id });
          } else {
            await api(`cases/${c.id}/${action === 'accept' ? 'decision' : action}`, {
              ...p,
              version: c.version,
              currency: c.currency,
              verified: p.verified === 'on',
              ...(action === 'accept' ? { decision: 'accepted' } : {}),
            });
            await refresh();
            setDialog(null);
            toast('Record saved.');
          }
        }}
      >
        {packet && (
          <>
            <div className="full">
              <Notice tone={action === 'draft' ? 'warning' : ''}>
                {action === 'final'
                  ? 'Confirm the original documents, quantities and retailer requirements. Passing checks does not establish retailer acceptance.'
                  : 'Incomplete checks are labelled in the PDF. A draft cannot unlock submission.'}
              </Notice>
            </div>
            <Field name="reviewer" title="Reviewer name" required={action === 'final'} />
            {action === 'final' && (
              <Verify>
                I reviewed the originals, requested amount and applicable submission requirements.
              </Verify>
            )}
          </>
        )}
        {action === 'submit' && (
          <>
            <div className="full">
              <Notice>
                Record a submission you already made. Nothing is sent to the retailer.
              </Notice>
            </div>
            <Field name="submission_ref" title="Retailer submission reference" required />
            <Field
              name="submitted_at"
              title="Submission date"
              value={today()}
              type="date"
              required
            />
            <Field name="followup_date" title="Follow-up date" type="date" />
          </>
        )}
        {action === 'decision' && (
          <>
            <Select
              name="decision"
              title="Outcome"
              value="approved"
              options={[
                ['approved', 'Approved (full or partial)'],
                ['rejected', 'Rejected'],
              ]}
            />
            <Field
              name="amount"
              title={`Approved amount · ${c.currency}`}
              value={String(c.disputed_cents / 100)}
              type="number"
              required
            />
            <Field
              name="source"
              title="Retailer response reference / evidence"
              type="textarea"
              required
            />
          </>
        )}
        {action === 'accept' && (
          <>
            <div className="full">
              <Notice tone="warning">
                Close this case because the deduction is valid or you have decided not to dispute
                it.
              </Notice>
            </div>
            <Field name="source" title="Reason and supporting reference" type="textarea" required />
          </>
        )}
        {action === 'credit' && (
          <>
            <div className="full">
              <Notice>
                Remaining approved:{' '}
                <strong>{money(c.approved_cents - c.credited_cents, c.currency)}</strong>Record the
                credit shown by the retailer.
              </Notice>
            </div>
            <Field name="credit_ref" title="Unique credit / allocation reference" required />
            <Field name="amount" title={`Credit amount · ${c.currency}`} type="number" required />
            <Field name="credit_date" title="Credit date" value={today()} type="date" required />
            <Field name="source" title="Remittance or credit-note reference" required />
            <Verify>I checked this credit against the retailer record.</Verify>
          </>
        )}
        {action === 'followup' && (
          <>
            <Field name="owner" title="Owner" value={c.owner} />
            <Field
              name="followup_date"
              title="Follow-up date"
              value={c.followup_date}
              type="date"
            />
            <Field name="notes" title="Case notes" value={c.notes} type="textarea" />
          </>
        )}
      </Form>
    </Modal>
  );
}
export function ReverseCredit({ id }: { id: string }) {
  const { api, refresh, setDialog, toast } = useApp();
  return (
    <Modal
      title="Reverse a credit entry"
      sub="Local record correction only. No transaction is sent."
      close={() => setDialog(null)}
    >
      <Form
        submit="Reverse entry"
        onSubmit={async (p) => {
          await api(`credits/${id}/reverse`, { reason: p.reason, verified: p.verified === 'on' });
          await refresh();
          setDialog(null);
          toast('Credit entry reversed; original retained.');
        }}
      >
        <div className="full">
          <Notice tone="warning">
            The original entry stays in the audit trail. This correction removes it from credited
            totals and restores the approved balance. Use a new allocation reference for any
            replacement entry.
          </Notice>
        </div>
        <Field name="reason" title="Reason for correction" type="textarea" required />
        <Verify>I confirm this credit entry was recorded in error.</Verify>
      </Form>
    </Modal>
  );
}
