# //// Neoffice — added file (no upstream equivalent).
# ////
# //// "TRANSFER MATCH DAYS = 0" MEANS THE SAME DAY, NOT "NOT SET".
# ////
# //// search_for_transfer_transaction read the setting with `if not days: days = 4`, so a user who set
# //// 0 to match the mirror of a transfer on the SAME day only was silently given four days either side
# //// (ERPNext fixed the same line in v16, frappe/erpnext#58766). The field defaults to 4, so the
# //// fallback only ever applies when the setting cannot be read at all.

import unittest
from unittest.mock import MagicMock, patch

import frappe

from mint.apis.bank_reconciliation import search_for_transfer_transaction

DAY = "2026-03-10"


def _window(setting):
	"""The (from, to) dates the mirror transaction is searched in, for a transfer made on DAY."""
	db = MagicMock()
	db.get_value.return_value = ("Some Company", 100, 0, DAY, "A Bank Account")
	db.get_single_value.return_value = setting
	db.get_list.return_value = []
	with patch.object(frappe, "db", db):
		search_for_transfer_transaction("ACC-BTN-0001")
	return tuple(db.get_list.call_args.kwargs["filters"]["date"][1])


class TestTransferMatchDays(unittest.TestCase):
	def test_zero_searches_the_same_day_only(self):
		self.assertEqual(_window(0), (DAY, DAY))

	def test_the_setting_is_the_number_of_days_either_side(self):
		self.assertEqual(_window(2), ("2026-03-08", "2026-03-12"))

	def test_an_unreadable_setting_falls_back_to_four_days(self):
		self.assertEqual(_window(None), ("2026-03-06", "2026-03-14"))
