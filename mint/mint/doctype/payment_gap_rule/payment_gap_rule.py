# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT A COMPANY DECIDED FOR A CUSTOMER WHO PAYS LESS THAN THE INVOICE, BEYOND A SMALL GAP.
# ////
# //// One rule per customer and company, made by a person from the card of a gap or by Nora, never by the import: the
# //// import only reads it. Three levels: the card proposes it (suggest), the credit note is prepared as a draft (draft),
# //// it is made by itself (automatic). The level automatic is only available once a person confirmed the handling at
# //// least AUTO_AFTER times for this customer, and only for a payment at the customer's usual share: a rule never acts
# //// on a payment it has not already seen the like of.

import frappe
from frappe import _
from frappe.model.document import Document

# A person confirmed the handling this many times before it may be made by itself.
AUTO_AFTER = 3


class PaymentGapRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link | None
		action: DF.Literal["credit_note", "gap"]
		company: DF.Link
		confirmed_times: DF.Int
		customer: DF.Link
		disabled: DF.Check
		last_confirmed_on: DF.Date | None
		mode: DF.Literal["suggest", "draft", "automatic"]
		share: DF.Percent
	# end: auto-generated types

	def validate(self):
		self._one_per_customer()
		if not 0 <= (self.share or 0) <= 100:
			frappe.throw(_("The usual share is a percentage between 0 and 100."))
		self._check_account()
		if self.mode in ("draft", "automatic") and not self.share:
			frappe.throw(_("A rule that prepares or makes the credit note by itself needs the usual share of the customer."))
		if self.mode == "automatic" and (self.confirmed_times or 0) < AUTO_AFTER:
			frappe.throw(
				_("The level automatic is available after {0} confirmations by a person: {1} so far.").format(
					AUTO_AFTER, self.confirmed_times or 0
				)
			)

	def _one_per_customer(self):
		other = frappe.db.exists(
			"Payment Gap Rule", {"company": self.company, "customer": self.customer, "name": ("!=", self.name)}
		)
		if other:
			frappe.throw(_("There is already a rule for {0} in {1}: {2}.").format(self.customer, self.company, other))

	def _check_account(self):
		if not self.account:
			return
		if self.action == "credit_note":
			from mint.apis import gap_credit_note

			problem = gap_credit_note.problem(self.company, self.account)
		else:
			from mint.apis import payment_gap

			try:
				payment_gap.check_account(self.company, self.account)
				problem = ""
			except frappe.ValidationError as error:
				frappe.clear_last_message()
				problem = str(error)
		if problem:
			frappe.throw(problem)
