# //// Neoffice — added file (no upstream equivalent).
# ////
# //// RECONCILING A PARTY'S PAYMENTS AGAINST ITS INVOICES, PLAYED ON REAL DATA BY THE PEOPLE WHO DO IT.
# ////
# //// The accountant of a company reconciles; a portal customer and an accountant limited to another company are
# //// refused at every door. The engine is ERPNext's, so what is proved here is what Mint adds: which parties are
# //// offered, the amount used per row, the preview that writes nothing, "nothing chosen" refused instead of
# //// everything allocated, and a screen that is out of date refused.

import json
import unittest

import frappe
from frappe.permissions import add_user_permission
from frappe.tests.roles import as_role, make_persona
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from mint.apis import party_reconciliation as pr

HOME = "mint-party-home-accountant@yopmail.com"
SCOPED = "mint-party-scoped-accountant@yopmail.com"


def _invoice(row, amount=None):
	return {"invoice_type": row["invoice_type"], "invoice_number": row["invoice_number"], **({"amount": amount} if amount else {})}


def _payment(row, amount=None):
	return {"reference_type": row["reference_type"], "reference_name": row["reference_name"], **({"amount": amount} if amount else {})}


class TestPartyReconciliation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = None
		for company in frappe.get_all("Company", pluck="name"):
			for party in pr.get_parties(company, "Customer", None, 1, 200):
				detail = pr.get_party_detail(company, "Customer", party["party"])
				if detail["invoices"] and detail["payments"]:
					cls.company, cls.party, cls.detail = company, party["party"], detail
					break
			if cls.company:
				break
		if not cls.company:
			raise unittest.SkipTest("no customer with open invoices and an unallocated payment on this site")
		others = frappe.get_all("Company", filters={"name": ["!=", cls.company]}, pluck="name", limit=1)
		if not others:
			raise unittest.SkipTest("the site has a single company")
		make_persona("accountant", HOME)
		add_user_permission("Company", cls.company, HOME)
		make_persona("accountant", SCOPED)
		add_user_permission("Company", others[0], SCOPED)
		frappe.clear_cache(user=HOME)
		frappe.clear_cache(user=SCOPED)
		cls.customers = frappe.get_all("Customer", pluck="name", limit=2)

	def _fresh(self):
		"""The party as it is now: the tests reconcile, and the class keeps one transaction."""
		with as_role("accountant", email=HOME):
			return pr.get_party_detail(self.company, "Customer", self.party)

	def _ledger_rows(self):
		return frappe.db.count("Payment Ledger Entry")

	# -- what is offered -----------------------------------------------------------------------------------------

	def test_the_accountant_is_offered_the_parties_that_have_both_sides(self):
		with as_role("accountant", email=HOME):
			parties = pr.get_parties(self.company, "Customer", None, 1, 200)
		self.assertIn(self.party, [p["party"] for p in parties])
		self.assertTrue(all(p["open_count"] and p["credit_count"] for p in parties))
		self.assertEqual(parties, sorted(parties, key=lambda p: p["oldest"] or frappe.utils.getdate()))

	def test_a_search_narrows_the_parties(self):
		with as_role("accountant", email=HOME):
			found = pr.get_parties(self.company, "Customer", self.party[:5].lower(), 1, 200)
			none = pr.get_parties(self.company, "Customer", "zzz-no-such-party-zzz", 1, 200)
		self.assertIn(self.party, [p["party"] for p in found])
		self.assertEqual(none, [])

	def test_the_detail_has_the_two_tables_and_a_ledger_that_agrees(self):
		with as_role("accountant", email=HOME):
			detail = pr.get_party_detail(self.company, "Customer", self.party)
		self.assertTrue(detail["invoices"] and detail["payments"])
		self.assertEqual(detail["check"]["difference"], 0)
		self.assertAlmostEqual(detail["totals"]["balance"], detail["totals"]["open"] - detail["totals"]["credit"], places=2)
		self.assertTrue(all("invoice_number" in row and "outstanding_amount" in row for row in detail["invoices"]))

	# -- what a click shows --------------------------------------------------------------------------------------

	def test_a_click_shows_the_voucher(self):
		row = self.detail["payments"][0]
		with as_role("accountant", email=HOME):
			shown = pr.get_voucher_detail(row["reference_type"], row["reference_name"])
		self.assertEqual(shown["name"], row["reference_name"])
		self.assertEqual(shown["status"], "Submitted")
		self.assertTrue(shown["route"].startswith("/app/"))
		with as_role("accountant", email=HOME), self.assertRaises(frappe.ValidationError):
			pr.get_voucher_detail("User", "Administrator")

	# -- the preview writes nothing; nothing chosen is refused -----------------------------------------------------

	def test_the_preview_settles_the_smaller_side_and_writes_nothing(self):
		detail = self._fresh()
		invoice, payment = detail["invoices"][0], detail["payments"][0]
		before = self._ledger_rows()
		with as_role("accountant", email=HOME):
			shown = pr.preview(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment)]))
		smaller = min(flt(invoice["outstanding_amount"]), flt(payment["amount"]))
		self.assertEqual(shown["settled"], flt(smaller, 2))
		self.assertEqual(shown["invoices_left"], flt(flt(invoice["outstanding_amount"]) - smaller, 2))
		self.assertEqual(shown["credits_left"], flt(flt(payment["amount"]) - smaller, 2))
		self.assertEqual(self._ledger_rows(), before)

	def test_nothing_chosen_is_refused_instead_of_everything_being_allocated(self):
		detail = self._fresh()
		before = self._ledger_rows()
		for invoices, payments in (([], []), ([_invoice(detail["invoices"][0])], []), ([], [_payment(detail["payments"][0])])):
			with as_role("accountant", email=HOME), self.assertRaises(frappe.ValidationError):
				pr.reconcile(self.company, "Customer", self.party, json.dumps(invoices), json.dumps(payments))
		self.assertEqual(self._ledger_rows(), before)

	# -- reconciling ---------------------------------------------------------------------------------------------

	def test_reconciling_part_of_an_invoice_with_part_of_a_credit_leaves_the_rest_open(self):
		detail = self._fresh()
		invoice, payment = detail["invoices"][0], detail["payments"][0]
		used = flt(min(10.0, flt(invoice["outstanding_amount"]), flt(payment["amount"])), 2)
		open_before = flt(frappe.db.get_value(invoice["invoice_type"], invoice["invoice_number"], "outstanding_amount"), 2)
		with as_role("accountant", email=HOME):
			done = pr.reconcile(
				self.company, "Customer", self.party, json.dumps([_invoice(invoice, used)]), json.dumps([_payment(payment, used)])
			)
		self.assertEqual(sum(flt(r["allocated_amount"]) for r in done["allocation"]), used)
		if invoice["invoice_type"] == "Sales Invoice":
			self.assertEqual(flt(frappe.db.get_value("Sales Invoice", invoice["invoice_number"], "outstanding_amount"), 2), flt(open_before - used, 2))
		# the party now offered is the same one, with that much less on both sides and a ledger that still agrees
		after = done["detail"]
		self.assertEqual(after["check"]["difference"], 0)
		self.assertAlmostEqual(after["totals"]["open"], detail["totals"]["open"] - used, places=2)
		self.assertAlmostEqual(after["totals"]["credit"], detail["totals"]["credit"] - used, places=2)

	def test_a_row_that_is_no_longer_what_the_screen_showed_is_refused(self):
		detail = self._fresh()
		invoice, payment = detail["invoices"][0], detail["payments"][0]
		too_much = flt(payment["amount"]) + 1
		missing = {"invoice_type": invoice["invoice_type"], "invoice_number": "NO-SUCH-INVOICE"}
		with as_role("accountant", email=HOME):
			with self.assertRaises(frappe.ValidationError):
				pr.preview(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment, too_much)]))
			with self.assertRaises(frappe.ValidationError):
				pr.preview(self.company, "Customer", self.party, json.dumps([missing]), json.dumps([_payment(payment)]))
			with self.assertRaises(frappe.ValidationError):
				pr.preview(self.company, "Customer", self.party, json.dumps([_invoice(invoice), _invoice(invoice)]), json.dumps([_payment(payment)]))

	def test_the_party_is_locked_to_its_own_kind(self):
		with as_role("accountant", email=HOME), self.assertRaises(frappe.ValidationError):
			pr.get_parties(self.company, "Employee", None, 1, 10)

	# -- who is refused ----------------------------------------------------------------------------------------

	def test_a_portal_customer_is_refused_everywhere(self):
		invoice, payment = self.detail["invoices"][0], self.detail["payments"][0]
		calls = (
			lambda: pr.get_parties(self.company, "Customer", None, 1, 10),
			lambda: pr.get_party_detail(self.company, "Customer", self.party),
			lambda: pr.preview(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment)])),
			lambda: pr.reconcile(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment)])),
			lambda: pr.get_voucher_detail(payment["reference_type"], payment["reference_name"]),
		)
		for call in calls:
			with as_role("portal_customer", customer=self.customers[0]), self.assertRaises(frappe.PermissionError):
				call()

	def test_an_accountant_of_another_company_is_refused_everywhere(self):
		invoice, payment = self.detail["invoices"][0], self.detail["payments"][0]
		calls = (
			lambda: pr.get_parties(self.company, "Customer", None, 1, 10),
			lambda: pr.get_party_detail(self.company, "Customer", self.party),
			lambda: pr.preview(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment)])),
			lambda: pr.reconcile(self.company, "Customer", self.party, json.dumps([_invoice(invoice)]), json.dumps([_payment(payment)])),
			lambda: pr.get_voucher_detail(payment["reference_type"], payment["reference_name"]),
		)
		for call in calls:
			with as_role("accountant", email=SCOPED), self.assertRaises(frappe.PermissionError):
				call()

	def test_reading_and_reconciling_answer_to_the_right_http_method(self):
		for fn in (pr.get_parties, pr.get_party_detail, pr.get_voucher_detail):
			self.assertEqual(tuple(frappe.allowed_http_methods_for_whitelisted_func[fn]), ("GET",))
		for fn in (pr.preview, pr.reconcile):
			self.assertEqual(tuple(frappe.allowed_http_methods_for_whitelisted_func[fn]), ("POST",))
