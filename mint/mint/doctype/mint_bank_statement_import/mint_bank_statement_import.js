// Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mint Bank Statement Import", {
    refresh(frm) {
        if (frm.doc.docstatus === 0 && frm.doc.file) {
            frm.add_custom_button(__("Process via Nora OCR"), () => {
                frappe.show_alert({
                    message: __("Processing bank statement with AI... This may take up to 60 seconds."),
                    indicator: "blue"
                });

                frm.call({
                    method: "process_file",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Extracting transactions from PDF..."),
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __("Transactions extracted successfully!"),
                                indicator: "green"
                            });
                            frm.reload_doc();
                        }
                    },
                    error: function(r) {
                        frappe.show_alert({
                            message: __("Failed to process file. Please try again."),
                            indicator: "red"
                        });
                    }
                });
            }, __("Actions"));
        }
    },
});
