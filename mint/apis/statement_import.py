# //// Neoffice — upstream's file (merged with v1.5.4). Ours, each marked in place: the short-row padding of
# //// get_transaction_rows (#1501; upstream still reads the missing cell), and (#1489) the decimal comma of
# //// get_float_amount, the column at index 0 of get_column_mapping, the date serial numbers of an .xls in
# //// get_transaction_rows, and the closing balance below zero in import_statement.
import frappe
import re
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)
from frappe import _
from frappe.utils import getdate

from datetime import datetime, timedelta  # //// Neoffice — timedelta: excel_serial_to_datetime (#1489)

from mint.apis.bank_account import set_closing_balance_as_per_statement

@frappe.whitelist(methods=["GET"])
def get_statement_details(file_url: str, bank_account: str):
    """
    Given a file path, try to get bank statement details.

    From the data, we want to "guess" the following:
    1. Row index of the header row
    2. Column mapping to standard variables?
    3. Row indices of all rows after the header row that are relevant - hence look like transactions
    4. Opening and Closing dates of the statement and balance
    """

    # //// Neoffice — the statement is for a bank account the user must be able to read (get_data checks the file).
    frappe.has_permission("Bank Account", ptype="read", doc=bank_account, throw=True)

    data = get_data(file_url)

    file_name = file_url.split("/")[-1]

    header_index = get_header_row_index(data)

    header_row = data[header_index]

    columns, column_mapping = get_column_mapping(header_row)

    transaction_rows, transaction_starting_index, transaction_ending_index = get_transaction_rows(data, header_index, column_mapping)

    date_format, amount_format = get_file_properties(transaction_rows)

    char_map = {
        "%d": "DD",
        "%m": "MM",
        "%Y": "YYYY",
        "%y": "YY",
        "%b": "MMM",
        "%B": "MMMM",
    }

    formatted_date_format = date_format
    for char, replacement in char_map.items():
        formatted_date_format = formatted_date_format.replace(char, replacement)

    statement_start_date, statement_end_date, closing_balance = get_closing_balance(transaction_rows, date_format)

    conflicting_transactions = check_for_conflicts(bank_account, statement_start_date, statement_end_date)

    final_transactions = get_final_transactions(transaction_rows, date_format, amount_format)

    account = frappe.get_cached_value("Bank Account", bank_account, "account")
    account_currency = frappe.get_cached_value("Account", account, "account_currency")

    return {
        "file_name": file_name,
        "file_path": file_url,
        "data": data,
        "header_index": header_index,
        "header_row": header_row,
        "columns": columns,
        "column_mapping": column_mapping,
        "transaction_starting_index": transaction_starting_index,
        "transaction_ending_index": transaction_ending_index,
        "transaction_rows": transaction_rows,
        "date_format": formatted_date_format,
        "amount_format": amount_format,
        "statement_start_date": statement_start_date,
        "statement_end_date": statement_end_date,
        "closing_balance": closing_balance,
        "conflicting_transactions": conflicting_transactions,
        "final_transactions": final_transactions,
        "currency": account_currency,
    }

@frappe.whitelist(methods=["POST"])
def import_statement(file_url: str, bank_account: str):
    """
    Given a file path and bank account, try to import the statement
    """

    # //// Neoffice — upstream translated the message of each throw below but not its title, so the dialog
    # //// header stayed English next to a French body. The titles go through _() as well.
    if not frappe.has_permission("Bank Transaction", "write"):
        frappe.throw(_("You do not have permission to import bank transactions"), title=_("Permission Denied"))
    
    if not frappe.has_permission("Bank Transaction", "create"):
        # //// Neoffice — see the block marker above: the throw title now goes through _() too
        # //// (54d0d0a "fix(i18n): pass bare UI strings and throw titles through the translate helpers").
        frappe.throw(_("You do not have permission to import bank transactions"), title=_("Permission Denied"))
    
    if not frappe.has_permission("Bank Transaction", "submit"):
        # //// Neoffice — see the block marker above: the throw title now goes through _() too
        # //// (54d0d0a "fix(i18n): pass bare UI strings and throw titles through the translate helpers").
        frappe.throw(_("You do not have permission to import and submit bank transactions"), title=_("Permission Denied"))

    

    company, account, is_company_account, disabled = frappe.get_value("Bank Account", bank_account, ["company", "account", "is_company_account", "disabled"])
    # //// Neoffice — same as above: the throw titles were left untranslated.
    if not is_company_account:
        frappe.throw(_("The bank account is not a company account. Please select a company account"), title=_("Invalid Bank Account"))
    
    if disabled:
        # //// Neoffice — see the markers above: the throw title now goes through _() too
        # //// (54d0d0a "fix(i18n): pass bare UI strings and throw titles through the translate helpers").
        frappe.throw(_("The bank account is disabled. Please enable it"), title=_("Disabled Bank Account"))
    
    currency = frappe.get_value("Account", account, "account_currency")
    # Create the bank transactions, submit them and then store the closing balance if any

    data = get_statement_details(file_url, bank_account)

    progress = 0

    for transaction in data.get("final_transactions"):
        bank_tx = frappe.get_doc({
            "doctype": "Bank Transaction",
            "date": transaction.get("date"),
            "status": "Unreconciled",
            "bank_account": bank_account,
            "withdrawal": transaction.get("withdrawal"),
            "deposit": transaction.get("deposit"),
            "description": transaction.get("description"),
            "reference_number": transaction.get("reference"),
            "transaction_type": transaction.get("transaction_type"),
            "currency": currency,
            "company": company,
        })
        bank_tx.insert()
        bank_tx.submit()
        progress += 1

        frappe.publish_realtime("mint-statement-import-progress", {
            "progress": round((progress / len(data.get("final_transactions"))) * 100),
        }, user=frappe.session.user)
    
    frappe.publish_realtime("mint-statement-import-progress", {
        "progress": 100,
        "total": len(data.get("final_transactions")),
    }, user=frappe.session.user)
    
    log = frappe.new_doc("Mint Bank Statement Import Log")
    log.bank_account = bank_account
    log.file = file_url
    log.number_of_transactions = len(data.get("final_transactions"))
    log.start_date = data.get("statement_start_date")
    log.end_date = data.get("statement_end_date")
    log.closing_balance = data.get("closing_balance")
    log.insert(ignore_permissions=True)

    # //// Neoffice — an overdrawn account has a closing balance below zero, and a statement can end on exactly zero: upstream
    # //// kept only a balance above zero (and the log field refused a negative one), so such a statement could not be
    # //// imported at all (#1489). Only a statement that names no balance leaves it unset.
    if data.get("closing_balance") is not None and data.get("statement_end_date"):
        set_closing_balance_as_per_statement(bank_account, frappe.utils.getdate(data.get("statement_end_date")), data.get("closing_balance"))
    
    from mint.apis.rules import run_rule_evaluation
    run_rule_evaluation()

    return {
        "success": True,
        "message": _("Bank statement imported successfully."),
        "start_date": data.get("statement_start_date"),
        "end_date": data.get("statement_end_date"),
    }

# //// Neoffice — added (#1490, get_data): a statement file that cannot be read says so in one clear sentence. Upstream let
# //// whatever the reader raised reach the screen: on an empty file the message quoted a folder of the server, with the
# //// e-mail address of the user that owns it. The original error goes to the Error Log (staff only), with its traceback;
# //// the person who uploaded the file reads nothing of the server. Drop only if upstream wraps the readers itself.
def throw_unreadable_file(file_path: str):
    frappe.log_error("Bank statement file could not be read", f"File: {file_path}\n\n{frappe.get_traceback()}")
    frappe.throw(_("The file could not be read"), title=_("Unreadable File"))
# //// END Neoffice ////


def get_data(file_path: str):

    # //// Neoffice — see throw_unreadable_file (#1490): a File record that does not exist, a file that cannot be opened and a
    # //// workbook the reader refuses all end in the same clear message. A refusal of permission is not hidden.
    try:
        file_doc = frappe.get_doc("File", {"file_url": file_path})
    except frappe.DoesNotExistError:
        throw_unreadable_file(file_path)
    # //// Neoffice — the file is named by the request and read from disk: without this, any logged-in account
    # //// (a portal customer included) could have a private spreadsheet of someone else parsed and returned.
    file_doc.check_permission("read")

    parts = file_doc.get_extension()
    extension = parts[1]
    # //// Neoffice — see throw_unreadable_file (#1490)
    try:
        content = file_doc.get_content()
    except frappe.PermissionError:
        raise
    except Exception:
        throw_unreadable_file(file_path)

    if extension.lower() not in (".csv", ".xlsx", ".xls"):
        # //// Neoffice — the throw title was left untranslated (see import_statement).
        frappe.throw(_("Import template should be of type .csv, .xlsx or .xls"), title=_("Invalid File Type"))

    # //// Neoffice — see throw_unreadable_file (#1490)
    try:
        if extension.lower() == ".csv":
            data = read_csv_content(content)
        elif extension.lower() == ".xlsx":
            data = read_xlsx_file_from_attached_file(fcontent=content)
        elif extension.lower() == ".xls":
            data = read_xls_file_from_attached_file(content)
    except frappe.PermissionError:
        raise
    except Exception:
        throw_unreadable_file(file_path)

    # //// Neoffice — added (#1490): a file with no cell at all used to go on to get_statement_details and fail there on
    # //// « list index out of range ». It is said plainly, before anything else reads it.
    if not any(cell not in (None, "") for row in (data or []) for cell in row):
        frappe.throw(_("The file is empty"), title=_("Empty File"))

    return data

def get_header_row_index(data: list[list[str]]):
    """
    Given the data, try to get the row index of the header row.
    """

    row_index = 0
    max_valid_columns = 0

    # Loop over rows and find the first row that has the most number of "valid" column headers
    # Valid columns is based on keywords present in each cell

    for idx, row in enumerate(data):
        valid_columns = 0
        for cell in row:
            if not cell:
                continue

            # If cell is a string, then we need to check if it contains any of the keywords
            if not isinstance(cell, str):
                continue

            if any(keyword in cell.lower() for keyword in ["date", "amount", "description", "reference", "transaction", "type", "cr", "dr", "deposit", "withdrawal", "balance"]):
                valid_columns += 1
        if valid_columns > max_valid_columns:
            max_valid_columns = valid_columns
            row_index = idx

    return row_index

def get_column_mapping(header_row: list[str]):
    """
    Given the header row, try to map each column index to a standard variable, or set it to "Do not import"
    """
    standard_variables = {
        "Date": ["date", "transaction date"], 
        "Withdrawal": ["withdrawal", "debit"],
        "Deposit": ["deposit", "credit"],
        "Amount": ["amount"], 
        "Description": ["description", "particulars", "remarks", "narration", "detail", "reference"], 
        "Reference": ["reference", "ref", "tran id", "transaction id", "cheque", "check", "id", "chq"], 
        "Transaction Type": ["transaction type", "cr/dr", "dr/cr", "debit/credit", "credit/debit"], 
        "Balance": ["balance"],
    }

    # A standard variable can be represented by multiple names

    column_mapping = {}

    # Loop over all columns and check if they contain any of the standard variable names
    # If not, we do not import it
    # If they do, we map the column index to the standard variable

    columns = []

    for idx, cell in enumerate(header_row):

       

        if not cell:
            continue

        if not isinstance(cell, str):
            continue

        column = {
            "index": idx,
            "header_text": cell,
            "variable": cell.strip().lower().replace(" ", "_").replace("?", "").replace(".", ""),
            "maps_to": "Do not import",
        }

        for standard_variable, names in standard_variables.items():
            if any(name in cell.lower().replace(".", "") for name in names):

                # //// Neoffice — "is the variable mapped yet", not "is its column index truthy": the column at index 0
                # //// (a Date in first position) is falsy, so a second "Value Date" column replaced it (#1489).
                if standard_variable not in column_mapping:
                    column["maps_to"] = standard_variable

                    column_mapping[standard_variable] = idx

                    break
        
        columns.append(column)
    

    return columns, column_mapping


# //// Neoffice — added (#1489, get_transaction_rows): the date of an .xls cell. xlrd gives a date cell as a plain float, the
# //// number of days since 1899-12-30 (a workbook on the 1900 date system, which is every one an export makes). Only a number
# //// that falls between 1954 and 2099 is taken for a date: the amounts and the 8-digit dates written as numbers stay what
# //// they were. Anything else (a string, a datetime from an .xlsx, nothing) is returned as it came.
def excel_serial_to_datetime(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if not 20000 <= value < 73051:
        return value
    return datetime(1899, 12, 30) + timedelta(days=value)
# //// END Neoffice ////


def get_transaction_rows(data: list[list[str]], header_index: int, column_mapping: dict[str, int]):
    """
    Given the data, header index and column mapping, try to get the transaction rows

    For each row after the header row, check if the data makes sense - date column should have a date, 
    amount column should be a number after removing any special charatcers, spaces and "CR/DR" text.
    Balance column should be a number after removing any special charatcers, spaces and "CR/DR" text.
    """

    transaction_rows = []

    transaction_starting_index = None
    transaction_ending_index = None

    valid_rows = data[header_index + 1:]

    column_map_keys = column_mapping.keys()

    # //// Neoffice — a row shorter than the header (a totals line, a footer, the trailing empty cells an export drops) raised
    # //// IndexError on the first column it lacked, and the whole import failed with « list index out of range » (#1501).
    # //// A missing cell reads as empty; a row with no date, or no amount, is skipped below exactly as before.
    width = max(column_mapping.values(), default=-1) + 1
    # //// END Neoffice ////

    for row_index, row in enumerate(valid_rows):

        # //// Neoffice — see above (#1501).
        if len(row) < width:
            row = [*row, *([None] * (width - len(row)))]
        # //// END Neoffice ////

        date = row[column_mapping["Date"]] if "Date" in column_map_keys else None
        # //// Neoffice — an .xls hands a date cell over as an Excel serial number (a float), which the check below took for
        # //// "not a date": every row was skipped and the file showed 0 transactions (#1489). An .xlsx gives a datetime.
        date = excel_serial_to_datetime(date)
        # //// END Neoffice ////
        amount = row[column_mapping["Amount"]] if "Amount" in column_map_keys else None
        withdrawal = row[column_mapping["Withdrawal"]] if "Withdrawal" in column_map_keys else None
        deposit = row[column_mapping["Deposit"]] if "Deposit" in column_map_keys else None
        balance = row[column_mapping["Balance"]] if "Balance" in column_map_keys else None

        if not date:
            continue

        if isinstance(date, datetime):
            date = date.strftime("%Y-%m-%d")

        if not isinstance(date, str):
            continue

        if not amount and not withdrawal and not deposit:
            continue

        # Check if date column is a valid date
        row_date_format = frappe.utils.guess_date_format(date)

        if not row_date_format:
            continue

        # Check if either the amount, withdrawal or deposit column is a valid number
        amount = get_float_amount(amount)
        withdrawal = get_float_amount(withdrawal)
        deposit = get_float_amount(deposit)
        balance = get_float_amount(balance)
            
        if not amount and not withdrawal and not deposit:
            continue

        if transaction_starting_index is None:
            transaction_starting_index = row_index

        transaction_ending_index = row_index

        transaction_row = {
            "date_format": row_date_format,
        }

        if "Date" in column_map_keys:
            # //// Neoffice — the date as converted above (an .xls serial number is a datetime here), see #1489.
            transaction_row["date"] = excel_serial_to_datetime(row[column_mapping["Date"]])
        if "Amount" in column_map_keys:
            transaction_row["amount"] = row[column_mapping["Amount"]]
        if "Withdrawal" in column_map_keys:
            transaction_row["withdrawal"] = row[column_mapping["Withdrawal"]]
        if "Deposit" in column_map_keys:
            transaction_row["deposit"] = row[column_mapping["Deposit"]]
        if "Balance" in column_map_keys:
            transaction_row["balance"] = row[column_mapping["Balance"]]
        if "Reference" in column_map_keys:
            transaction_row["reference"] = row[column_mapping["Reference"]]
        if "Description" in column_map_keys:
            transaction_row["description"] = row[column_mapping["Description"]]
        if "Transaction Type" in column_map_keys:
            transaction_row["transaction_type"] = row[column_mapping["Transaction Type"]]
        
        transaction_rows.append(transaction_row)
    
    base_index = header_index + 1

    if transaction_starting_index is not None:
        transaction_starting_index += base_index
    
    if transaction_ending_index is not None:
        transaction_ending_index += base_index

    return transaction_rows, transaction_starting_index, transaction_ending_index

def get_float_amount(amount):

    if not amount:
        return None

    if isinstance(amount, str):
        # //// Neoffice — the comma is read for what it is (#1489): upstream dropped every comma, so a decimal comma vanished
        # //// ("12,50" was 1250.0, "1850,50" 185050.0). A comma is the decimal mark when it is the only one and 1 or 2 digits
        # //// follow it ("12,50", "1.850,50"); anything else is a thousands separator, as before ("1,250", "1,850.50").
        amount = amount.lower().replace(" ", "").replace("cr", "").replace("dr", "")
        amount = re.sub(r'[^\d.,-]', '', amount)
        if re.fullmatch(r"[^,]*,\d{1,2}", amount):
            amount = amount.replace(".", "").replace(",", ".")
        else:
            amount = amount.replace(",", "")
        # //// END Neoffice ////
        # Remove any other alphabets and currency symbols - do not remove the minus or decimal sign
        amount = re.sub(r'[^\d.-]', '', amount)
        try:
            amount = float(amount)
        except ValueError:
            return None
    elif isinstance(amount, int):
        amount = float(amount)
    else:
        try:
            amount = float(amount)
        except ValueError:
            return None

    return amount

def get_file_properties(transactions: list):
    """
    From the transaction rows, try to figure out the following:
    1. Most common date format
    2. Amount format - does it contain "CR/Dr" text or is it in a separate column (maybe transaction type?). Amount could also be positive and negative.
    """

    date_format_frequency = {
        "%d/%m/%Y": 0,
    }

    amount_format_frequency = {
        "separate_columns_for_withdrawal_and_deposit": 0,
        "dr_cr_in_amount": 0,
        "positive_negative_in_amount": 0,
        "cr_dr_in_transaction_type": 0,
        "deposit_withdrawal_in_transaction_type": 0,
    }

    for transaction in transactions:
        date_format = transaction.get("date_format")

        if date_format:
            date_format_frequency[date_format] = date_format_frequency.get(date_format, 0) + 1
        
        # Check if there's an amount column
        # If there's a separate column for withdrawal and deposit, we can skip this
        if transaction.get("withdrawal", None) or transaction.get("deposit", None):
            amount_format_frequency["separate_columns_for_withdrawal_and_deposit"] += 1
            continue

        amount = transaction.get("amount", None)

        if not amount:
            continue

        if isinstance(amount, str) and ("cr" in amount.lower() or "dr" in amount.lower()):
            amount_format_frequency["dr_cr_in_amount"] += 1
        
        # Check if there's a transaction type column containing "cr"/"dr"
        if transaction.get("transaction_type", None):
            if "cr" in transaction.get("transaction_type", "").lower() or "dr" in transaction.get("transaction_type", "").lower():
                amount_format_frequency["cr_dr_in_transaction_type"] += 1
            if "deposit" in transaction.get("transaction_type", "").lower() or "withdrawal" in transaction.get("transaction_type", "").lower():
                amount_format_frequency["deposit_withdrawal_in_transaction_type"] += 1
        
        # Else assume that the amount is expressed as positive/negative value
        else:
            amount_format_frequency["positive_negative_in_amount"] += 1
    
    most_common_date_format = max(date_format_frequency, key=date_format_frequency.get)
    most_common_amount_format = max(amount_format_frequency, key=amount_format_frequency.get)

    return most_common_date_format, most_common_amount_format


def get_closing_balance(transactions: list, date_format: str):
    """
    Given the transactions and date format, try to get the statement start date, end date and closing balance
    """

    statement_start_date = None
    statement_end_date = None
    closing_balance = None

    for transaction in transactions:
        date = transaction.get("date")
        if not date:
            continue

        if isinstance(date, datetime):
            tx_date = date
        else:
            tx_date = datetime.strptime(date, date_format)

        if statement_start_date is None or tx_date < statement_start_date:
            statement_start_date = tx_date

        if statement_end_date is None or tx_date >= statement_end_date:
            statement_end_date = tx_date

            closing_balance = transaction.get("balance")

    return getdate(statement_start_date), getdate(statement_end_date), get_float_amount(closing_balance)


def check_for_conflicts(bank_account: str, start_date: str, end_date: str):
    """
    Given a bank account, start date and end date, check if there are any conflicts with existing bank transactions
    """

    conflicts = frappe.get_all("Bank Transaction", filters={
        "bank_account": bank_account,
        "date": ["between", [start_date, end_date]],
        "docstatus": 1,
    }, fields=["name", "date", "withdrawal", "deposit", "description", "reference_number", "currency"],
    order_by="date")

    return conflicts


def get_final_transactions(transactions: list, date_format: str, amount_format: str):
    """
    Given the transactions, date format and amount format, try to get the final transactions
    """

    final_transactions = []

    def parse_amount(transaction_row: dict):
        """
        Given a transaction row, try to parse the amount - returns tuple of (withdrawal, deposit)
        """

        if amount_format == "separate_columns_for_withdrawal_and_deposit":
            return get_float_amount(transaction_row.get("withdrawal")), get_float_amount(transaction_row.get("deposit"))
        
        if amount_format == "dr_cr_in_amount":
            amount = transaction_row.get("amount")
            float_amount = get_float_amount(amount)
            if "cr" in amount.lower():
                return 0, float_amount
            else:
                return float_amount, 0
        
        if amount_format == "positive_negative_in_amount":
            amount = get_float_amount(transaction_row.get("amount", "0"))
            if amount > 0:
                return 0, abs(amount)
            else:
                return abs(amount), 0
        
        if amount_format == "cr_dr_in_transaction_type":
            transaction_type = transaction_row.get("transaction_type")
            amount = get_float_amount(transaction_row.get("amount", "0"))
            if "cr" in transaction_type.lower():
                return 0, abs(amount)
            else:
                return abs(amount), 0
        
        if amount_format == "deposit_withdrawal_in_transaction_type":
            transaction_type = transaction_row.get("transaction_type")
            amount = get_float_amount(transaction_row.get("amount", "0"))
            if "deposit" in transaction_type.lower():
                return 0, abs(amount)
            else:
                return abs(amount), 0
        
        return 0, 0
    
    for transaction in transactions:
        date = transaction.get("date")

        if isinstance(date, datetime):
            date = date.strftime("%Y-%m-%d")
        else:
            date = datetime.strptime(date, date_format).strftime("%Y-%m-%d")

        withdrawal, deposit = parse_amount(transaction)
        final_transactions.append({
            "date": date,
            "withdrawal": withdrawal,
            "deposit": deposit,
            "description": transaction.get("description"),
            "reference": transaction.get("reference"),
            "transaction_type": transaction.get("transaction_type"),
        })
    
    return final_transactions