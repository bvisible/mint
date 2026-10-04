frappe.pages['bank-reconciliation'].on_page_load = function (wrapper) {
	// Redirect to the mint web app
	window.location.href = '/mint';

	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bank Reconciliation - Mint"),
		single_column: true,
	});

	//// Neoffice — upstream passed the button label as a bare string, which set_primary_action does not
	//// translate; it stayed English. We wrap it in __().
	page.set_primary_action(__("Open Bank Reconciliation"), function () {
		window.location.href = '/mint';
	});
}
