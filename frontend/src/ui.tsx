import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type FormEvent,
  type ReactNode,
} from 'react';
import { X } from 'lucide-react';
import { errorMessage, label } from './api';
import type { Claim, Currency, Fields } from './types';

export function Button({
  children,
  primary = false,
  small = false,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean; small?: boolean }) {
  return (
    <button
      {...props}
      className={`btn ${primary ? 'primary' : ''} ${small ? 'small' : ''} ${className}`}
    >
      {children}
    </button>
  );
}
export function Header({
  eye,
  title,
  sub,
  children,
}: {
  eye: string;
  title: string;
  sub: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eye}</div>
        <h1>{title}</h1>
        <p className="subtitle">{sub}</p>
      </div>
      <div className="actions">{children}</div>
    </header>
  );
}
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-xl border border-line bg-white p-[23px] mb-5 max-[760px]:p-[18px] ${className}`}
    >
      {children}
    </section>
  );
}
export function Notice({
  children,
  tone = '',
}: {
  children: ReactNode;
  tone?: 'warning' | 'error' | '';
}) {
  return (
    <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {children}
    </div>
  );
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
export function Badge({ claim }: { claim: Claim }) {
  const ready = claim.assessment?.readiness;
  return claim.status === 'open' ? (
    <span
      className={`pill ${ready === 'ready' ? 'ready' : ready === 'conflict' ? 'danger' : 'missing'}`}
    >
      {ready === 'ready'
        ? 'Ready for review'
        : ready === 'conflict'
          ? 'Investigate mismatch'
          : 'Needs evidence'}
    </span>
  ) : (
    <span className={`pill ${claim.status === 'credited' ? 'ready' : 'review'}`}>
      {label(claim.status)}
    </span>
  );
}
export function CurrencySelect({
  value,
  onChange,
}: {
  value: Currency;
  onChange: (value: Currency) => void;
}) {
  return (
    <select
      className="search !min-w-0 !w-auto"
      aria-label="Display currency"
      value={value}
      onChange={(e) => onChange(e.target.value as Currency)}
    >
      {['GBP', 'USD', 'CAD', 'EUR'].map((c) => (
        <option key={c}>{c}</option>
      ))}
    </select>
  );
}
export function Metric({
  title,
  value,
  sub,
  featured = false,
}: {
  title: string;
  value: ReactNode;
  sub?: string;
  featured?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border px-[22px] py-[21px] max-[1150px]:px-[15px] ${featured ? 'border-[#d4e2d9] bg-[#e6eee9]' : 'border-line bg-white'}`}
    >
      <div className="text-[13px] text-muted">{title}</div>
      <strong className="block my-[7px] text-[29px] max-[1150px]:text-[26px] tracking-[-.9px] font-semibold tabular-nums">
        {value}
      </strong>
      <small className="text-xs text-muted">{sub}</small>
    </div>
  );
}
export function Modal({
  title,
  sub,
  children,
  wide = false,
  close,
  locked = false,
}: {
  title: string;
  sub?: string;
  children: ReactNode;
  wide?: boolean;
  close: () => void;
  locked?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const node = ref.current!;
    if (!node.open) node.showModal();
    return () => node.close();
  }, []);
  useEffect(() => {
    const node = ref.current!;
    const cancel = (e: Event) => {
      e.preventDefault();
      if (!locked) close();
    };
    node.addEventListener('cancel', cancel);
    return () => node.removeEventListener('cancel', cancel);
  }, [close, locked]);
  return (
    <dialog ref={ref} className={wide ? 'wide' : ''} aria-labelledby={titleId}>
      <div className="modal-header">
        <div>
          <h2 id={titleId}>{title}</h2>
          <p className="subtitle">{sub}</p>
        </div>
        <button
          className="close grid place-items-center"
          type="button"
          aria-label="Close dialog"
          onClick={close}
          disabled={locked}
        >
          <X size={17} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Form({
  children,
  onSubmit,
  submit = 'Save',
  onBusy,
}: {
  children: ReactNode;
  onSubmit: (values: Fields, form: HTMLFormElement) => Promise<void>;
  submit?: string;
  onBusy?: (busy: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    onBusy?.(true);
    setError('');
    try {
      const values = Object.fromEntries(Array.from(new FormData(form), ([k, v]) => [k, String(v)]));
      await onSubmit(values, form);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
      onBusy?.(false);
    }
  }
  return (
    <form onSubmit={save}>
      <fieldset disabled={busy} className="m-0 border-0 p-0 min-w-0">
        <div className="modal-body">
          <div className="form-grid">{children}</div>
          <p className="inline-error" role="alert">
            {error}
          </p>
        </div>
        <div className="modal-footer">
          <Button primary type="submit">
            {busy ? 'Working…' : submit}
          </Button>
        </div>
      </fieldset>
    </form>
  );
}
export function Field({
  name,
  title,
  value = '',
  type = 'text',
  required = false,
  full = false,
}: {
  name: string;
  title: string;
  value?: string | number;
  type?: string;
  required?: boolean;
  full?: boolean;
}) {
  const id = useId();
  return (
    <div className={`field ${type === 'textarea' || full ? 'full' : ''}`}>
      <label htmlFor={id}>
        {title}
        {required && ' *'}
      </label>
      {type === 'textarea' ? (
        <textarea id={id} name={name} defaultValue={value} required={required} maxLength={2000} />
      ) : (
        <input
          id={id}
          name={name}
          type={type}
          defaultValue={value}
          required={required}
          {...(type === 'number' ? { step: '0.01', min: '0' } : {})}
        />
      )}
    </div>
  );
}
export function Select({
  name,
  title,
  options,
  value = '',
  required = false,
}: {
  name: string;
  title: string;
  options: (string | [string, string])[];
  value?: string;
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>
        {title}
        {required && ' *'}
      </label>
      <select id={id} name={name} defaultValue={value} required={required}>
        {options.map((o) => {
          const [v, t] = Array.isArray(o) ? o : [o, label(o)];
          return (
            <option key={v} value={v}>
              {t}
            </option>
          );
        })}
      </select>
    </div>
  );
}
export function Verify({ children }: { children: ReactNode }) {
  return (
    <label className="check-label field full">
      <input name="verified" type="checkbox" required />
      {children}
    </label>
  );
}
