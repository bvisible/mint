"""
Nora OCR Integration for Mint
Replaces Google Document AI for bank statement parsing

This module provides a bridge between Mint's bank statement import
functionality and Nora's unified OCR API (ocr_process).

All bank statement extractions create Document Scan records for
complete traceability.

Usage:
    from mint.apis.nora_ocr import extract_bank_transactions
    transactions = extract_bank_transactions("/files/bank_statement.pdf")
"""
import frappe
from frappe import _


# Bank statement extraction prompt optimized for structured output
BANK_STATEMENT_PROMPT = """
Extract ALL transactions from this bank statement.

For EACH transaction visible in the document, extract:
- date: Transaction date in YYYY-MM-DD format (convert from any format)
- amount: The transaction amount as a positive number string (no currency symbol, no thousands separator)
- type: Either "Deposit" for credits/incoming money OR "Withdrawal" for debits/outgoing money
- description: The transaction description/narration/reference text

RULES:
- Extract ALL transactions from ALL pages
- Convert ALL dates to YYYY-MM-DD format (e.g., "15/03/2024" becomes "2024-03-15")
- Amount must be a positive number as a STRING (e.g., "1234.56" not 1234.56)
- Remove currency symbols and thousands separators from amounts
- Type is "Deposit" for money coming IN (credits, deposits, incoming transfers)
- Type is "Withdrawal" for money going OUT (debits, withdrawals, payments, charges)
- Description should capture the transaction text/narration/reference
- If a field is unclear or missing, use empty string ""

Return a JSON array of transaction objects.
"""

# JSON schema for bank statement transactions
BANK_STATEMENT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["date", "amount", "type", "description"],
        "properties": {
            "date": {
                "type": "string",
                "description": "Transaction date in YYYY-MM-DD format"
            },
            "amount": {
                "type": "string",
                "description": "Positive amount as string without currency symbol"
            },
            "type": {
                "type": "string",
                "enum": ["Deposit", "Withdrawal"],
                "description": "Transaction type"
            },
            "description": {
                "type": "string",
                "description": "Transaction description/narration"
            }
        }
    }
}


def extract_bank_transactions(file_url: str) -> list:
    """
    Extract bank transactions from a PDF statement using Nora OCR.

    This function calls Nora's unified ocr_process() API with a specialized
    prompt for bank statement parsing. It replaces the Google Document AI
    integration for a free, self-hosted alternative.

    All extractions create a Document Scan record for complete traceability.

    Args:
        file_url (str): Frappe file URL to the bank statement PDF
            (e.g., "/files/statement.pdf" or "/private/files/statement.pdf")

    Returns:
        list: List of transaction dicts with keys:
            - date: str (YYYY-MM-DD format)
            - amount: str (positive number as string)
            - type: str ("Deposit" or "Withdrawal")
            - description: str

    Raises:
        frappe.ValidationError: If extraction fails or returns invalid data

    Example:
        transactions = extract_bank_transactions("/files/bank_statement.pdf")
        for tx in transactions:
            print(f"{tx['date']}: {tx['type']} {tx['amount']} - {tx['description']}")
    """
    frappe.logger().info(f"[Mint Nora OCR] Starting bank statement extraction: {file_url}")

    try:
        # Call Nora's unified OCR API with Document Scan creation
        # Use page splitting for multi-page bank statements
        result = frappe.call(
            "nora.api.ocr.ocr_process",
            file_url=file_url,
            prompt=BANK_STATEMENT_PROMPT,
            output_schema=BANK_STATEMENT_SCHEMA,
            create_document_scan=True,  # Create Document Scan for traceability
            add_to_rag=False,
            validate_hallucination=False,  # Bank statements don't need hallucination check
            max_retries=1,
            use_page_splitting=True,  # Enable page-by-page processing for multi-page PDFs
            pages_per_batch=1  # Process 1 page at a time (fastest: ~19s/page vs 61s/2 pages)
        )

        frappe.logger().info(f"[Mint Nora OCR] Extraction result: success={result.get('success')}, "
                            f"processing_time={result.get('processing_time')}s, "
                            f"model={result.get('model_used')}, "
                            f"retry_count={result.get('retry_count')}, "
                            f"json_repair_applied={result.get('json_repair_applied')}, "
                            f"document_scan={result.get('document_scan_name')}")

        if not result.get("success"):
            errors = result.get("validation_errors", [])
            raw = result.get("raw_response", "")
            error_msg = result.get("error", "Unknown error")

            frappe.log_error(
                "Nora OCR Bank Statement Extraction Failed",
                f"Error: {error_msg}\n\n"
                f"Validation errors: {errors}\n\n"
                f"Raw response (first 1000 chars): {raw[:1000] if raw else 'N/A'}"
            )

            frappe.throw(
                _("Failed to extract transactions from bank statement. "
                  "Please check the file format or try again. Error: {0}").format(error_msg)
            )

        data = result.get("data", [])

        # Handle both direct list and dict with transactions/items key
        if isinstance(data, dict):
            # Extract transactions from dict structure (from paged OCR merge)
            data = data.get("transactions") or data.get("items") or []

        # Validate we got a list
        if not isinstance(data, list):
            frappe.log_error(
                "Nora OCR Unexpected Data Type",
                f"Expected list, got {type(data).__name__}: {data}"
            )
            frappe.throw(_("Invalid extraction result: expected a list of transactions"))

        # Validate and normalize each transaction
        normalized_transactions = []
        for i, tx in enumerate(data):
            if not isinstance(tx, dict):
                frappe.logger().warning(f"[Mint Nora OCR] Skipping non-dict item at index {i}: {tx}")
                continue

            # Normalize transaction
            normalized = {
                "date": _normalize_date(tx.get("date", "")),
                "amount": _normalize_amount(tx.get("amount", "0")),
                "type": _normalize_type(tx.get("type", "")),
                "description": str(tx.get("description", "") or "").strip()
            }

            # Skip invalid transactions
            if not normalized["amount"] or normalized["amount"] == "0":
                frappe.logger().warning(f"[Mint Nora OCR] Skipping transaction with zero/missing amount: {tx}")
                continue

            normalized_transactions.append(normalized)

        frappe.logger().info(f"[Mint Nora OCR] Extracted {len(normalized_transactions)} valid transactions")

        return normalized_transactions

    except frappe.ValidationError:
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        frappe.log_error("Nora OCR Integration Error", f"{str(e)}\n\n{frappe.get_traceback()}")
        frappe.throw(
            _("Bank statement OCR processing failed: {0}").format(str(e))
        )


def _normalize_date(date_str: str) -> str:
    """
    Normalize date string to YYYY-MM-DD format.

    Args:
        date_str: Date string in various formats

    Returns:
        str: Date in YYYY-MM-DD format or original string if parsing fails
    """
    if not date_str:
        return ""

    date_str = str(date_str).strip()

    # Already in ISO format
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str

    # Try common formats
    import re
    from datetime import datetime

    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    match = re.match(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$', date_str)
    if match:
        day, month, year = map(int, match.groups())
        # Handle 2-digit year
        if year < 100:
            year += 2000

        # Swap day/month if day > 12 (likely DD/MM format)
        if day > 12 and month <= 12:
            pass  # Already correct
        elif month > 12 and day <= 12:
            day, month = month, day  # Swap

        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            pass

    return date_str


def _normalize_amount(amount_str: str) -> str:
    """
    Normalize amount to a positive number string.

    Args:
        amount_str: Amount string possibly with currency symbols

    Returns:
        str: Clean positive number string
    """
    if not amount_str:
        return "0"

    amount_str = str(amount_str).strip()

    # Remove currency symbols and whitespace
    import re
    # Remove common currency symbols and words
    clean = re.sub(r'[CHF€$£¥₹\s]', '', amount_str, flags=re.IGNORECASE)

    # Remove thousands separators (but keep decimal point)
    # Handle both comma and dot as decimal separators
    if ',' in clean and '.' in clean:
        # Both present: assume last one is decimal separator
        if clean.rfind(',') > clean.rfind('.'):
            # Comma is decimal separator (European format: 1.234,56)
            clean = clean.replace('.', '').replace(',', '.')
        else:
            # Dot is decimal separator (US format: 1,234.56)
            clean = clean.replace(',', '')
    elif ',' in clean:
        # Only comma: check if it's decimal or thousands
        parts = clean.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Likely decimal separator
            clean = clean.replace(',', '.')
        else:
            # Likely thousands separator
            clean = clean.replace(',', '')

    # Remove any remaining non-numeric characters except dot and minus
    clean = re.sub(r'[^\d.\-]', '', clean)

    # Remove minus sign (we want absolute value)
    clean = clean.lstrip('-')

    # Ensure valid number format
    if not clean or clean == '.':
        return "0"

    try:
        # Parse and re-format to ensure valid number
        value = float(clean)
        return str(abs(value))
    except ValueError:
        return "0"


def _normalize_type(type_str: str) -> str:
    """
    Normalize transaction type to "Deposit" or "Withdrawal".

    Args:
        type_str: Transaction type string

    Returns:
        str: "Deposit" or "Withdrawal"
    """
    if not type_str:
        return "Deposit"  # Default

    type_lower = str(type_str).strip().lower()

    # Check for withdrawal indicators
    withdrawal_keywords = ['withdrawal', 'debit', 'dr', 'out', 'payment', 'charge', 'expense']
    if any(kw in type_lower for kw in withdrawal_keywords):
        return "Withdrawal"

    # Check for deposit indicators
    deposit_keywords = ['deposit', 'credit', 'cr', 'in', 'income', 'receipt', 'transfer in']
    if any(kw in type_lower for kw in deposit_keywords):
        return "Deposit"

    # If exact match after title case
    if type_str.strip() in ["Deposit", "Withdrawal"]:
        return type_str.strip()

    # Default to Deposit
    return "Deposit"


@frappe.whitelist()
def create_document_scan_for_bank_statement(file_url: str, force_create: bool = False) -> dict:
    """
    Create a Document Scan for bank statement extraction.
    OCR runs in background via frappe.enqueue.
    Returns immediately with document_scan_name.

    Args:
        file_url: Frappe file URL to the bank statement PDF
        force_create: If True, create with suffix if duplicate exists

    Returns:
        dict: {
            "success": bool,
            "document_scan_name": str,
            "message": str,
            "duplicate": bool (if a duplicate exists),
            "existing_name": str (name of existing document if duplicate)
        }
    """
    import json
    from datetime import date

    if not file_url:
        return {
            "success": False,
            "message": _("Please provide a file_url parameter")
        }

    frappe.logger().info(f"[Mint Nora OCR] Creating Document Scan for bank statement: {file_url}")

    try:
        # Generate base document name
        today = date.today().isoformat()
        file_name = file_url.split("/")[-1].replace(".pdf", "").replace(".PDF", "")
        base_name = f"{today}_BankStatement_{file_name}"
        generated_name = base_name

        # Check if document with this name already exists
        if frappe.db.exists("Document Scan", base_name):
            if not force_create:
                # Return duplicate info so frontend can ask user
                return {
                    "success": False,
                    "duplicate": True,
                    "existing_name": base_name,
                    "message": _("A Document Scan with this name already exists")
                }
            else:
                # Find next available suffix
                suffix = 2
                while frappe.db.exists("Document Scan", f"{base_name}-{suffix}"):
                    suffix += 1
                generated_name = f"{base_name}-{suffix}"

        # Create Document Scan with bank statement prompt via neoffice_theme API
        result = frappe.call(
            "neoffice_theme.neoffice_theme.doctype.document_scan.document_scan.create_document_scan_from_json",
            json_data=json.dumps({
                "generated_document_name": generated_name,
                "source_file": file_url,
                "document_type": "Other",  # Bank Statement
                "custom_prompt": BANK_STATEMENT_PROMPT,
                "custom_schema": BANK_STATEMENT_SCHEMA
            })
        )

        if result.get("success"):
            frappe.logger().info(f"[Mint Nora OCR] Document Scan created: {result.get('name')}")
            return {
                "success": True,
                "document_scan_name": result.get("name"),
                "message": _("Bank statement processing started")
            }
        else:
            return {
                "success": False,
                "message": result.get("message", _("Failed to create Document Scan"))
            }

    except Exception as e:
        frappe.log_error("Bank Statement Document Scan Creation Failed", frappe.get_traceback())
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def check_document_scan_status(document_scan_name: str) -> dict:
    """
    Check the OCR status of a Document Scan.

    Args:
        document_scan_name: Name of the Document Scan

    Returns:
        dict: {
            "status": "Pending" | "Processing" | "Completed" | "Failed",
            "ocr_status": str,
            "transactions": list (if completed),
            "error": str (if failed)
        }
    """
    if not document_scan_name:
        return {"status": "Error", "error": _("Missing document_scan_name")}

    try:
        doc = frappe.get_doc("Document Scan", document_scan_name)

        if doc.ocr_status == "Completed":
            # Extract transactions from ocr_results
            transactions = extract_transactions_from_document_scan(doc)
            return {
                "status": "Completed",
                "ocr_status": doc.ocr_status,
                "transactions": transactions,
                "count": len(transactions)
            }

        elif doc.ocr_status == "Failed":
            return {
                "status": "Failed",
                "ocr_status": doc.ocr_status,
                "error": doc.ocr_error or _("OCR processing failed")
            }

        else:
            # Still processing
            return {
                "status": "Processing",
                "ocr_status": doc.ocr_status
            }

    except frappe.DoesNotExistError:
        return {"status": "Error", "error": _("Document Scan not found")}
    except Exception as e:
        return {"status": "Error", "error": str(e)}


def extract_transactions_from_document_scan(doc) -> list:
    """
    Extract and normalize transactions from a completed Document Scan.

    Args:
        doc: Document Scan document with ocr_results

    Returns:
        list: Normalized transactions
    """
    import json

    if not doc.ocr_results:
        return []

    try:
        data = json.loads(doc.ocr_results)
    except json.JSONDecodeError:
        frappe.logger().warning(f"[Mint Nora OCR] Invalid JSON in ocr_results for {doc.name}")
        return []

    # Handle both array and dict formats
    if isinstance(data, dict):
        # If it's a dict, it might have a 'transactions' key or be an invoice format
        data = data.get("transactions", [])

    if not isinstance(data, list):
        return []

    # Normalize transactions
    normalized_transactions = []
    for tx in data:
        if not isinstance(tx, dict):
            continue

        normalized = {
            "date": _normalize_date(tx.get("date", "")),
            "amount": _normalize_amount(tx.get("amount", "0")),
            "type": _normalize_type(tx.get("type", "")),
            "description": str(tx.get("description", "") or "").strip()
        }

        if normalized["amount"] and normalized["amount"] != "0":
            normalized_transactions.append(normalized)

    return normalized_transactions


@frappe.whitelist()
def start_ocr_processing(docname: str, force_create: bool = False) -> dict:
    """
    Start async OCR processing via Document Scan for a Mint Bank Statement Import.
    Returns immediately with status.

    Args:
        docname: Name of the Mint Bank Statement Import document
        force_create: If True, create new scan even if duplicate exists (with suffix)

    Returns:
        dict with status, document_scan_name, and message
        If duplicate exists and force_create=False, returns duplicate info
    """
    doc = frappe.get_doc("Mint Bank Statement Import", docname)

    if not doc.file:
        frappe.throw(_("Please upload a file"))

    # Create Document Scan for bank statement (OCR runs in background)
    result = create_document_scan_for_bank_statement(doc.file, force_create=force_create)

    # Handle duplicate case
    if result.get("duplicate"):
        return {
            "status": "Duplicate",
            "existing_name": result.get("existing_name"),
            "message": result.get("message")
        }

    if result.get("success"):
        doc.document_scan_name = result.get("document_scan_name")
        doc.ocr_status = "Processing"
        doc.save()
        return {
            "status": "Processing",
            "document_scan_name": result.get("document_scan_name"),
            "message": _("OCR processing started")
        }
    else:
        doc.ocr_status = "Failed"
        doc.error = result.get("message")
        doc.save()
        frappe.throw(result.get("message"))


@frappe.whitelist()
def check_ocr_processing_status(docname: str) -> dict:
    """
    Check OCR processing status and populate transactions if completed.
    Called by frontend polling.

    Args:
        docname: Name of the Mint Bank Statement Import document

    Returns:
        dict with status, count (if completed), or error (if failed)
    """
    doc = frappe.get_doc("Mint Bank Statement Import", docname)

    if not doc.document_scan_name:
        return {"status": "Not Started"}

    result = check_document_scan_status(doc.document_scan_name)

    if result.get("status") == "Completed":
        # Populate transactions table
        transactions = result.get("transactions", [])
        doc._populate_transactions(transactions)
        doc.ocr_status = "Completed"
        doc.status = "Completed"
        doc.save()
        return {
            "status": "Completed",
            "count": len(transactions),
            "message": _("{0} transactions extracted").format(len(transactions))
        }

    elif result.get("status") == "Failed":
        doc.ocr_status = "Failed"
        doc.error = result.get("error")
        doc.status = "Error"
        doc.save()
        return {
            "status": "Failed",
            "error": result.get("error")
        }

    else:
        # Still processing
        return {"status": "Processing"}


@frappe.whitelist()
def test_bank_statement_extraction(file_url: str = None) -> dict:
    """
    Test function to extract bank transactions from a PDF.

    This is a whitelisted function for testing the OCR integration
    from the browser console or via API. Returns detailed timing and
    retry information for debugging.

    Args:
        file_url: Frappe file URL to test

    Returns:
        dict: {
            "success": bool,
            "transactions": list,
            "count": int,
            "processing_time": float,
            "retry_count": int,
            "json_repair_applied": bool,
            "document_scan_name": str,
            "error": str (if failed)
        }
    """
    import time

    if not file_url:
        return {
            "success": False,
            "error": "Please provide a file_url parameter"
        }

    start_time = time.time()

    try:
        # Call ocr_process directly to get full result with tracking
        # Use page splitting for multi-page documents (15+ pages)
        result = frappe.call(
            "nora.api.ocr.ocr_process",
            file_url=file_url,
            prompt=BANK_STATEMENT_PROMPT,
            output_schema=BANK_STATEMENT_SCHEMA,
            create_document_scan=True,
            add_to_rag=False,
            validate_hallucination=False,
            max_retries=2,  # More retries for testing
            use_page_splitting=True,  # Enable page-by-page processing for multi-page PDFs
            pages_per_batch=1  # Process 1 page at a time (fastest: ~19s/page vs 61s/2 pages)
        )

        total_time = time.time() - start_time

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "transactions": [],
                "processing_time": round(total_time, 2),
                "retry_count": result.get("retry_count", 0),
                "json_repair_applied": result.get("json_repair_applied", False),
                "document_scan_name": result.get("document_scan_name")
            }

        # Normalize transactions
        # Handle both direct list and dict with transactions/items key
        data = result.get("data", [])
        if isinstance(data, dict):
            # Extract transactions from dict structure
            data = data.get("transactions") or data.get("items") or []
        normalized_transactions = []
        for tx in data:
            if not isinstance(tx, dict):
                continue
            normalized = {
                "date": _normalize_date(tx.get("date", "")),
                "amount": _normalize_amount(tx.get("amount", "0")),
                "type": _normalize_type(tx.get("type", "")),
                "description": str(tx.get("description", "") or "").strip()
            }
            if normalized["amount"] and normalized["amount"] != "0":
                normalized_transactions.append(normalized)

        return {
            "success": True,
            "transactions": normalized_transactions,
            "count": len(normalized_transactions),
            "processing_time": round(total_time, 2),
            "retry_count": result.get("retry_count", 0),
            "json_repair_applied": result.get("json_repair_applied", False),
            "document_scan_name": result.get("document_scan_name"),
            "model_used": result.get("model_used")
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "transactions": [],
            "processing_time": round(time.time() - start_time, 2)
        }
