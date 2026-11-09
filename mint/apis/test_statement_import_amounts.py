# //// Neoffice — added file (no upstream equivalent): a bank statement read as it is written (#1489).
"""
Amounts, dates and balances of a statement file are read as the bank wrote them.

A decimal comma was dropped ("12,50" was read 1250.00), a Date column in first position was replaced by a later
"Value Date" column, the date cells of an .xls (plain numbers for xlrd) made every row be skipped, and an overdrawn account
could not be imported because its closing balance is below zero. None of these needs a site: the parsing functions are
pure, and ``import_statement`` is run against a stand-in for frappe.

Run with:
    python -m pytest mint/apis/test_statement_import_amounts.py -v
or, on a bench:
    bench --site prodclone.local run-tests --app mint --module mint.apis.test_statement_import_amounts
"""

import json
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from mint.apis import statement_import
from mint.apis.statement_import import (
    excel_serial_to_datetime,
    get_closing_balance,
    get_column_mapping,
    get_final_transactions,
    get_float_amount,
    get_transaction_rows,
)

LOG_JSON = (
    Path(__file__).resolve().parents[1]
    / "mint"
    / "doctype"
    / "mint_bank_statement_import_log"
    / "mint_bank_statement_import_log.json"
)

HEADER = ["Date", "Description", "Withdrawal", "Deposit", "Balance"]
MAPPING = {"Date": 0, "Description": 1, "Withdrawal": 2, "Deposit": 3, "Balance": 4}
# 1 October 2026 as xlrd hands a date cell over: the days since 1899-12-30
SERIAL = float((date(2026, 10, 1) - date(1899, 12, 30)).days)


class TestAmountsAreReadWithTheirDecimalMark(unittest.TestCase):
    def test_a_decimal_comma_is_a_decimal_mark(self):
        for text, expected in [
            ("12,50", 12.5),
            ("1850,50", 1850.5),
            ("1.850,50", 1850.5),
            ("1 850,50", 1850.5),
            ("-12,50", -12.5),
            ("12,5", 12.5),
            ("CHF 12,50", 12.5),
            ("12,50 CR", 12.5),
        ]:
            with self.subTest(text=text):
                self.assertEqual(get_float_amount(text), expected)

    def test_a_comma_that_separates_thousands_is_still_dropped(self):
        for text, expected in [
            ("1,250", 1250.0),
            ("1,850.50", 1850.5),
            ("1,234,567", 1234567.0),
            ("-1,250.00", -1250.0),
            ("1'850.50", 1850.5),
        ]:
            with self.subTest(text=text):
                self.assertEqual(get_float_amount(text), expected)

    def test_what_was_read_before_is_read_the_same(self):
        for text, expected in [
            ("12.50", 12.5),
            ("12.50 CR", 12.5),
            ("DR 12.50", 12.5),
            ("-12.50", -12.5),
            (1250, 1250.0),
            (12.5, 12.5),
        ]:
            with self.subTest(text=text):
                self.assertEqual(get_float_amount(text), expected)

    def test_what_is_not_an_amount_is_none(self):
        for text in ("", None, "n/a", ",", "-"):
            with self.subTest(text=text):
                self.assertIsNone(get_float_amount(text))


class TestADateColumnInFirstPositionIsKept(unittest.TestCase):
    def test_a_value_date_column_does_not_replace_the_date_column(self):
        columns, mapping = get_column_mapping(["Date", "Description", "Value Date", "Amount"])

        self.assertEqual(mapping, {"Date": 0, "Description": 1, "Amount": 3})
        self.assertEqual([c["maps_to"] for c in columns], ["Date", "Description", "Do not import", "Amount"])

    def test_the_first_column_of_a_kind_wins_wherever_it_stands(self):
        _, mapping = get_column_mapping(["Description", "Date", "Value Date", "Amount"])

        self.assertEqual(mapping["Date"], 1)


class TestAnXlsDateIsADate(unittest.TestCase):
    def test_a_serial_number_is_the_day_it_counts_from(self):
        self.assertEqual(excel_serial_to_datetime(SERIAL), datetime(2026, 10, 1))
        self.assertEqual(excel_serial_to_datetime(46296), datetime(2026, 10, 1))

    def test_what_is_not_a_date_serial_is_left_as_it_came(self):
        today = datetime(2026, 10, 1)
        for value in ("2026-10-01", today, None, True, 4.5, 995.5, 20261001, 20261001.0, ""):
            with self.subTest(value=value):
                self.assertEqual(excel_serial_to_datetime(value), value)

    def test_the_rows_of_an_xls_are_transactions(self):
        rows, start, end = get_transaction_rows(
            [HEADER, [SERIAL, "Coffee", 4.5, "", 995.5], [SERIAL + 1, "Salary", "", 3000.0, 3995.5]],
            0,
            MAPPING,
        )

        self.assertEqual([r["description"] for r in rows], ["Coffee", "Salary"])
        self.assertEqual([r["date"] for r in rows], [datetime(2026, 10, 1), datetime(2026, 10, 2)])
        self.assertEqual((start, end), (1, 2))

        date_format = rows[0]["date_format"]
        self.assertEqual(
            get_closing_balance(rows, date_format), (date(2026, 10, 1), date(2026, 10, 2), 3995.5)
        )
        final = get_final_transactions(rows, date_format, "separate_columns_for_withdrawal_and_deposit")
        self.assertEqual([t["date"] for t in final], ["2026-10-01", "2026-10-02"])
        self.assertEqual([(t["withdrawal"], t["deposit"]) for t in final], [(4.5, None), (None, 3000.0)])

    def test_a_number_that_is_not_a_date_still_skips_the_row(self):
        rows, start, end = get_transaction_rows([HEADER, [20261001.0, "Coffee", "4.50", "", ""]], 0, MAPPING)

        self.assertEqual((rows, start, end), ([], None, None))


class TestAClosingBalanceBelowZeroIsKept(unittest.TestCase):
    def test_the_balance_of_the_last_day_is_read_with_its_sign(self):
        rows = [
            {"date": datetime(2026, 10, 1), "balance": "-250.00"},
            {"date": datetime(2026, 10, 2), "balance": "-1,250.00"},
        ]

        self.assertEqual(get_closing_balance(rows, "%Y-%m-%d")[2], -1250.0)

    def import_with(self, closing_balance):
        """import_statement of a statement that ends on `closing_balance`; returns the call that stores the balance."""
        data = {
            "final_transactions": [],
            "statement_start_date": "2026-10-01",
            "statement_end_date": "2026-10-02",
            "closing_balance": closing_balance,
        }
        with (
            mock.patch.object(statement_import, "frappe") as frappe,
            mock.patch.object(statement_import, "get_statement_details", return_value=data),
            mock.patch.object(statement_import, "set_closing_balance_as_per_statement") as store,
            mock.patch.dict("sys.modules", {"mint.apis.rules": mock.MagicMock()}),
        ):
            frappe.get_value.side_effect = [("Company", "Account", 1, 0), "CHF"]
            statement_import.import_statement("/files/statement.csv", "BA-1")
        return store

    def test_an_overdrawn_account_has_its_balance_stored(self):
        store = self.import_with(-250.0)

        store.assert_called_once()
        self.assertEqual(store.call_args.args[2], -250.0)

    def test_a_statement_that_ends_on_zero_has_its_balance_stored(self):
        self.assertEqual(self.import_with(0.0).call_count, 1)

    def test_a_balance_above_zero_is_stored_as_before(self):
        self.assertEqual(self.import_with(1500.0).call_args.args[2], 1500.0)

    def test_a_statement_with_no_balance_stores_none(self):
        self.assertEqual(self.import_with(None).call_count, 0)

    def test_the_log_field_accepts_a_negative_balance(self):
        fields = {f["fieldname"]: f for f in json.loads(LOG_JSON.read_text())["fields"]}

        self.assertNotIn("non_negative", fields["closing_balance"])
        # the count of transactions is still never negative
        self.assertEqual(fields["number_of_transactions"].get("non_negative"), 1)
