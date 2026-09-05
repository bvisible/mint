# //// Neoffice — added file (no upstream equivalent): the same VAT arithmetic re-implemented
# //// without frappe so the rounding can be checked with plain python, off a bench.
# //// (Defect worth knowing at the merge: it COPIES the functions instead of importing them,
# //// so it cannot catch a change made in vat_utils.py.)
"""
Standalone tests for VAT calculation logic (no Frappe dependencies)

Run with: python mint/apis/test_vat_calculations_standalone.py
"""

from decimal import Decimal, ROUND_HALF_UP

# //// Neoffice — imports the real functions instead of duplicating them (13577b4 "chore: the residues of
# //// the marking pass, in one lot"): the copies below were identical to vat_utils.py, docstrings aside,
# //// so they could never catch a regression made there.
# The functions under test come from the module itself: a copy would prove nothing
# (tracker #229 - the three copies were identical to vat_utils, docstrings aside).
from mint.apis.vat_utils import calculate_vat_amount, excluding_vat_price, to_decimal
# //// Neoffice — removed the to_decimal/excluding_vat_price/calculate_vat_amount copies that used to
# //// follow this comment (13577b4 "chore: the residues of the marking pass, in one lot"): replaced by
# //// the import above.


# Copy of utility functions for standalone testing


def test_to_decimal():
    """Test decimal rounding"""
    print("\n=== Testing to_decimal() ===")

    tests = [
        (10.126, 2, 10.13, "Should round up"),
        (10.124, 2, 10.12, "Should round down"),
        (10.125, 2, 10.13, "Should round half up"),
        (0, 2, 0.0, "Zero should return 0.0"),
        (None, 2, 0.0, "None should return 0.0"),
    ]

    for value, precision, expected, description in tests:
        result = to_decimal(value, precision)
        assert result == expected, f"{description}: Expected {expected}, got {result}"
        print(f"  ✓ {description}: {value} → {result}")

    print("✅ All to_decimal() tests passed")


def test_excluding_vat_price():
    """Test price excluding VAT calculation"""
    print("\n=== Testing excluding_vat_price() ===")

    tests = [
        (1200, 20, 1000.0, "1200 TTC with 20% VAT = 1000 HT"),
        (105.50, 5.5, 100.0, "105.50 TTC with 5.5% VAT = 100 HT"),
        (100, 0, 100.0, "0% VAT returns same price"),
        (0, 20, 0.0, "Zero price returns 0.0"),
        (2400, 20, 2000.0, "2400 TTC with 20% VAT = 2000 HT"),
    ]

    for price_ttc, vat_rate, expected_ht, description in tests:
        result = excluding_vat_price(price_ttc, vat_rate)
        assert abs(result - expected_ht) < 0.01, f"{description}: Expected {expected_ht}, got {result}"
        print(f"  ✓ {description}")

    print("✅ All excluding_vat_price() tests passed")


def test_calculate_vat_amount():
    """Test VAT amount calculation"""
    print("\n=== Testing calculate_vat_amount() ===")

    # Test HT mode (is_vat_excluded=True)
    print("\n  HT Mode (is_vat_excluded=True):")
    ht_tests = [
        (1000, 20, 200.0, "1000 HT + 20% VAT = 200 VAT"),
        (100, 5.5, 5.5, "100 HT + 5.5% VAT = 5.5 VAT"),
        (500, 10, 50.0, "500 HT + 10% VAT = 50 VAT"),
        (1000, 0, 0.0, "1000 HT + 0% VAT = 0 VAT"),
    ]

    for price_ht, vat_rate, expected_vat, description in ht_tests:
        result = calculate_vat_amount(price_ht, vat_rate, is_vat_excluded=True)
        assert abs(result - expected_vat) < 0.01, f"{description}: Expected {expected_vat}, got {result}"
        print(f"    ✓ {description}")

    # Test TTC mode (is_vat_excluded=False)
    print("\n  TTC Mode (is_vat_excluded=False):")
    ttc_tests = [
        (1200, 20, 200.0, "1200 TTC with 20% VAT = 200 VAT"),
        (105.50, 5.5, 5.5, "105.50 TTC with 5.5% VAT = 5.5 VAT"),
        (110, 10, 10.0, "110 TTC with 10% VAT = 10 VAT"),
    ]

    for price_ttc, vat_rate, expected_vat, description in ttc_tests:
        result = calculate_vat_amount(price_ttc, vat_rate, is_vat_excluded=False)
        assert abs(result - expected_vat) < 0.01, f"{description}: Expected {expected_vat}, got {result}"
        print(f"    ✓ {description}")

    print("✅ All calculate_vat_amount() tests passed")


def test_real_world_scenarios():
    """Test real-world scenarios"""
    print("\n=== Testing Real-World Scenarios ===")

    # Scenario 1: Restaurant bill (France)
    print("\n  Scenario 1: Restaurant Bill (France)")
    print("    - Food: 100€ HT @ 5.5% VAT")
    food_ht = 100.0
    food_vat_rate = 5.5
    food_vat = calculate_vat_amount(food_ht, food_vat_rate, is_vat_excluded=True)
    food_ttc = food_ht + food_vat
    print(f"      Food HT: {food_ht}€")
    print(f"      Food VAT: {food_vat}€")
    print(f"      Food TTC: {food_ttc}€")
    assert abs(food_ttc - 105.5) < 0.01, "Food TTC should be 105.50"

    print("    - Drinks: 50€ HT @ 20% VAT")
    drinks_ht = 50.0
    drinks_vat_rate = 20
    drinks_vat = calculate_vat_amount(drinks_ht, drinks_vat_rate, is_vat_excluded=True)
    drinks_ttc = drinks_ht + drinks_vat
    print(f"      Drinks HT: {drinks_ht}€")
    print(f"      Drinks VAT: {drinks_vat}€")
    print(f"      Drinks TTC: {drinks_ttc}€")
    assert abs(drinks_ttc - 60.0) < 0.01, "Drinks TTC should be 60.00"

    total_ttc = food_ttc + drinks_ttc
    print(f"    Total TTC: {total_ttc}€")
    assert abs(total_ttc - 165.5) < 0.01, "Total TTC should be 165.50"
    print("  ✓ Restaurant bill calculation correct")

    # Scenario 2: Invoice with 20% VAT entered as TTC
    print("\n  Scenario 2: User enters 1200€ TTC (includes 20% VAT)")
    amount_entered = 1200.0
    vat_rate = 20

    # Extract HT and VAT
    amount_ht = excluding_vat_price(amount_entered, vat_rate)
    amount_vat = calculate_vat_amount(amount_entered, vat_rate, is_vat_excluded=False)

    print(f"    Amount entered (TTC): {amount_entered}€")
    print(f"    Amount HT (extracted): {amount_ht}€")
    print(f"    VAT amount: {amount_vat}€")
    print(f"    Verification: {amount_ht} + {amount_vat} = {amount_ht + amount_vat}€")

    assert abs(amount_ht - 1000.0) < 0.01, "HT should be 1000"
    assert abs(amount_vat - 200.0) < 0.01, "VAT should be 200"
    assert abs(amount_ht + amount_vat - amount_entered) < 0.01, "HT + VAT should equal TTC"
    print("  ✓ TTC to HT extraction correct")

    # Scenario 3: Multiple lines with same VAT rate
    print("\n  Scenario 3: Multiple expense lines @ 20% VAT")
    expenses = [
        ("Office supplies", 500.0),
        ("Software license", 1000.0),
        ("Marketing", 750.0)
    ]

    total_ht = 0
    total_vat = 0

    for name, amount_ht in expenses:
        vat = calculate_vat_amount(amount_ht, 20, is_vat_excluded=True)
        ttc = amount_ht + vat
        total_ht += amount_ht
        total_vat += vat
        print(f"    {name}: {amount_ht}€ HT + {vat}€ VAT = {ttc}€ TTC")

    print(f"    Total HT: {total_ht}€")
    print(f"    Total VAT: {total_vat}€")
    print(f"    Total TTC: {total_ht + total_vat}€")

    assert abs(total_ht - 2250.0) < 0.01, "Total HT should be 2250"
    assert abs(total_vat - 450.0) < 0.01, "Total VAT should be 450"
    print("  ✓ Multiple lines calculation correct")

    print("\n✅ All real-world scenarios passed")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print(" VAT CALCULATION TESTS (Standalone)")
    print("="*70)

    try:
        test_to_decimal()
        test_excluding_vat_price()
        test_calculate_vat_amount()
        test_real_world_scenarios()

        print("\n" + "="*70)
        print(" ✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n📝 Summary:")
        print("  - Decimal rounding: ✓")
        print("  - HT ↔ TTC conversion: ✓")
        print("  - VAT calculation (HT mode): ✓")
        print("  - VAT calculation (TTC mode): ✓")
        print("  - Real-world scenarios: ✓")
        print("\n💡 Next steps:")
        print("  1. Test in actual ERPNext environment")
        print("  2. Configure Account with taxable_account field")
        print("  3. Create Item Tax Template with VAT rates")
        print("  4. Test via Mint UI with bank transactions")

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
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
