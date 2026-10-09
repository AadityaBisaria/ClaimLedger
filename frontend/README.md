# ClaimLedger frontend

React 19, TypeScript with strict checking, Tailwind CSS 4, Vite 7 and Lucide icons. This is the operational app, with the existing forest-green, lime and paper design preserved. It uses React state and components throughout; it does not wrap the old HTML renderer.

## Build and validate

Requires Node 22.18+ and pnpm 11. The lockfile pins the tested dependency versions.

```powershell
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm test
pnpm run build
```

The Python server serves `dist/index.html` and its compiled assets. The distribution is included, so the normal ClaimLedger launcher needs only Python. Node is needed when changing the frontend. After rebuilding, refresh the browser; restarting Python is unnecessary for asset-only changes.

For development, start the Python server on port 8765 and run `pnpm dev` in this folder. Open the Vite address printed in the terminal. Vite proxies `/api` to the loopback backend; it supplies that backend's local Host/Origin while retaining the request token. The Python Host, Origin and token checks remain in force. Development and production use the same SQLite data, so choose Demo when testing.

## Components

| File | Responsibility |
| --- | --- |
| `App.tsx`, `context.ts` | Workspace lifecycle, navigation, request cancellation, dialogs |
| `types.ts`, `api.ts` | Typed domain models, workspace-bound API, money and file helpers |
| `Queue.tsx`, `CaseDetail.tsx` | Work queue, evidence readiness and audit trail |
| `Documents.tsx` | Bulk uploads, library, suggested matches and shared originals |
| `EvidenceReview.tsx` | Per-SKU review, PDF/image previews, page OCR and source highlights |
| `Actions.tsx`, `Import.tsx`, `Outcomes.tsx` | Case forms, import validation, exports, credits and guidance |
| `ui.tsx`, `styles.css` | Accessible native dialogs, reusable UI and Tailwind design tokens |

Tailwind handles reusable card/metric layout, spacing, responsive overrides and design tokens. Custom component CSS preserves the established table, evidence-review and dialog details. There is no UI-template dependency or remote font/CDN requirement. All production assets load from the local server.

Request handlers capture a workspace. Switching workspaces cancels old requests and remounts the workspace; dialogs keep the selector disabled while open. Quantity suggestions never confirm evidence, and selecting a different SKU, page or candidate clears the review checkbox. The backend remains authoritative for versions, readiness, amounts and lifecycle rules.

`pnpm run format` formats source; `pnpm run format:check` checks it. Browser smoke checks are documented in the parent `VALIDATION.md`. Legacy files in the parent `static/` folder are retained as a reference and are not served.
