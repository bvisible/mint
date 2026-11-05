# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE RULE OF A CUSTOMER WHO PAYS LESS THAN THE INVOICE: READING IT, SETTING IT, COUNTING THE CONFIRMATIONS, ACTING ON IT.
# ////
# //// The rule itself is a document (Payment Gap Rule, one per customer and company, made by a person from the card of a
# //// gap or by Nora). Here it is read, matched against a payment, confirmed by each person's decision, and applied by the
# //// import at the level the company chose for this customer:
# ////   suggest    nothing happens at the import, the card proposes the handling
# ////   draft      the import prepares the credit note as a draft; the person validates it from the card
# ////   automatic  the import makes it by itself: only once a person confirmed it AUTO_AFTER times, only for a payment at
# ////              the customer's usual share, only when the invoice is recognised without doubt and the company let
# ////              payment gaps pass by themselves. Anything else stays for a person.

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from mint.apis.gap_credit_note import SAME_SHARE
from mint.mint.doctype.payment_gap_rule.payment_gap_rule import AUTO_AFTER

RULE = "Payment Gap Rule"
FIELDS = ["name", "company", "customer", "action", "mode", "share", "account", "confirmed_times", "last_confirmed_on", "disabled"]
MODES = ("suggest", "draft", "automatic")
ACTIONS = ("credit_note", "gap")


def get(company: str, customer: str):
	rows = frappe.get_all(RULE, filters={"company": company, "customer": customer}, fields=FIELDS, limit_page_length=1)
	return rows[0] if rows else None


def matches(rule, share: float, strict: bool = False) -> bool:
	"""The rule applies to a payment at `share` (a fraction of the invoice) when it is within two points of the usual
	share. A rule with no usual share applies to any partial payment, except where `strict` (acting by itself)."""
	if not rule or rule.disabled:
		return False
	if not flt(rule.share):
		return not strict
	return abs(flt(rule.share) / 100 - share) <= SAME_SHARE + 1e-9


def account_for(rule, share: float) -> str | None:
	"""The account the rule of the customer names for the credit note, when the rule is for a payment like this one: it is
	the account of the card and of the draft the import prepared, so nobody has to choose it again."""
	if rule and not rule.disabled and rule.action == "credit_note" and rule.account and matches(rule, share):
		return rule.account
	return None


def summary(rule, share: float) -> dict:
	"""What the card shows of the rule of this customer for a payment at this share."""
	if not rule:
		return {"exists": False, "auto_after": AUTO_AFTER}
	confirmed = int(rule.confirmed_times or 0)
	return {
		"exists": True,
		"name": rule.name,
		"mode": rule.mode,
		"action": rule.action,
		"share": flt(rule.share, 1),
		"account": rule.account,
		"confirmed_times": confirmed,
		"can_automatic": confirmed >= AUTO_AFTER and bool(flt(rule.share)),
		"matches": matches(rule, share),
		"disabled": bool(rule.disabled),
		"auto_after": AUTO_AFTER,
	}


def set_rule(
	company: str,
	customer: str,
	mode: str,
	action: str,
	share: float,
	account: str | None,
	seeded: int,
	override_share: bool = False,
) -> str:
	"""Make or change the rule of this customer. `share` is the fraction of the invoice paid now, taken as the usual one
	when the rule is new; `seeded` the confirmations the customer's own history already gives it (credit notes the
	office made by hand at this share), so that a habit of years is not asked to be repeated again."""
	if mode not in MODES or action not in ACTIONS:
		frappe.throw(_("Unknown level or handling of the rule."))
	existing = get(company, customer)
	if existing:
		doc = frappe.get_doc(RULE, existing.name)
		doc.mode, doc.action, doc.disabled = mode, action, 0
		if account:
			doc.account = account
		# the share a person said replaces the usual one; the share of a payment only fills a rule that has none
		if override_share or not flt(doc.share):
			doc.share = flt(share * 100, 1)
		doc.save()
	else:
		doc = frappe.get_doc(
			{
				"doctype": RULE,
				"company": company,
				"customer": customer,
				"mode": mode,
				"action": action,
				"share": flt(share * 100, 1),
				"account": account or None,
				"confirmed_times": int(seeded or 0),
			}
		)
		doc.insert()
	return doc.name


def confirm(company: str, customer: str, share: float, action: str) -> bool:
	"""A person decided this handling for a payment at this share: one more confirmation of the rule, when the rule is
	for this handling and this share. False when it changed nothing."""
	rule = get(company, customer)
	if not rule or rule.disabled or rule.action != action or not matches(rule, share):
		return False
	values = {"confirmed_times": int(rule.confirmed_times or 0) + 1, "last_confirmed_on": nowdate()}
	if not flt(rule.share):
		values["share"] = flt(share * 100, 1)
	frappe.db.set_value(RULE, rule.name, values, update_modified=False)
	return True


def handle_at_import(verdict, invoice: str, transaction, bank_transaction: str, ledger_account: str, stats: dict) -> bool:
	"""What the import does with a partial payment of a sale whose customer has a rule. True when it settled the line by
	itself; a draft is prepared and the line left to a person (False), and any doubt leaves the line as it was."""
	from mint.apis import gap_credit_note, payment_gap, statement_follow_up as follow_up

	if verdict.kind != "partial":
		return False
	customer = frappe.db.get_value("Sales Invoice", invoice, "customer")
	share = gap_credit_note.share_paid(invoice, verdict.amount)
	rule = get(verdict.company, customer)
	if not rule or rule.mode == "suggest" or not matches(rule, share, strict=True):
		return False
	credit = rule.action == "credit_note"
	blocker = (
		gap_credit_note.preview(verdict.company, customer, transaction.date, verdict.gap, rule.account or None)["blocker"]
		if credit
		else payment_gap.account_problem(verdict, rule.account, True)
	)
	if blocker:
		return False
	label = _("{0} - Payment for {1}").format(transaction.party_name or transaction.party_match, invoice)

	if rule.mode == "draft":
		if not credit:
			return False
		remark = _("Balance of {0}, paid {1} on {2}").format(invoice, verdict.amount, transaction.date)
		draft = gap_credit_note.prepare(verdict.company, customer, transaction.date, verdict.gap, rule.account or None, remark)
		transaction.db_set({"credit_note": draft, "payment_gap_rule": rule.name})
		return False

	settings = payment_gap.get_settings(verdict.company)
	company_currency = frappe.get_cached_value("Company", verdict.company, "default_currency")
	if not (
		int(rule.confirmed_times or 0) >= AUTO_AFTER
		and settings.automatic
		and verdict.sure
		and verdict.currency == company_currency
	):
		return False
	reference = transaction.unique_reference or transaction.reference or ""
	entry = payment_gap.book(
		verdict,
		"Sales Invoice",
		invoice,
		ledger_account,
		transaction.date,
		reference,
		label,
		by_person=True,
		account=None if credit else (rule.account or None),
		settle_in_full=not credit,
	)
	from mint.mint.doctype.mint_bank_statement_import.mint_bank_statement_import import _link_payment_entry_to_bt

	_link_payment_entry_to_bt(frappe.get_doc("Bank Transaction", bank_transaction), entry, reconciliation_type="Voucher Created")
	made = follow_up.make_credit_note(verdict, invoice, transaction.date, rule.account or None) if credit else None
	follow_up.note_decision(bank_transaction, "passed_gap", made)
	transaction.db_set({"payment_entry": entry, "credit_note": made, "payment_gap_rule": rule.name, "status": "Paid", "imported": 1})
	stats["auto_matched"] += 1
	stats["passed_with_gap"] += 1
	stats["gap_total"] += abs(verdict.gap)
	return True


# -- what Nora reads and does with the rule of a customer -----------------------------------------------------------------
# Nora is told what the customer's own invoices say (the share it usually pays, how often the rest ended as a credit note)
# and what rule it already has; she can propose the rule, and make it once the person said yes. Same checks as the card.


def overview(company: str, customer: str) -> dict:
	"""The rule of this customer (or none), what its invoices say, and what its credit note would be made of."""
	from mint.apis import gap_credit_note

	share = gap_credit_note.usual_share(company, customer)
	habit = gap_credit_note.history(company, customer, "", share) if share else None
	rule = get(company, customer)
	made = gap_credit_note.defaults(company, customer)
	return {
		"company": company,
		"customer": customer,
		"rule": summary(rule, share or 0),
		"habit": habit,
		"credit_note": {"item": made.item_name, "account": made.account, "times": made.times, "source": made.source},
	}


def plan(
	company: str,
	customer: str,
	mode: str,
	action: str = "credit_note",
	share: float | str | None = None,
	account: str | None = None,
) -> dict:
	"""What setting the rule would do, checked as the document checks it, nothing written. `share` is a percentage (the habit
	of the customer when left out). What refuses it is in `problems`, as sentences: nothing is raised."""
	from mint.apis import gap_credit_note, payment_gap

	problems = []
	if mode not in MODES or action not in ACTIONS:
		problems.append(_("Unknown level or handling of the rule."))
	existing = get(company, customer)
	said = None if share in (None, "") else flt(share) / 100
	fraction = said if said is not None else (flt(existing.share) / 100 if existing and flt(existing.share) else gap_credit_note.usual_share(company, customer))
	if fraction is not None and not 0 < fraction <= 1:
		problems.append(_("The usual share is a percentage between 0 and 100."))
	seeded = gap_credit_note.history(company, customer, "", fraction)["closed_by_credit"] if (fraction and action == "credit_note") else 0
	confirmed = int(existing.confirmed_times or 0) if existing else seeded
	if mode in ("draft", "automatic") and not fraction:
		problems.append(_("A rule that prepares or makes the credit note by itself needs the usual share of the customer."))
	if mode == "automatic" and confirmed < AUTO_AFTER:
		problems.append(
			_("The level automatic is available after {0} confirmations by a person: {1} so far.").format(AUTO_AFTER, confirmed)
		)
	chosen = account or (existing.account if existing else None)
	if chosen:
		if action == "credit_note":
			problem = gap_credit_note.problem(company, chosen)
			if problem:
				problems.append(problem)
		else:
			try:
				payment_gap.check_account(company, chosen)
			except frappe.ValidationError as error:
				frappe.clear_last_message()
				problems.append(str(error))
	return {
		"change": "update" if existing else "create",
		"company": company,
		"customer": customer,
		"mode": mode,
		"action": action,
		"share": flt(fraction * 100, 1) if fraction else None,
		"share_from_habit": said is None,
		"account": chosen,
		"confirmed_times": confirmed,
		"automatic_available": confirmed >= AUTO_AFTER and bool(fraction),
		# what the customer's own invoices say of this share: the evidence the person is shown before they say yes
		"habit": gap_credit_note.history(company, customer, "", fraction) if fraction else None,
		"problems": problems,
	}


def apply(
	company: str,
	customer: str,
	mode: str,
	action: str = "credit_note",
	share: float | str | None = None,
	account: str | None = None,
) -> dict:
	"""Make or change the rule as `plan` showed it. Refused, in sentences, when `plan` found a problem."""
	from mint.apis import gap_credit_note

	checked = plan(company, customer, mode, action, share, account)
	if checked["problems"]:
		frappe.throw(" ".join(checked["problems"]))
	fraction = flt(checked["share"]) / 100
	existing = get(company, customer)
	frappe.has_permission(RULE, "write" if existing else "create", throw=True)
	seeded = gap_credit_note.history(company, customer, "", fraction)["closed_by_credit"] if action == "credit_note" else 0
	set_rule(company, customer, mode, action, fraction, checked["account"], seeded, override_share=share not in (None, ""))
	return summary(get(company, customer), fraction)
