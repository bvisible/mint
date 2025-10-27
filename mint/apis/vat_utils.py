import frappe
from typing import Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP

def to_decimal(value: float, precision: int = 2) -> float:
    """
    Round a number to the specified precision using ROUND_HALF_UP

    Args:
        value: The value to round
        precision: Number of decimal places (default: 2)

    Returns:
        The rounded value as float
    """
    if value is None or value == 0:
        return 0.0

    # Use Decimal for precise rounding
    decimal_value = Decimal(str(value))
    # Create the quantize pattern (e.g., '0.01' for 2 decimal places)
    quantize_pattern = Decimal('0.1') ** precision
    rounded = decimal_value.quantize(quantize_pattern, rounding=ROUND_HALF_UP)

    return float(rounded)


def excluding_vat_price(price_with_tax: float, vat_rate: float, precision: int = 2) -> float:
    """
    Calculate the price excluding VAT from a price including VAT and VAT rate

    Args:
        price_with_tax: Price including VAT (TTC)
        vat_rate: VAT rate as percentage (e.g., 20 for 20%)
        precision: Number of decimal places for rounding

    Returns:
        Price excluding VAT (HT)
    """
    # Input validation
    if not price_with_tax or price_with_tax == 0:
        return 0.0
    if not vat_rate or vat_rate == 0:
        return price_with_tax

    # Safe calculation
    divisor = 1 + (vat_rate / 100)
    if divisor <= 0:
        return price_with_tax

    return to_decimal(price_with_tax / divisor, precision)


def calculate_vat_amount(price: float, vat_rate: float, is_vat_excluded: bool = True, precision: int = 2) -> float:
    """
    Calculate the VAT amount

    Args:
        price: The price (HT or TTC depending on is_vat_excluded)
        vat_rate: VAT rate as percentage
        is_vat_excluded: If True, price is HT. If False, price is TTC
        precision: Number of decimal places for rounding

    Returns:
        VAT amount
    """
    # Input validation
    if not price or price == 0:
        return 0.0
    if not vat_rate or vat_rate == 0:
        return 0.0

    if is_vat_excluded:
        # If the price is excluding VAT (HT), calculate VAT directly
        return to_decimal(price * vat_rate / 100, precision)
    else:
        # If the price is including VAT (TTC), calculate the price excluding VAT first
        price_without_vat = excluding_vat_price(price, vat_rate, precision)
        return to_decimal(price - price_without_vat, precision)


def get_company_vat_method(company: str) -> Optional[str]:
    """
    Retrieve the VAT accounting method for a company

    Args:
        company: Company name

    Returns:
        VAT accounting method or None if not set
    """
    if not company:
        return None

    return frappe.get_cached_value("Company", company, "vat_accounting_method")


def get_account_tax_info(account_name: str) -> Optional[Dict[str, Any]]:
    """
    Get tax information for an account

    Args:
        account_name: Account name

    Returns:
        Dictionary with tax_rate and tax_account, or None if no tax configured
    """
    if not account_name:
        return None

    # Get the taxable_account field from Account
    taxable_account = frappe.get_cached_value("Account", account_name, "taxable_account")

    if not taxable_account:
        return None

    # Get the Item Tax Template
    try:
        tax_template = frappe.get_doc("Item Tax Template", taxable_account)
    except Exception:
        # Template doesn't exist or other error
        return None

    if not tax_template or not tax_template.taxes or len(tax_template.taxes) == 0:
        return None

    # Find the first tax line with a tax rate > 0
    for tax in tax_template.taxes:
        if tax.tax_rate and tax.tax_rate > 0:
            return {
                "tax_rate": tax.tax_rate,
                "tax_account": tax.tax_type
            }

    return None


def calculate_journal_entry_with_vat(
    entries: list,
    is_withdrawal: bool,
    is_vat_excluded: bool = False,
    disable_vat_calculation: bool = False,
    company: str = None
) -> list:
    """
    Calculate journal entry lines with VAT

    Args:
        entries: List of entry dictionaries with 'account' and 'amount'
        is_withdrawal: Whether this is a withdrawal (True) or deposit (False)
        is_vat_excluded: If True, amounts are HT. If False, amounts are TTC
        disable_vat_calculation: If True, skip VAT calculation
        company: Company name (to check VAT method)

    Returns:
        List of all entry dictionaries including VAT lines
    """
    result_entries = []

    # Check if company uses flat-rate taxation
    if company:
        vat_method = get_company_vat_method(company)
        if vat_method and "Flat" in vat_method:
            disable_vat_calculation = True

    for entry in entries:
        account = entry.get("account")
        amount = entry.get("amount", 0)

        if not account or amount == 0:
            result_entries.append(entry)
            continue

        # Check if VAT calculation is disabled
        if disable_vat_calculation:
            result_entries.append(entry)
            continue

        # Get tax info for this account
        tax_info = get_account_tax_info(account)

        if not tax_info:
            # No tax configured for this account
            result_entries.append(entry)
            continue

        # Calculate base amount and tax amount
        if is_vat_excluded:
            # Mode HT: amount entered is HT, calculate VAT directly
            base_amount = amount
            tax_amount = calculate_vat_amount(base_amount, tax_info["tax_rate"], True)
        else:
            # Mode TTC: amount entered is TTC, extract HT and calculate VAT
            base_amount = excluding_vat_price(amount, tax_info["tax_rate"])
            tax_amount = amount - base_amount

        # Add the base entry (with HT amount)
        base_entry = entry.copy()
        base_entry["amount"] = base_amount
        base_entry["_is_base_for_vat"] = True
        result_entries.append(base_entry)

        # Add the VAT entry
        vat_entry = {
            "account": tax_info["tax_account"],
            "amount": tax_amount,
            "party_type": None,
            "party": None,
            "cost_center": entry.get("cost_center"),
            "user_remark": f"TVA - {entry.get('user_remark', account)}",
            "_is_vat_line": True,
            "_source_account": account
        }
        result_entries.append(vat_entry)

    return result_entries
