# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHO MAY CALL WHAT: THE ENDPOINTS OF MINT THAT NO RIGHT STOOD IN FRONT OF.
# ////
# //// ERPNext v16 hardened every whitelisted method of its bank module (permission per record, POST for
# //// anything that writes, no read of a record the user may not read), and v15-hotfix received the same.
# //// Mint kept its own copies of those methods, and its own draft-entry and file readers, without them:
# //// a portal customer could read another customer's party details, have any private spreadsheet parsed,
# //// and an accountant limited to one company could read, and clear, another company's bank lines.
# //// Each test below was red on the code as it stood, with the identity that acts in real life
# //// (frappe/tests/roles.py), never Administrator.

import unittest
from unittest.mock import patch

import frappe
from frappe.permissions import add_user_permission
from frappe.tests.roles import as_role, make_persona
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from mint.apis import bank_account, bank_clearance, bank_reconciliation, nora_ocr, rules, statement_import

SCOPED = "mint-scoped-accountant@yopmail.com"
HOME = "mint-home-accountant@yopmail.com"
PROBE_FILE = "mint-permission-probe.csv"

# Everything below writes, so none of it may answer to a link someone is led to open (a GET carries no CSRF token).
POST_ONLY = (
	bank_account.set_closing_balance_as_per_statement,
	bank_reconciliation.reconcile_vouchers,
	bank_reconciliation.unreconcile_transaction,
	bank_reconciliation.undo_reconciliation_action,
	bank_reconciliation.create_internal_transfer,
	bank_reconciliation.clear_clearing_date,
	bank_clearance.update_clearance_date,
	nora_ocr.start_ocr_processing,
	nora_ocr.check_ocr_processing_status,
	nora_ocr.create_import_from_document_scan,
)


class TestMintEndpointsAnswerOnlyToWhoMayRead(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		transaction = frappe.get_all(
			"Bank Transaction",
			filters={"docstatus": 1},
			fields=["name", "bank_account", "withdrawal", "deposit"],
			limit=1,
		)
		if not transaction:
			raise unittest.SkipTest("no submitted Bank Transaction on this site")
		cls.transaction = transaction[0]
		account = frappe.db.get_value(
			"Bank Account", cls.transaction.bank_account, ["name", "company", "account"], as_dict=True
		)
		cls.bank_account, cls.company, cls.gl_account = account.name, account.company, account.account
		others = frappe.get_all("Company", filters={"name": ["!=", cls.company]}, pluck="name", limit=1)
		if not others:
			raise unittest.SkipTest("the site has a single company")
		cls.other_company = others[0]
		customers = frappe.get_all("Customer", pluck="name", limit=2)
		cls.own_customer, cls.other_customer = customers[0], customers[1]
		cls.voucher = frappe.get_all(
			"Payment Entry", filters={"docstatus": 1, "company": cls.company}, pluck="name", limit=1
		)
		cls._make_probe_file()
		cls._make_draft_entry()
		# An accountant who may only see the OTHER company, and one who sees the company of the bank line.
		make_persona("accountant", SCOPED)
		add_user_permission("Company", cls.other_company, SCOPED)
		make_persona("accountant", HOME)
		add_user_permission("Company", cls.company, HOME)
		frappe.clear_cache(user=SCOPED)
		frappe.clear_cache(user=HOME)

	@classmethod
	def _make_probe_file(cls):
		cls.probe_url = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": PROBE_FILE,
				"is_private": 1,
				"content": "Date,Description,Debit,Credit,Balance\n2026-01-02,Somebody's salary,0,5000,9000\n",
			}
		).insert(ignore_if_duplicate=True).file_url

	@classmethod
	def _make_draft_entry(cls):
		debit_side = "credit" if cls.transaction.withdrawal > 0 else "debit"
		other_side = "debit" if debit_side == "credit" else "credit"
		expense = frappe.get_all(
			"Account",
			filters={"company": cls.company, "root_type": "Expense", "is_group": 0},
			pluck="name",
			limit=1,
		)
		cost_center = frappe.get_cached_value("Company", cls.company, "cost_center")
		cls.draft = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Bank Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"cheque_no": "MINT-PROBE",
				"cheque_date": nowdate(),
				"accounts": [
					{"account": cls.gl_account, f"{debit_side}_in_account_currency": 123.45},
					{
						"account": expense[0],
						"cost_center": cost_center,
						f"{other_side}_in_account_currency": 123.45,
					},
				],
			}
		).insert()

	# -- who may read another customer's party, an account's defaults, a private file ------------------------

	def test_a_portal_customer_cannot_read_another_customers_party_details(self):
		with as_role("portal_customer", customer=self.own_customer):
			with self.assertRaises(frappe.PermissionError):
				bank_reconciliation.get_party_details(self.company, "Customer", self.other_customer)

	def test_a_portal_customer_cannot_read_the_defaults_of_an_account(self):
		with as_role("portal_customer", customer=self.own_customer):
			with self.assertRaises(frappe.PermissionError):
				bank_reconciliation.get_account_defaults(self.gl_account)

	def test_a_portal_customer_cannot_have_a_private_file_parsed(self):
		with as_role("portal_customer", customer=self.own_customer):
			with self.assertRaises(frappe.PermissionError):
				statement_import.get_statement_details(self.probe_url, self.bank_account)

	def test_a_portal_customer_cannot_import_someone_elses_document_scan(self):
		scan = frappe.get_all("Document Scan", pluck="name", limit=1)
		if not scan:
			self.skipTest("no Document Scan on this site")
		# The OCR is queued, never run: the test must not reach a service outside.
		with as_role("portal_customer", customer=self.own_customer), patch.object(frappe, "enqueue"):
			with self.assertRaises(frappe.PermissionError):
				nora_ocr.create_import_from_document_scan(scan[0], self.bank_account)

	def test_a_portal_customer_cannot_start_the_rule_evaluation(self):
		with as_role("portal_customer", customer=self.own_customer):
			with self.assertRaises(frappe.PermissionError):
				rules.run_rule_evaluation()

	# -- an accountant limited to one company -----------------------------------------------------------------

	def test_a_scoped_accountant_cannot_read_the_draft_entries_of_another_company(self):
		with as_role("accountant", email=SCOPED):
			with self.assertRaises(frappe.PermissionError):
				self._drafts()

	def test_a_scoped_accountant_cannot_read_the_closing_balance_of_another_company(self):
		with as_role("accountant", email=SCOPED):
			with self.assertRaises(frappe.PermissionError):
				bank_account.get_closing_balance_as_per_statement(self.bank_account, nowdate())

	def test_a_scoped_accountant_cannot_set_the_closing_balance_of_another_company(self):
		with as_role("accountant", email=SCOPED):
			with self.assertRaises(frappe.PermissionError):
				bank_account.set_closing_balance_as_per_statement(self.bank_account, nowdate(), 1.0)

	def test_a_scoped_accountant_cannot_clear_a_voucher_of_another_company(self):
		if not self.voucher:
			self.skipTest("no submitted Payment Entry in the company of the bank line")
		with as_role("accountant", email=SCOPED):
			with self.assertRaises(frappe.PermissionError):
				bank_clearance.update_clearance_date("Payment Entry", self.voucher[0], self.gl_account, nowdate())

	def test_a_voucher_of_a_doctype_that_is_not_one_cannot_be_named(self):
		with as_role("accountant", email=HOME):
			with self.assertRaises(frappe.ValidationError):
				bank_clearance.update_clearance_date("User", "Administrator", self.gl_account, nowdate())

	# -- the accountant of the company still does her work ------------------------------------------------------

	def test_the_accountant_of_the_company_still_reads_and_clears(self):
		with as_role("accountant", email=HOME):
			self.assertIn("party_name", bank_reconciliation.get_party_details(self.company, "Customer", self.own_customer))
			self.assertIsNotNone(bank_reconciliation.get_account_defaults(self.gl_account))
			self.assertIn("balance", bank_account.get_closing_balance_as_per_statement(self.bank_account, nowdate()))
			self.assertIn(self.draft.name, {row["name"] for row in self._drafts()})
			bank_account.set_closing_balance_as_per_statement(self.bank_account, nowdate(), 1.0)
			if self.voucher:
				bank_clearance.update_clearance_date("Payment Entry", self.voucher[0], self.gl_account, nowdate())

	def test_the_accountant_still_has_her_own_file_parsed(self):
		with as_role("accountant", email=HOME):
			own_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "mint-own-statement.csv",
					"is_private": 1,
					"content": "Date,Description,Debit,Credit,Balance\n2026-01-02,Rent,100,0,900\n",
				}
			).insert()
			self.assertTrue(statement_import.get_statement_details(own_file.file_url, self.bank_account))

	# -- anything that writes answers to POST only -----------------------------------------------------------------

	def test_what_writes_answers_to_post_only(self):
		# Frappe v15 keeps the allowed methods in a list, our fork (v16 parity) in a tuple.
		not_post = [
			fn.__name__
			for fn in POST_ONLY
			if tuple(frappe.allowed_http_methods_for_whitelisted_func.get(fn, ())) != ("POST",)
		]
		self.assertEqual(not_post, [])

	def _drafts(self):
		return bank_reconciliation.get_draft_journal_entries(
			self.transaction.name, add_days(nowdate(), -3650), add_days(nowdate(), 3650)
		)
