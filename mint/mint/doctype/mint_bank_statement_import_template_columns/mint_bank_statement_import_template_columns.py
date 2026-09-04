#//// Neoffice — NOT ours: upstream v1.5.0 child-table controller, carried by hand (89e7929).
#//// Byte-identical to upstream/develop. Take upstream's at the merge, drop this marker.
# Copyright (c) 2026, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MintBankStatementImportTemplateColumns(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		header_text: DF.Data
		maps_to: DF.Literal["Do not import", "Date", "Description", "Amount", "Balance", "Deposit", "Withdrawal", "Reference", "Transaction Type"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		variable: DF.Data | None
	# end: auto-generated types

	pass
