# Neoffice fork markers

Map of **our** divergence from upstream in this repository. Everything that can carry a
comment carries a `//// Neoffice — …` marker in place; this file holds what cannot:
non-commentable files, generated artifacts, and the hunks where a comment would change the
rendered output.

At the next upstream merge, `grep -rn "////"` in the source plus this file give the complete
picture of what is ours and why.

---

## mint

Fork of **The-Commit-Company/mint**, branch `version-15` of `bvisible/mint`.

### Base and attribution (established 2026-09-04)

| Fact | Value |
|---|---|
| Upstream remote | `https://github.com/The-Commit-Company/mint.git` |
| Upstream branches | `main` (tip `93f6235`), `develop` (tip `69ac9e5`, the upstream default) |
| `merge-base origin/version-15 upstream/develop` | `feb81798f673471c0f97cd2e2ab8ed5241d53ed0` |
| `merge-base origin/version-15 upstream/main` | `feb81798…` and `20726e6…` (`v1.3.1`) |
| Tip of an upstream branch contained in ours (`--is-ancestor`) | **none** — neither `upstream/main` nor `upstream/develop` is an ancestor of `origin/version-15` |
| **BASE used for the marker pass** | **`feb81798f673471c0f97cd2e2ab8ed5241d53ed0`** — *"fix: set a max width for against account (#115)"*, Nikhil Kothari, 2026-02-22. It is the newest upstream commit contained in our history (we merged `upstream/develop` at that point in `47b3178`), and the merge-base with **both** upstream branches. |

**Attribution proof**

- `git rev-list --count origin/version-15 ^feb81798…` → **276**
- `git rev-list --count origin/version-15 ^upstream/main ^upstream/develop` → **248** — these
  248 are ours. The 28 extra commits of the first count are upstream merge commits reachable
  from `v1.3.1` (`20726e6`) but not from `feb81798`; **zero** of them is a non-merge commit,
  so they carry no content of their own.
- Authors of the 248: Jérémy Christillin 175, `github-actions[bot]` 45 (built assets),
  Daniel (`daniel@neoffice.io`) 17, barredterra 4, Nikhil Kothari 3, Nora 2, NeoService 1,
  Claude Sonnet 4.5 1.
- `git cherry upstream/develop origin/version-15` → 240 `+`, 0 `=`: no commit of ours has a
  patch-equivalent upstream.
- **No `(cherry picked from commit …)` line anywhere in the range.** Three commits are
  nonetheless hand-made backports, identified by identical subject and identical patch:
  | ours | upstream | subject |
  |---|---|---|
  | `4969a76` | `05f708b` | fix: type filter on bank transaction list |
  | `768ef4c` | `5ba8c6b` | fix: apply user permissions when fetching bank accounts |
  | `64c3ad6` | `6417282` | fix: use standard function to parse date format |
  They are marked in place as `backport of upstream <sha> (cherry-pick), drop at the merge`.
- `git diff --stat feb81798…HEAD` → **194 files changed, 36 103 insertions, 1 083 deletions**.

> ⚠️ **A large part of that diff is NOT ours.** Upstream released **v1.5.0 / v1.5.2 after
> `feb81798`** and, instead of merging their branch, we carried the release in by hand
> (`89e7929` Daniel, then `2bdac9c`). Files that are **byte-identical to `upstream/develop`
> today** are marked *"NOT ours … take upstream's at the merge"*: `frontend/.env.production`,
> `frontend/src/components/ui/{card,table,file-dropzone,empty}.tsx`,
> `frontend/src/components/features/BankReconciliation/BankTransactionList.tsx`,
> `frontend/src/components/features/BankStatementImporter/{CSV/CSVImport.tsx,import_utils.ts}`,
> `frontend/src/pages/BankStatementImporter.tsx`,
> `frontend/src/types/Mint/MintBankStatementImportLog.ts`, and the whole
> `mint_bank_statement_import_log` / `_template` / `_template_columns` doctypes.

---

### Non-commentable files (no comment syntax — listed here so the marker check accepts them)

#### `package.json`
Ours. Upstream's `build` script is `cd frontend && yarn build`. Ours short-circuits when
`mint/public/mint/assets` already exists (`[skip-build]`), because this branch **commits the
build**: the client VMs do not have the RAM to run vite, so `bench` must not rebuild on
install. `FORCE_REBUILD=1` or the added `build:force` target does the real build.

#### `frontend/package.json`
Ours, four changes:
- `build` and the added `build:force` prepend `NODE_OPTIONS=--max-old-space-size=4096` — vite
  runs out of heap on this project with Node's default limit;
- dependency `@neoffice/frappe-sidebar-react` pinned to a git SHA — the shared NeoCockpit shell
  the embedded `/mint` renders inside (family **B** of the cockpit consumers: re-pin **and**
  rebuild when the cockpit changes);
- dependency `@neoffice/nora-learn-react` pinned to a git SHA — the in-app tutorial overlay;
- `react-router` / `react-router-dom` — required by `App.tsx`; upstream relies on the
  transitive copy.

#### `frontend/.env.production`
**NOT ours.** `VITE_BASE_NAME='mint'`, identical to `upstream/develop`. Hand-carried with the
v1.5.0 port (`89e7929`). Take upstream's at the merge.

#### `mint/mint/doctype/mint_bank_statement_import/mint_bank_statement_import.json`
Mixed. Compared with `upstream/develop`, **these fields are ours only**:

| field | type | why |
|---|---|---|
| `column_break_main`, `upload_area` | layout | the form was rebuilt around the import wizard |
| `document_status` | Select (Draft/Submitted/Cancelled) | `docstatus` is an integer the list view cannot render as a label (`6d264d7`) |
| `section_break_ocr`, `column_break_ocr` | layout | OCR block |
| `ocr_status` | Select ("", Pending, Processing, Completed, Failed) | asynchronous NORA OCR of PDF statements (`b714fd5`) |
| `document_scan_name` | Link → Document Scan | traceability of every OCR run (`f715b79`) |
| `section_break_xml`, `column_break_xml`, `section_break_txn`, `txn_spacer` | layout | CAMT.053 block |
| `bank_statement_id` | Data | the `<MsgId>` of the CAMT file |
| `opening_balance`, `closing_balance` | Currency | balances read from the CAMT statement |
| `import_summary` | Small Text | one-line result shown as a dashboard headline |
| `content_hash` | Data | SHA of the uploaded file; without it a re-sent statement created every Bank Transaction twice (`5bb4045`) |

`currency` is **upstream's** field (v1.5.0), not ours. Property changes that are ours:
`file_type` gains the `XML` option plus `default: PDF`, `hidden`, `read_only` (the wizard sets
it); `file` becomes `hidden` (same reason); `bank_account.reqd` 1 → 0 and `status.reqd` 1 → 0
(the wizard creates the document before those are known); `amended_from` hidden.
**No upstream field was removed.**

> Several of these are candidates to become **Custom Fields** instead of fork changes at the
> next merge — `document_status`, `import_summary`, `content_hash` and the OCR trio are pure
> additions with no upstream counterpart and would survive an upstream schema change untouched.

#### `mint/mint/doctype/mint_bank_statement_import_transactions/mint_bank_statement_import_transactions.json`
Mixed. **Ours only** (all added for the CAMT.053 flow, `5bb4045` → `957a5b9`):
`unique_reference`, `party_name`, `party_iban`, `credit_debit`, `status`,
`existing_bank_transaction`, `invoice_matches`, `party_match`, `matched_amount`.
The `columns` widths and the `in_list_view` flips on `reference`, `imported` and
`string_amount` are **upstream's** v1.5.0 (`89e7929`). No upstream field removed.

#### `mint/mint/doctype/mint_bank_statement_import_log/mint_bank_statement_import_log.json`
#### `mint/mint/doctype/mint_bank_statement_import_template/mint_bank_statement_import_template.json`
#### `mint/mint/doctype/mint_bank_statement_import_template_columns/mint_bank_statement_import_template_columns.json`
**NOT ours.** Upstream v1.5.0 doctypes, hand-carried by `89e7929`. Field for field identical to
`upstream/develop`. Take upstream's at the merge and drop the header markers in their `.py`.

---

### Files the marker checker skips, listed for completeness

| Path | Whose | Note |
|---|---|---|
| `.github/workflows/build-frontend.yml` | ours | builds the SPA in CI and commits the artifacts (the commit-the-build pattern) |
| `.github/workflows/tests.yml` | ours | caller of the fleet CI (`bvisible/neoffice-ci`) |
| `.github/workflows/fork-markers.yml` | ours | this discipline, enforced on every push to `version-15` |
| `.github/workflows/upstream-preview.yml` | ours | weekly bench on upstream `frappe`/`erpnext` |
| `mint/locale/fr.po` | ours | French catalogue (2 611 lines). Upstream ships EN + DE only. Generated once by `generate_french_translations.py`, maintained since by the PO workflow. **PO only, never a `translations/*.csv`.** |
| `frontend/yarn.lock`, `frontend/package-lock.json` | ours | consequence of the four dependency changes above. `package-lock.json` is an added file: **the project uses yarn**, so this second lockfile is redundant and should be deleted rather than merged. |
| `mint/public/mint/assets/**` | generated | vite output committed on purpose (see below). Includes the bank-logo SVGs and PNGs copied from `frontend/public/assets/`. |
| `mint/public/._mint` | **accident** | AppleDouble resource fork committed by `89e7929` from a macOS checkout. Binary, 163 bytes, no purpose. **Delete it.** |

---

### Generated artifacts — mark the source, never these

`mint/public/mint/index.html`, `mint/www/mint.html` and everything under
`mint/public/mint/assets/` are the **vite output of `frontend/`**, committed because the client
VMs cannot run the build (see `.gitignore`, where upstream's two ignore lines are kept commented
out, and `CLAUDE.md`). `mint/www/mint.html` is then copied from `mint/public/mint/index.html`
by `yarn copy-html-entry`.

**Never write a marker into any of them** — proven on 2026-09-04: a *"GENERATED FILE, do not
edit"* comment added to the two HTML entry points was wiped by the very next
`build-frontend` run. What keeps them marked is the markers in **`frontend/index.html`**,
which vite carries through into the build output (five marker lines survive in
`mint/www/mint.html` and `mint/public/mint/index.html`). The same holds for
`mint/public/mint/assets/bank-logos/*.svg`: they are copies of
`frontend/public/assets/bank-logos/*.svg`, and their markers come from the source files.
**Mark the source, never the artifact.**

---

### Hunks that cannot carry a marker in place

| Where | Why | What was done instead |
|---|---|---|
| `mint/apis/bank_reconciliation.py`, `Args:` block of `create_bank_entry_and_reconcile` | inside a docstring: a `#` line there would become part of the documented text | marker placed on the line **above the opening `"""`** |
| `mint/mint/doctype/mint_bank_statement_import/mint_bank_statement_import.py`, docstring of `_populate_transactions` | same | same |
| `frontend/public/assets/bank-logos/Cembra.svg`, `…/Banque_Cantonale_du_Valais.svg` | single-line minified SVG with no end-of-file newline; the XML declaration must stay first, so nothing can be inserted above it | marker appended in the XML **epilog** (after `</svg>`). This is the only place in the pass where a non-comment line changed: adding the marker line necessarily adds the missing newline at end of file. Whitespace only, no content change. |
| `frontend/src/components/features/BankReconciliation/*.tsx`, JSX children | `//` in JSX children renders as text | `{/* //// Neoffice — … */}` used there, `//` everywhere else (attribute lists included: JSX allows JS comments between attributes) |

### Decisions recorded

- `mint/api/__init__.py`, `mint/mint/doctype/mint_bank_statement_import_log/__init__.py`,
  `…_template/__init__.py`, `…_template_columns/__init__.py` are **empty** and left unmarked:
  a marker in an empty package file carries no information and the three doctype ones are
  upstream's anyway.
- `mint/apis/statement_import.py` differs from `upstream/develop` by **trailing whitespace
  only** (five lines in `get_column_mapping`). Take upstream's file at the merge.
- `frontend/src/components/features/BankStatementImporter/CSV/CSVRawDataPreview.tsx` and
  `…/StatementDetails.tsx` differ from `upstream/develop` by **one line each** (an `_()` wrap
  around a tooltip). Take upstream's file and re-apply that single wrap.
