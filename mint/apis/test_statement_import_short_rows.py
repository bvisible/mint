# //// Neoffice — added file (no upstream equivalent): a bank statement whose rows are shorter than its header (#1501).
"""
A statement row shorter than the header does not fail the import.

An export drops the trailing empty cells of a row, and many statements end with a totals or footer line of a cell or two. The
import read ``row[column]`` for every mapped column and raised ``IndexError: list index out of range`` on the first column such
a row lacked: the person who uploaded the file saw that error and nothing was imported.

Run with:
    python -m pytest mint/apis/test_statement_import_short_rows.py -v
"""

from mint.apis.statement_import import get_transaction_rows

HEADER = ["Date", "Description", "Withdrawal", "Deposit", "Balance"]
MAPPING = {"Date": 0, "Description": 1, "Withdrawal": 2, "Deposit": 3, "Balance": 4}
FULL_1 = ["2026-10-01", "Coffee", "4.50", "", "995.50"]
FULL_2 = ["2026-10-02", "Salary", "", "3000", "3995.50"]


def _read(*body, mapping=MAPPING):
    return get_transaction_rows([HEADER, *body], 0, mapping)


def test_a_footer_line_of_one_cell_does_not_fail_the_import():
    rows, start, end = _read(FULL_1, FULL_2, ["Total"])
    assert [r["description"] for r in rows] == ["Coffee", "Salary"]
    assert (start, end) == (1, 2)


def test_a_row_whose_trailing_cells_were_dropped_is_still_a_transaction():
    rows, start, end = _read(FULL_1, ["2026-10-03", "Fee", "2.00"])
    assert [r["description"] for r in rows] == ["Coffee", "Fee"]
    fee = rows[1]
    assert fee["withdrawal"] == "2.00" and fee["deposit"] is None and fee["balance"] is None
    assert (start, end) == (1, 2)


def test_a_row_with_a_date_and_no_amount_is_skipped():
    rows, _, _ = _read(FULL_1, ["2026-10-04", "Memo"])
    assert [r["description"] for r in rows] == ["Coffee"]


def test_an_empty_row_is_skipped():
    rows, _, _ = _read([], FULL_1, [])
    assert [r["description"] for r in rows] == ["Coffee"]


def test_a_statement_with_no_transaction_has_no_range():
    assert _read(["Total"], []) == ([], None, None)


def test_a_header_with_no_row_below_it_has_no_range():
    assert get_transaction_rows([HEADER], 0, MAPPING) == ([], None, None)


def test_a_row_the_length_of_the_header_is_read_as_before():
    rows, start, end = _read(FULL_1, FULL_2)
    assert rows[0] == {
        "date_format": rows[0]["date_format"],
        "date": "2026-10-01",
        "withdrawal": "4.50",
        "deposit": "",
        "balance": "995.50",
        "description": "Coffee",
    }
    assert (start, end) == (0 + 1, 1 + 1)


def test_the_padding_follows_the_widest_mapped_column_and_not_the_header():
    # only the first three columns are mapped: a row of three cells is complete
    rows, _, _ = _read(["2026-10-03", "Fee", "2.00"], mapping={"Date": 0, "Description": 1, "Withdrawal": 2})
    assert [r["description"] for r in rows] == ["Fee"]


def test_no_mapped_column_is_no_transaction():
    assert _read(FULL_1, mapping={}) == ([], None, None)
