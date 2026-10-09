import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Files, ListChecks, ShieldCheck, WalletCards } from 'lucide-react';
import { apiUrl, createApi, errorMessage } from './api';
import { AppContext, useApp, type DialogState } from './context';
import { Queue, type Filter } from './Queue';
import { CaseDetail, type CaseAction } from './CaseDetail';
import { EditCase, CaseActionDialog, ReverseCredit } from './Actions';
import { Documents, LinkExisting, Matches, UploadDialog } from './Documents';
import { EvidenceReview } from './EvidenceReview';
import { ImportDialog } from './Import';
import { Guide, Outcomes } from './Outcomes';
import { Button, Modal, Notice } from './ui';
import type { Api, Claim, Currency, Detail, Evidence, View, Workspace } from './types';

export function App() {
  const [workspace, setWorkspace] = useState<Workspace>('demo');
  return <WorkspaceApp key={workspace} workspace={workspace} setWorkspace={setWorkspace} />;
}
function WorkspaceApp({
  workspace,
  setWorkspace,
}: {
  workspace: Workspace;
  setWorkspace: (w: Workspace) => void;
}) {
  const [token, setToken] = useState(''),
    [view, setView] = useState<View>('queue'),
    [cases, setCases] = useState<Claim[]>([]),
    [detail, setDetail] = useState<Detail | null>(null),
    [dialog, setDialog] = useState<DialogState | null>(null),
    [currency, setCurrency] = useState<Currency>('GBP'),
    [search, setSearch] = useState(''),
    [filter, setFilter] = useState<Filter>('all'),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [message, setMessage] = useState(''),
    [revision, setRevision] = useState(0);
  const controller = useRef(new AbortController()),
    activeCase = useRef<string | null>(null),
    generation = useRef(0),
    messageTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const api = useMemo<Api>(
    () =>
      <T,>(path: string, body?: unknown) =>
        createApi(workspace, token, controller.current.signal)<T>(path, body),
    [workspace, token],
  );
  const url = useCallback((p: string) => apiUrl(p, workspace), [workspace]);
  const toast = useCallback((text: string) => {
    if (controller.current.signal.aborted) return;
    setMessage(text);
    clearTimeout(messageTimer.current);
    messageTimer.current = setTimeout(() => setMessage(''), 5000);
  }, []);
  // A controller per mounted workspace prevents late responses appearing in another workspace.
  // StrictMode replays effects; replace the controller on setup rather than reusing an aborted signal.
  useEffect(() => {
    const boot = new AbortController();
    setLoading(true);
    createApi(
      workspace,
      '',
      boot.signal,
    )<{ token: string }>('bootstrap')
      .then((r) => {
        setToken(r.token);
        return createApi(workspace, r.token, boot.signal)<{ cases: Claim[] }>('cases');
      })
      .then((r) => {
        setCases(r.cases);
        setLoading(false);
      })
      .catch((e) => {
        if (!boot.signal.aborted) {
          setError(errorMessage(e));
          setLoading(false);
        }
      });
    return () => {
      boot.abort();
    };
  }, [workspace]);
  useEffect(() => {
    controller.current = new AbortController();
    return () => {
      controller.current.abort();
      ++generation.current;
      clearTimeout(messageTimer.current);
    };
  }, []);
  const refresh = useCallback(async () => {
    const current = activeCase.current,
      request = ++generation.current;
    const [r, d] = await Promise.all([
      api<{ cases: Claim[] }>('cases'),
      current ? api<Detail>(`cases/${current}`) : Promise.resolve(null),
    ]);
    if (request !== generation.current) return;
    setCases(r.cases);
    if (activeCase.current === current && d) setDetail(d);
    setRevision((r) => r + 1);
  }, [api]);
  const openCase = useCallback(
    async (id: string) => {
      const request = ++generation.current;
      setError('');
      try {
        const d = await api<Detail>(`cases/${id}`);
        if (request !== generation.current) return;
        activeCase.current = id;
        setDetail(d);
        setView('queue');
      } catch (e) {
        if (request === generation.current) toast(errorMessage(e));
      }
    },
    [api, toast],
  );
  const review = useCallback(
    async (id: string, caseId = '', next = false) => {
      try {
        const d = await api<Evidence>(`documents/${id}`);
        setDialog({ kind: 'review', document: d, caseId, next });
      } catch (e) {
        toast(errorMessage(e));
      }
    },
    [api, toast],
  );
  function navigate(next: View) {
    ++generation.current;
    activeCase.current = null;
    setDetail(null);
    setView(next);
    setError('');
  }
  function action(a: CaseAction) {
    if (!detail) return;
    if (a === 'edit') setDialog({ kind: 'edit', claim: detail.case });
    else if (a === 'upload') setDialog({ kind: 'upload', caseId: detail.case.id });
    else if (a === 'link') setDialog({ kind: 'link', caseId: detail.case.id });
    else setDialog({ kind: 'action', action: a, detail });
  }
  const nav = [
    { id: 'queue' as const, title: 'Work queue', icon: ListChecks },
    { id: 'documents' as const, title: 'Evidence library', icon: Files },
    { id: 'credits' as const, title: 'Credits & outcomes', icon: WalletCards },
    { id: 'guide' as const, title: 'Getting started', icon: BookOpen },
  ];
  return (
    <AppContext.Provider
      value={{ api, workspace, cases, url, refresh, openCase, toast, setDialog, review }}
    >
      <aside className="sidebar">
        <a
          className="brand"
          href="#queue"
          onClick={(e) => {
            e.preventDefault();
            navigate('queue');
          }}
        >
          <span className="brand-mark">CL</span>ClaimLedger
        </a>
        <div className="nav-label">Your workspace</div>
        <nav id="nav" aria-label="Workspace navigation">
          {nav.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? 'active' : ''}`}
              aria-current={view === n.id ? 'page' : undefined}
              onClick={() => navigate(n.id)}
            >
              <n.icon size={19} strokeWidth={1.6} className="shrink-0" />
              <span className="!text-[14px] !w-auto !text-left">{n.title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <label htmlFor="workspace">Workspace</label>
          <select
            id="workspace"
            value={workspace}
            disabled={!!dialog || loading}
            onChange={(e) => setWorkspace(e.target.value as Workspace)}
          >
            <option value="demo">Demo · fictional records</option>
            <option value="live">Live · your records</option>
          </select>
          <p className="flex gap-2 items-start max-[760px]:hidden">
            <ShieldCheck size={15} className="mt-1 shrink-0" />
            <span>
              Private local workspace
              <br />
              Saved on this computer
            </span>
          </p>
          <div className="profile">
            <span className="avatar">YO</span>
            <div>
              <strong>Your workspace</strong>
              <small>Single operator</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <div className={`demo-banner ${workspace === 'live' ? 'live-banner' : ''}`}>
          {workspace === 'demo' ? (
            <>
              <span className="pill demo">DEMO</span>Fictional records to explore the workflow. Your
              live workspace is separate.
            </>
          ) : (
            <>
              <strong>LIVE</strong>Your records · stored on this computer
            </>
          )}
        </div>
        <div id="content">
          {error && (
            <Notice tone="error">
              <strong>Could not load ClaimLedger</strong>
              {error} Refresh after starting the local server.
            </Notice>
          )}
          {loading ? (
            <p className="loading" role="status">
              Loading your workspace…
            </p>
          ) : (
            !error && (
              <>
                {detail ? (
                  <CaseDetail
                    detail={detail}
                    back={() => navigate('queue')}
                    action={action}
                    review={(id) => void review(id, detail.case.id)}
                    unlink={async (id) => {
                      try {
                        await api(`documents/${id}/unlink`, { case_id: detail.case.id });
                        await refresh();
                        toast('Unlinked. Original retained in the library.');
                      } catch (e) {
                        toast(errorMessage(e));
                      }
                    }}
                    url={url}
                  />
                ) : view === 'queue' ? (
                  <Queue
                    cases={cases}
                    currency={currency}
                    setCurrency={setCurrency}
                    search={search}
                    setSearch={setSearch}
                    filter={filter}
                    setFilter={setFilter}
                    openCase={(id) => void openCase(id)}
                    newCase={() => setDialog({ kind: 'edit' })}
                    importCases={() => setDialog({ kind: 'import' })}
                  />
                ) : view === 'documents' ? (
                  <Documents key={revision} />
                ) : view === 'credits' ? (
                  <Outcomes key={revision} currency={currency} setCurrency={setCurrency} />
                ) : (
                  <Guide />
                )}
              </>
            )
          )}
        </div>
        <footer className="app-footer">
          ClaimLedger<span>Evidence first. Every claim accounted for.</span>
        </footer>
      </main>
      {dialog && (
        <Dialog
          key={dialog.kind === 'review' ? `${dialog.document.id}-${dialog.caseId}` : dialog.kind}
          state={dialog}
        />
      )}
      {message && (
        <div id="toast" className="visible" role="status" aria-live="polite">
          {message}
        </div>
      )}
    </AppContext.Provider>
  );
}
function Dialog({ state: d }: { state: DialogState }) {
  // All interactions render through React; originals and packet downloads remain same-origin API links.
  if (d.kind === 'edit') return <EditCase claim={d.claim} />;
  if (d.kind === 'action') return <CaseActionDialog action={d.action} detail={d.detail} />;
  if (d.kind === 'upload') return <UploadDialog caseId={d.caseId} />;
  if (d.kind === 'matches') return <Matches />;
  if (d.kind === 'review')
    return <EvidenceReview document={d.document} caseId={d.caseId} next={d.next} />;
  if (d.kind === 'link') return <LinkExisting caseId={d.caseId} />;
  if (d.kind === 'import') return <ImportDialog />;
  if (d.kind === 'reverse') return <ReverseCredit id={d.id} />;
  return <ExportReady id={d.id} />;
}
function ExportReady({ id }: { id: string }) {
  const { url, setDialog } = useApp();
  return (
    <Modal title="Packet ready" sub="No submission has been sent." close={() => setDialog(null)}>
      <div className="modal-body">
        <Notice>The ZIP contains the summary, original documents and evidence manifest.</Notice>
        <div className="actions">
          <a className="btn" href={url(`exports/${id}/pdf`)}>
            Download PDF
          </a>
          <a className="btn primary" href={url(`exports/${id}/zip`)}>
            Download ZIP + originals
          </a>
          <Button onClick={() => setDialog(null)}>Done</Button>
        </div>
      </div>
    </Modal>
  );
}
