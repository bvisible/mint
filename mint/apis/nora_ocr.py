"""
Nora OCR Integration for Mint
Replaces Google Document AI for bank statement parsing

This module provides a bridge between Mint's bank statement import
functionality and Nora's generic OCR extraction API.

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

    This function calls Nora's generic extract_data() API with a specialized
    prompt for bank statement parsing. It replaces the Google Document AI
    integration for a free, self-hosted alternative.

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
        # Call Nora's generic extraction API
        result = frappe.call(
            "nora.api.ocr.extract_data",
            file_url=file_url,
            prompt=BANK_STATEMENT_PROMPT,
            output_schema=BANK_STATEMENT_SCHEMA,
            validate_schema=True,
            max_retries=2
        )

        frappe.logger().info(f"[Mint Nora OCR] Extraction result: success={result.get('success')}, "
                            f"processing_time={result.get('processing_time')}s, "
                            f"model={result.get('model_used')}")

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
def test_bank_statement_extraction(file_url: str = None) -> dict:
    """
    Test function to extract bank transactions from a PDF.

    This is a whitelisted function for testing the OCR integration
    from the browser console or via API.

    Args:
        file_url: Frappe file URL to test

    Returns:
        dict: {
            "success": bool,
            "transactions": list,
            "count": int,
            "error": str (if failed)
        }
    """
    if not file_url:
        return {
            "success": False,
            "error": "Please provide a file_url parameter"
        }

    try:
        transactions = extract_bank_transactions(file_url)
        return {
            "success": True,
            "transactions": transactions,
            "count": len(transactions)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "transactions": []
        }
