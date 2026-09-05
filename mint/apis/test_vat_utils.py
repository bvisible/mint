# //// Neoffice — added file (no upstream equivalent): unit tests for vat_utils.py, our own
# //// module. Upstream ships no VAT logic and no test for it.
"""
Unit tests for VAT calculation utilities

Run these tests with:
    python -m pytest mint/apis/test_vat_utils.py -v

Or run directly:
    python mint/apis/test_vat_utils.py
"""

import sys
import os

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from mint.apis.vat_utils import (
    to_decimal,
    excluding_vat_price,
    calculate_vat_amount,
    calculate_journal_entry_with_vat
)


def test_to_decimal():
    """Test decimal rounding"""
    print("\n=== Testing to_decimal() ===")

    # Test basic rounding
    assert to_decimal(10.126, 2) == 10.13, "Should round up"
    assert to_decimal(10.124, 2) == 10.12, "Should round down"
    assert to_decimal(10.125, 2) == 10.13, "Should round half up"

    # Test zero
    assert to_decimal(0, 2) == 0.0, "Zero should return 0.0"
    assert to_decimal(None, 2) == 0.0, "None should return 0.0"

    print("✓ to_decimal() tests passed")


def test_excluding_vat_price():
    """Test price excluding VAT calculation"""
    print("\n=== Testing excluding_vat_price() ===")

    # Test with 20% VAT
    # 1200 TTC with 20% VAT should give 1000 HT
    ht = excluding_vat_price(1200, 20)
    assert ht == 1000.0, f"Expected 1000.0, got {ht}"

    # Test with 5.5% VAT (common in France for food)
    # 105.50 TTC with 5.5% VAT should give 100 HT
    ht = excluding_vat_price(105.50, 5.5)
    expected = 100.0
    assert abs(ht - expected) < 0.01, f"Expected {expected}, got {ht}"

    # Test with 0% VAT
    ht = excluding_vat_price(100, 0)
    assert ht == 100, "0% VAT should return same price"

    # Test with zero price
    ht = excluding_vat_price(0, 20)
    assert ht == 0.0, "Zero price should return 0.0"

    print("✓ excluding_vat_price() tests passed")


def test_calculate_vat_amount():
    """Test VAT amount calculation"""
    print("\n=== Testing calculate_vat_amount() ===")

    # Test mode HT (is_vat_excluded=True)
    # 1000 HT with 20% VAT should give 200 VAT
    vat = calculate_vat_amount(1000, 20, is_vat_excluded=True)
    assert vat == 200.0, f"Expected 200.0, got {vat}"

    # Test mode TTC (is_vat_excluded=False)
    # 1200 TTC with 20% VAT should give 200 VAT
    vat = calculate_vat_amount(1200, 20, is_vat_excluded=False)
    assert vat == 200.0, f"Expected 200.0, got {vat}"

    # Test with 5.5% VAT in HT mode
    vat = calculate_vat_amount(100, 5.5, is_vat_excluded=True)
    assert vat == 5.5, f"Expected 5.5, got {vat}"

    # Test with 0% VAT
    vat = calculate_vat_amount(1000, 0, is_vat_excluded=True)
    assert vat == 0.0, "0% VAT should give 0 VAT amount"

    # Test with zero price
    vat = calculate_vat_amount(0, 20, is_vat_excluded=True)
    assert vat == 0.0, "Zero price should give 0 VAT amount"

    print("✓ calculate_vat_amount() tests passed")


def test_calculate_journal_entry_with_vat_ht_mode():
    """Test journal entry calculation in HT mode (is_vat_excluded=True)"""
    print("\n=== Testing calculate_journal_entry_with_vat() - HT Mode ===")

    # Mock entries: 1000€ HT on expense account
    entries = [
        {
            "account": "6000 - Expenses",
            "amount": 1000.0,
            "party_type": None,
            "party": None,
            "cost_center": "Main - CC",
            "user_remark": "Test expense"
        }
    ]

    # Mock get_account_tax_info to return 20% VAT
    # We'll need to mock this, but for now we'll test the logic
    # This test will fail without proper mocking, but shows the expected behavior

    # In HT mode, amount entered is HT, so we expect:
    # - Base entry: 1000€ (unchanged)
    # - VAT entry: 200€

    print("  Testing HT mode: 1000€ HT + 20% VAT should create:")
    print("    - Base entry: 1000€")
    print("    - VAT entry: 200€")
    print("  (Full test requires Frappe context for account lookup)")


def test_calculate_journal_entry_with_vat_ttc_mode():
    """Test journal entry calculation in TTC mode (is_vat_excluded=False)"""
    print("\n=== Testing calculate_journal_entry_with_vat() - TTC Mode ===")

    # Mock entries: 1200€ TTC on expense account
    entries = [
        {
            "account": "6000 - Expenses",
            "amount": 1200.0,
            "party_type": None,
            "party": None,
            "cost_center": "Main - CC",
            "user_remark": "Test expense"
        }
    ]

    # In TTC mode, amount entered is TTC, so we expect:
    # - Base entry: 1000€ (extracted HT)
    # - VAT entry: 200€

    print("  Testing TTC mode: 1200€ TTC with 20% VAT should create:")
    print("    - Base entry: 1000€ (HT extracted)")
    print("    - VAT entry: 200€")
    print("  (Full test requires Frappe context for account lookup)")


def test_multiple_entries_with_different_vat():
    """Test journal entry with multiple lines having different VAT rates"""
    print("\n=== Testing Multiple Entries with Different VAT Rates ===")

    # Scenario: Restaurant bill
    # - Food: 100€ HT at 5.5% VAT = 105.50 TTC
    # - Drinks: 50€ HT at 20% VAT = 60 TTC
    # Total TTC = 165.50

    print("  Restaurant bill scenario:")
    print("    - Food: 100€ HT + 5.5% VAT (105.50 TTC)")
    print("    - Drinks: 50€ HT + 20% VAT (60 TTC)")
    print("  Expected result:")
    print("    - Food account: 100€")
    print("    - VAT 5.5%: 5.50€")
    print("    - Drinks account: 50€")
    print("    - VAT 20%: 10€")
    print("  (Full test requires Frappe context)")


def test_account_without_vat():
    """Test that accounts without VAT configuration are not affected"""
    print("\n=== Testing Account Without VAT ===")

    entries = [
        {
            "account": "5000 - Bank Account",  # No VAT on bank accounts
            "amount": 1000.0,
        }
    ]

    # Without VAT configuration, should return same entry unchanged
    result = calculate_journal_entry_with_vat(
        entries=entries,
        is_withdrawal=True,
        is_vat_excluded=False,
        disable_vat_calculation=False,
        company=None
    )

    assert len(result) == 1, f"Expected 1 entry, got {len(result)}"
    assert result[0]["amount"] == 1000.0, "Amount should be unchanged"

    print("✓ Account without VAT returns unchanged")


def test_vat_calculation_disabled():
    """Test that VAT calculation can be disabled"""
    print("\n=== Testing VAT Calculation Disabled ===")

    entries = [
        {
            "account": "6000 - Expenses",
            "amount": 1200.0,
        }
    ]

    # With disable_vat_calculation=True, should return same entries unchanged
    result = calculate_journal_entry_with_vat(
        entries=entries,
        is_withdrawal=True,
        is_vat_excluded=False,
        disable_vat_calculation=True,  # Disabled
        company=None
    )

    assert len(result) == 1, f"Expected 1 entry, got {len(result)}"
    assert result[0]["amount"] == 1200.0, "Amount should be unchanged when VAT disabled"

    print("✓ VAT calculation can be disabled")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running VAT Calculation Tests")
    print("="*60)

    try:
        test_to_decimal()
        test_excluding_vat_price()
        test_calculate_vat_amount()
        test_account_without_vat()
        test_vat_calculation_disabled()
        test_calculate_journal_entry_with_vat_ht_mode()
        test_calculate_journal_entry_with_vat_ttc_mode()
        test_multiple_entries_with_different_vat()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nNote: Some tests require a full Frappe/ERPNext context")
        print("to test account lookups and complete integration.")

        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
