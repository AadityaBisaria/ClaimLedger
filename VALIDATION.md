# MVP verification — 4 October 2026

## Automated: 59 backend tests and 6 frontend tests passed

Run with the bundled Python runtime and `-m unittest discover -s tests -v`.

Validated integer money arithmetic; malformed and ambiguous amounts; deadline-source requirements; CSV/XLSX imports; duplicate and conflicting rows; transaction rollback; source-row provenance; original file deduplication and path handling; invalid PDFs; manual review for scans; reference suggestions remaining unconfirmed; missing/pallet-only/subject-to-count evidence; unit and quantity conflicts; impossible shortage quantities; draft/final gating; unchanged original hashes inside ZIPs; stale export and stale form protection; partial approvals and credits; duplicate/oversized/concurrent credit rejection; credit reversal with retained history; database reopen; workspace access; HTTP Host/Origin/token protections; static-file traversal rejection; and template integrity.

React/TypeScript passed strict type checking and the Vite production build. Six frontend request tests cover captured workspace/token semantics, page-preview queries, backend conflict errors, request cancellation, oversized evidence and currency display. Backend tests use temporary stores and leave Live data untouched.

## Browser checks completed

- Dashboard displays distinct readiness, approval and credit figures.
- Imported `fixtures/demo-import.csv` through the actual file picker, mapped columns, validated and committed the fictional record.
- Uploaded `fixtures/demo-invoice.txt`; confirmed extracted suggestions against the original and saved human-reviewed fields. Missing dispatch and delivery evidence still blocked final export.
- Generated a reviewed PDF/ZIP through the review dialog for fictional NF-1043.
- Prepared fictional QA-WORKFLOW and recorded submission, a £200 partial approval and a £75 actual credit through the UI. Aggregate credited and awaiting-credit totals reconciled.
- Confirmed the empty Live workspace after restarting the server. Demo records persisted.
- Inspected desktop and 390px-wide layouts. Tables scroll horizontally on small screens; primary actions remain available.
- Exercised the optional read-only WebMCP listing tool in the earlier vanilla frontend. That optional tool is not registered by the React frontend.
- No browser console errors were observed in the checked flows.
- Reversed the fictional QA credit through **Correct entry**. The £75 original remained visible with its reason; credited totals fell from £135 to £60 and awaiting credit rose from £185 to £260.
- Replaced the browser-dependent embedded PDF viewer after visual QA found a blank preview. PDF source pages now render locally using PDFium; the original invoice was visibly verified beside the form. Source-page bounds are tested, as are native Excel date cells.

## Export inspection

Rendered both pages of a generated fictional reviewed packet and inspected them visually. Text was legible, page margins were intact, originals were indexed with hashes and source pages, and the demo label was visible. A synthetic example is retained at `verification/reviewed-demo-packet.pdf`.

## What remains unvalidated

No supplier has provided real deduction cases. There is no evidence yet of time saved, retailer acceptance, increased recovery or willingness to pay. No live retailer portal, email or financial system was contacted. There is no claim of universal UK, Canadian, US or European retailer-policy compliance.

Before a paid pilot: obtain consented/redacted historical cases, confirm one retailer's actual process, compare operator time and output quality against the current workflow, and prioritize multi-line evidence mapping if the cases require it. Hosted deployment would need a separate security and multi-user implementation.

## Multi-SKU, bulk upload and OCR upgrade

Added 14 checks for line-review isolation, independent stale versions, unchanged packet fingerprints when another SKU is reviewed, deduplication preserving mappings, unlink isolation, source-reference bounds, frozen extraction snapshots, exact matching with conflicts, delimited rows, legacy migration, real local image OCR and scanned PDF page-2 OCR with unchanged original hashes.

Browser verification imported two MULTI-2001 lines and uploaded four files in one picker operation. All four originals were saved; three text PDFs and one OCR image produced eight exact reference/SKU suggestions. Confirming TEA-MULTI reduced the queue to seven suggestions while OAT-MULTI remained unconfirmed. The same scan correctly prefilled 50 cases for tea and 80 cases for oats. Clicking an OCR quantity highlighted its location in the source image. Confirming the tea invoice, dispatch and receipt made that line ready while the oats line still required shipping evidence.

The existing database retained 7 cases, 13 documents, 16 links, 2 credits, 53 audit events and 3 exports at migration. All 16 original confirmed links retained their reviewed evidence. SQLite integrity and foreign-key checks passed. Additional fictional demonstration cases were added only to Demo; Live was left untouched.

Known limits: OCR operates per page, and bulk OCR processes only the first page of scans. Candidate parsing handles labelled fields and delimited line rows; arbitrary retailer table layouts still require manual mapping. Low-confidence and even high-confidence OCR are unverified until the operator reviews the original. Shared documents now support multiple SKU cases; split shipments remain outside automatic readiness.

Generated the updated reviewed packet through the browser. Its manifest contained only TEA-MULTI's reviewed 50-case quantities, retained OCR source snippets, and original files with matching hashes. Both PDF pages rendered successfully; the evidence-index page was visually checked for readable source snapshots and intact margins. The example is saved as `verification/multisku-reviewed-demo.pdf`.

## React, TypeScript and Tailwind migration

The production UI now renders through React components with strict TypeScript models, Tailwind 4 theme/utility styles and Lucide icons. The existing forest-green sidebar, lime brand mark, pale-green metrics, paper background, compact tables and evidence-focused dialogs were retained. The Python API, SQLite schema, original files and packet generator were not replaced. Compiled assets are included under `frontend/dist/`, so the normal launcher still runs one Python process.

Completed browser checks on the React production build:

- Loaded existing cases, readiness, credits, packet history, original previews and audit details from the same database.
- Saved an existing invoice review; the reviewer and activity trail updated without losing other source documents.
- Confirmed the OAT-MULTI invoice at 80 cases; the suggested queue fell from four to three and the TEA-MULTI invoice suggestion remained unconfirmed.
- Reran local OCR on the scanned invoice. Tea remained 50 cases; selecting its quantity highlighted the matching source region, and the verification checkbox stayed unchecked.
- Generated a reviewed NF-1043 packet and received PDF/ZIP download links.
- Imported the two-line CSV fixture through the picker, mapped columns and validated it. Both duplicates were skipped and the zero-record commit button was disabled.
- Bulk uploaded three existing PDF originals. Each was reported as already saved; existing mappings were retained.
- Created fictional QA-REACT-1001 in CAD at 10.01, saved owner/follow-up/notes and recorded an accepted outcome.
- Attempted a £201 credit against £200 remaining approval; the form displayed the backend cap error. Recorded £1.01 and reversed it through the credits form. The original entry and reversal reason remained visible; totals returned to their prior values.
- Switched to Live and verified an empty queue and zero totals. No Live cases were created.
- Inspected a phone-sized viewport. Fixed the cramped mobile sidebar; the final page width fits the viewport while deduction tables scroll within their container. Screenshot: `verification/react-mobile.jpg`.
- Loaded Vite development mode, including React StrictMode, and saved notes through its token-authenticated API proxy. No console errors were observed in that check. Returned to the production URL and stopped the extra Vite process.

Three additional HTTP tests verify compiled JS/CSS MIME types and restrictive CSP, deny legacy scripts/frontend sources, and reject encoded asset traversal and unknown assets. Formatting checks pass. SQLite integrity is `ok`, foreign-key errors are zero, and Live has zero cases. All UI writes above affected fictional Demo records only.

The final dashboard screenshot is `verification/react-dashboard.jpg`. The former vanilla sources remain in `static/` as a reference and are not publicly served. The normal local app remains open at `http://127.0.0.1:8765/`.
