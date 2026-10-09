import type { Api, FilePayload, Workspace } from './types';

export function apiUrl(path: string, workspace: Workspace) {
  return `/api/${path}${path.includes('?') ? '&' : '?'}workspace=${workspace}`;
}
export function createApi(workspace: Workspace, token: string, signal?: AbortSignal): Api {
  return async <T>(path: string, body?: unknown): Promise<T> => {
    const response = await fetch(apiUrl(path, workspace), {
      signal,
      ...(body === undefined
        ? {}
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-ClaimLedger-Token': token },
            body: JSON.stringify(body),
          }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
    return result as T;
  };
}
export async function filePayload(file: File): Promise<FilePayload> {
  if (file.size > 10 * 1024 * 1024) throw new Error('Maximum file size is 10 MB.');
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve({ filename: file.name, data: String(reader.result).split(',')[1] });
    reader.onerror = () => reject(new Error('Could not read file.'));
    reader.readAsDataURL(file);
  });
}
export const money = (cents: number, currency = 'GBP') =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(cents / 100);
export const label = (s: string) => s.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase());
export function today() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The operation could not be completed.';
}
