import { createContext, useContext } from 'react';
import type { Api, Claim, Detail, Evidence, Workspace } from './types';
import type { CaseAction } from './CaseDetail';
export type DialogState =
  | { kind: 'edit'; claim?: Claim }
  | { kind: 'action'; action: CaseAction; detail: Detail }
  | { kind: 'upload'; caseId?: string }
  | { kind: 'matches' }
  | { kind: 'review'; document: Evidence; caseId: string; next?: boolean }
  | { kind: 'link'; caseId: string }
  | { kind: 'import' }
  | { kind: 'reverse'; id: string }
  | { kind: 'export'; id: string };
export interface AppContextValue {
  api: Api;
  workspace: Workspace;
  cases: Claim[];
  url: (p: string) => string;
  refresh: () => Promise<void>;
  openCase: (id: string) => Promise<void>;
  toast: (t: string) => void;
  setDialog: (d: DialogState | null) => void;
  review: (id: string, caseId?: string, next?: boolean) => Promise<void>;
}
export const AppContext = createContext<AppContextValue | null>(null);
export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('Workspace context is missing.');
  return context;
}
