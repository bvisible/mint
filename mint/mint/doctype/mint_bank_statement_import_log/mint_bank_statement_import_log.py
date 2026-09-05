# //// Neoffice — NOT ours: upstream v1.5.0 doctype controller, carried by hand (89e7929).
# //// Byte-identical to upstream/develop. Take upstream's at the merge, drop this marker.
# Copyright (c) 2026, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MintBankStatementImportLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bank_account: DF.Link
		closing_balance: DF.Currency
		end_date: DF.Date | None
		file: DF.Attach
		number_of_transactions: DF.Int
		start_date: DF.Date | None
	# end: auto-generated types
