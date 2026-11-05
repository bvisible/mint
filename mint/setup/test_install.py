# //// Neoffice — added file (no upstream equivalent).
# ////
# //// A FRESH INSTALL OF MINT ON ERPNEXT v16 MUST NOT ADD A FIELD ERPNEXT ALREADY SHIPS.
# ////
# //// v16 moved Mint's bank module into ERPNext: Bank Transaction.is_rule_evaluated,
# //// Bank Account.is_credit_card and Bank Transaction Payments.reconciliation_type are standard
# //// fields there. Upstream Mint skips ALL its custom fields when reconciliation_type exists
# //// (561c65c); we also add matched_rule, which v16 does not have under that name, so the skip is
# //// per field. On v15 none of the four is a standard field: everything must still be created.

import unittest
from unittest.mock import MagicMock, patch

import frappe

from mint.setup import install

ALL_FIELDS = {
	"Bank Transaction Payments": {"reconciliation_type"},
	"Bank Account": {"is_credit_card"},
	"Bank Transaction": {"is_rule_evaluated", "matched_rule"},
}


def _install(native):
	"""Run after_install with `native` = {(doctype, fieldname)} standard fields; return what it asked for."""
	db = MagicMock()
	db.exists.side_effect = lambda doctype, filters=None, *a, **kw: (
		doctype == "DocField" and (filters["parent"], filters["fieldname"]) in native
	)
	with patch.object(frappe, "db", db), patch.object(install, "create_custom_fields") as create:
		install.after_install()
	(requested,) = create.call_args.args
	return {doctype: {f["fieldname"] for f in fields} for doctype, fields in requested.items()}


class TestAfterInstallSkipsFieldsErpnextShips(unittest.TestCase):
	def test_v15_creates_every_field(self):
		self.assertEqual(_install(native=set()), ALL_FIELDS)

	def test_v16_keeps_only_the_field_it_lacks(self):
		native = {
			("Bank Transaction Payments", "reconciliation_type"),
			("Bank Account", "is_credit_card"),
			("Bank Transaction", "is_rule_evaluated"),
		}
		self.assertEqual(_install(native), {"Bank Transaction": {"matched_rule"}})

	def test_a_single_native_field_removes_only_itself(self):
		native = {("Bank Transaction Payments", "reconciliation_type")}
		expected = {k: v for k, v in ALL_FIELDS.items() if k != "Bank Transaction Payments"}
		self.assertEqual(_install(native), expected)
