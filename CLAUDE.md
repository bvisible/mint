# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mint is an open-source bank reconciliation tool for ERPNext, built as a Frappe Framework application with a React-based frontend. The app is accessible at the `/mint` path on an ERPNext site and provides an enhanced interface for reconciling bank transactions.

## Architecture

### Backend (Frappe App)
- **Framework**: Frappe Framework (Python)
- **Integration**: Built on top of ERPNext's accounting module
- **Structure**: Standard Frappe app structure
  - `mint/`: Main Python package
    - `mint/doctype/`: Custom DocTypes for Mint functionality
      - `mint_bank_transaction_rule/`: Rules for automatic transaction classification
      - `mint_bank_statement_import/`: Bank statement import functionality
      - `mint_settings/`: Global app settings
    - `apis/`: Whitelisted API methods
      - `bank_reconciliation.py`: Core reconciliation logic
      - `transactions.py`: Bank transaction operations
      - `rules.py`: Rule evaluation and management
      - `bank_account.py`: Bank account utilities
      - `google_ai.py`: Google Cloud Document AI integration for PDF parsing
  - `hooks.py`: Frappe hooks configuration
    - Registers the app in ERPNext with route `/mint`
    - Scheduler job runs hourly for rule evaluation: `mint.apis.rules.scheduler_run_rule_evaluation`
  - `public/`: Static assets (compiled frontend builds go here)
  - `www/`: Web pages/routes

### Frontend (React SPA)
- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS v4 with shadcn/ui components
- **State Management**: Jotai for atomic state
- **Data Fetching**: frappe-react-sdk (custom ERPNext/Frappe integration)
- **Structure**:
  - `frontend/src/`
    - `pages/BankReconciliation.tsx`: Main reconciliation interface
    - `components/`
      - `features/BankReconciliation/`: Feature-specific components
      - `features/Settings/`: Settings interface
      - `common/`: Shared components
      - `ui/`: shadcn/ui component library
    - `types/`: TypeScript type definitions for Frappe/ERPNext doctypes
    - `lib/`: Utility functions
    - `hooks/`: Custom React hooks

### Build & Deployment
The frontend React app is built and bundled into the `mint/public/mint/` directory, making it accessible as a static resource within the Frappe app. The build process also copies the HTML entry point to `mint/www/mint.html` to enable the `/mint` route.

## Development Commands

### Frontend Development
```bash
# Install frontend dependencies
yarn install
# or from root:
yarn postinstall

# Start development server (runs on port 8080 with proxy to Frappe backend)
cd frontend && yarn dev
# or from root:
yarn dev

# Build for production
cd frontend && yarn build
# or from root:
yarn build

# Lint frontend code
cd frontend && yarn lint
```

### Backend Development
This is a Frappe app, so it must be installed in a Frappe bench:

```bash
# Install the app in your bench
bench get-app https://github.com/The-Commit-Company/mint

# Install on a site
bench --site [sitename] install-app mint

# Start Frappe development server
bench start
```

### Testing
No test suite is currently configured in the repository.

## Key Integration Points

### ERPNext Dependencies
Mint heavily integrates with ERPNext's accounting module:
- **Bank Transaction**: Core doctype used for tracking transactions
- **Payment Entry**: Used for creating payment vouchers
- **Journal Entry**: Used for bank entries and transfers
- **Bank Account**: Extended with custom fields and logic
- Uses ERPNext functions like `create_payment_entry_bts` and `create_journal_entry_bts` from `bank_reconciliation_tool`

### API Pattern
Backend APIs in `mint/apis/` are decorated with `@frappe.whitelist()` to expose them to the frontend. The React frontend calls these via the frappe-react-sdk's `useFrappePostCall` and `useFrappeGetCall` hooks.

### Reconciliation Workflow
The core reconciliation flow:
1. Load unreconciled bank transactions for a date range
2. Search for matching vouchers (Payment Entry, Journal Entry) based on amount, date, reference
3. Match transactions via `reconcile_vouchers()` API
4. Or create new entries: Bank Entry (Journal Entry), Payment Entry, or Internal Transfer
5. Track reconciliation status and allow undo operations

### Rule Engine
The `Mint Bank Transaction Rule` doctype allows users to create rules that automatically classify transactions based on:
- Transaction type (Deposit/Withdrawal)
- Description patterns
- Amount ranges
- Date ranges

Rules suggest actions (create Bank Entry, Payment Entry, or Transfer) when matched. The scheduler evaluates rules hourly.

## Code Conventions

### Python (Backend)
- Follow Frappe framework conventions
- Use type hints where possible (enabled via `export_python_type_annotations = True`)
- Whitelisted methods should validate permissions before operations
- Use `frappe.throw()` for user-facing errors with translated messages via `_()`

### TypeScript (Frontend)
- Strict mode enabled
- Component files use `.tsx` extension
- Use functional components with hooks
- Types are generated/maintained in `src/types/` matching Frappe DocTypes
- Use shadcn/ui components from `components/ui/`
- Path alias `@/` maps to `src/`

### Styling
- Tailwind CSS utility classes
- No custom CSS except for `index.css` (base styles)
- Use shadcn/ui component variants via `class-variance-authority`

## Dependencies

### Key Python Dependencies
- `frappe` (managed by bench)
- `erpnext` (managed by bench)
- `google-cloud-documentai`: For PDF bank statement parsing (experimental feature)

### Key Frontend Dependencies
- `frappe-react-sdk`: Official Frappe integration for React
- `@tanstack/react-table`: Data tables
- `react-hook-form` + `zod`: Form handling and validation
- `fuse.js`: Fuzzy search for transactions
- `date-fns`/`dayjs`: Date utilities
- `lucide-react`: Icon library
- `sonner`: Toast notifications
- `jotai`: Atomic state management
- Various Radix UI primitives (via shadcn/ui)

## Important Notes

- The app requires ERPNext to be installed and running
- Bank logos are included for Indian, European, and North American banks
- The UI supports translations (strings wrapped in translation functions)
- Cross-currency payment creation is not supported in the Mint UI (must be done in ERPNext)
- PDF parsing via Google Cloud Document AI is experimental and not recommended for production use
- The app uses AGPLv3 license
