# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT BECAME OF EACH LINE OF AN IMPORT, READ FROM THE BANK LINE IT CREATED.
# ////
# //// Played on real invoices of the site, through the import itself (the lines are made the way the morning statement
# //// makes them). What a person does afterwards in the bank reconciliation is played with the same functions the
# //// screen calls: the decider's entry and the link of an entry to a bank line.

import frappe
from frappe.tests.roles import as_role
from frappe.utils import flt

from mint.apis import payment_gap, statement_follow_up as follow_up
from mint.apis.test_payment_gap_import import GapImportCase
from mint.mint.doctype.mint_bank_statement_import import mint_bank_statement_import as importer


class TestStatementFollowUp(GapImportCase):
	def _reconcile_by_hand(self, statement, idx=0, bank_line=None):  # role-check: ok what the reconciliation books runs as the system here
		"""What a person does afterwards: the entry of the gap, linked to the bank line of the import line."""
		line = statement.transactions[idx]
		self._settings(payment_gap_automatic=1)
		verdict = payment_gap.judge("Sales Invoice", self.sales, line.amount, line.date, None)
		entry = payment_gap.book(
			verdict, "Sales Invoice", self.sales, self.ledger, line.date, line.unique_reference, "by hand"
		)
		importer._link_payment_entry_to_bt(
			frappe.get_doc("Bank Transaction", bank_line or line.bank_transaction), entry, reconciliation_type="Voucher Created"
		)
		return entry

	@property
	def ledger(self):
		return frappe.db.get_value("Bank Account", self.bank_account, "account")

	def _overview(self, statement):
		return follow_up.get_import_overview(statement.name)

	# -- the states ------------------------------------------------------------------------------------------------

	def test_a_line_the_import_passed_says_so_and_names_its_entry(self):  # role-check: ok the import is a job of the system
		self._settings(payment_gap_automatic=1)
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		overview = self._overview(statement)
		line = overview["lines"][0]
		self.assertEqual(line["state"], "passed_alone")
		self.assertEqual([voucher["name"] for voucher in line["vouchers"]], [statement.transactions[0].payment_entry])
		self.assertEqual(overview["counts"]["passed_alone"], 1)
		self.assertEqual(overview["progress"], {"total": 1, "waiting": 0, "done": 1})

	def test_a_gap_left_to_a_person_waits_with_its_verdict(self):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		line = self._overview(statement)["lines"][0]
		self.assertEqual((line["state"], line["difference_kind"]), ("to_decide", "rounding"))
		self.assertEqual(self._overview(statement)["progress"], {"total": 1, "waiting": 1, "done": 0})

	def test_a_line_that_recognised_no_invoice_waits_to_be_matched(self):
		line = self._line("Sales Invoice", self.sales, 12.34)
		line["invoice_matches"], line["party_match"] = "", ""
		statement = self._import(line)
		self.assertEqual(self._overview(statement)["lines"][0]["state"], "to_match")

	def test_what_a_person_reconciles_afterwards_shows_in_the_import_without_anything_copied(self):  # role-check: ok see _reconcile_by_hand
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		self.assertEqual(self._overview(statement)["lines"][0]["state"], "to_decide")
		entry = self._reconcile_by_hand(statement)
		line = self._overview(statement)["lines"][0]
		self.assertEqual(line["state"], "handled")
		self.assertEqual([(v["doctype"], v["name"]) for v in line["vouchers"]], [("Payment Entry", entry)])
		self.assertTrue(line["vouchers"][0]["by"])
		self.assertEqual(self._overview(statement)["progress"]["waiting"], 0)

	def test_an_undone_reconciliation_brings_the_line_back_to_waiting(self):  # role-check: ok see _reconcile_by_hand
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		self._reconcile_by_hand(statement)
		self.assertEqual(self._overview(statement)["lines"][0]["state"], "handled")
		frappe.db.set_value("Bank Transaction", statement.transactions[0].bank_transaction, "status", "Unreconciled")
		self.assertEqual(self._overview(statement)["lines"][0]["state"], "to_decide")

	def test_leaving_a_gap_open_is_recorded_with_who_and_when(self):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		bank_line = statement.transactions[0].bank_transaction
		self.assertTrue(follow_up.note_decision(bank_line, "left_open"))
		line = self._overview(statement)["lines"][0]
		self.assertEqual((line["state"], line["decision"], line["decided_by"]), ("left_open", "left_open", "Administrator"))
		self.assertTrue(line["decided_on"])
		self.assertEqual(self._overview(statement)["progress"], {"total": 1, "waiting": 0, "done": 1})

	def test_a_decision_is_one_of_the_known_ones_and_a_foreign_bank_line_records_nothing(self):
		with self.assertRaises(frappe.ValidationError):
			follow_up.note_decision("whatever", "maybe")
		self.assertFalse(follow_up.note_decision("a-bank-line-no-import-made", "left_open"))

	def test_a_line_the_bank_already_had_creates_nothing_and_is_not_counted(self):
		owed = self._owed("Sales Invoice", self.sales)
		line = self._line("Sales Invoice", self.sales, owed - 0.03)
		self._import(dict(line))
		second = self._import(dict(line))
		overview = self._overview(second)
		self.assertEqual(overview["lines"][0]["state"], "duplicate")
		self.assertEqual(overview["progress"], {"total": 0, "waiting": 0, "done": 0})

	def test_an_import_made_before_the_link_existed_is_followed_by_the_duplicate_key(self):  # role-check: ok see _reconcile_by_hand
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		# an older import: its line does not carry the bank line it created
		frappe.db.set_value(
			"Mint Bank Statement Import Transactions", statement.transactions[0].name, "bank_transaction", None
		)
		statement.reload()
		found = self._overview(statement)["lines"][0]
		self.assertEqual(found["state"], "to_decide")
		self.assertTrue(found["bank_transaction"])
		self._reconcile_by_hand(statement, bank_line=found["bank_transaction"])
		self.assertEqual(self._overview(statement)["lines"][0]["state"], "handled")
		listed = next(item for item in follow_up.list_imports(self.bank_account) if item["name"] == statement.name)
		self.assertEqual(listed["counts"]["handled"], 1)

	def test_a_draft_has_imported_nothing_yet(self):
		draft = frappe.get_doc(
			{
				"doctype": "Mint Bank Statement Import",
				"bank_account": self.bank_account,
				"file_type": "XML",
				"currency": "CHF",
				"transactions": [self._line("Sales Invoice", self.sales, 10)],
			}
		).insert()
		overview = self._overview(draft)
		self.assertEqual(overview["lines"][0]["state"], "not_imported")
		self.assertEqual(overview["progress"], {"total": 0, "waiting": 0, "done": 0})

	# -- the list ---------------------------------------------------------------------------------------------------

	def test_the_list_counts_as_the_overview_does(self):
		self._settings(payment_gap_automatic=1)
		sales_owed = self._owed("Sales Invoice", self.sales)
		purchase_owed = self._owed("Purchase Invoice", self.purchase)
		statement = self._import(
			self._line("Sales Invoice", self.sales, sales_owed - 0.02),
			self._line("Purchase Invoice", self.purchase, purchase_owed + 7),
		)
		listed = next(item for item in follow_up.list_imports(self.bank_account) if item["name"] == statement.name)
		self.assertEqual(listed["counts"], self._overview(statement)["counts"])
		self.assertEqual(listed["progress"], {"total": 2, "waiting": 1, "done": 1})
		self.assertEqual(listed["source"], "manual")

	# -- the rights ---------------------------------------------------------------------------------------------------

	def test_somebody_who_cannot_read_the_import_cannot_follow_it(self):
		statement = self._import(self._line("Sales Invoice", self.sales, flt(self._owed("Sales Invoice", self.sales))))
		with as_role("Guest"):
			with self.assertRaises(frappe.PermissionError):
				follow_up.get_import_overview(statement.name)
			with self.assertRaises(frappe.PermissionError):
				follow_up.list_imports()
