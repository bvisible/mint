// Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mint Bank Statement Import", {
    refresh(frm) {
        // Clean up any existing polling interval
        if (frm._poll_interval) {
            clearInterval(frm._poll_interval);
            frm._poll_interval = null;
        }

        // Show Document Scan link if available
        if (frm.doc.document_scan_name) {
            frm.add_custom_button(__("View Document Scan"), () => {
                frappe.set_route("Form", "Document Scan", frm.doc.document_scan_name);
            });
        }

        // If currently processing, start polling
        if (frm.doc.ocr_status === "Processing") {
            frm.dashboard.set_headline(__("OCR processing in progress..."), "blue");
            start_polling(frm);
        }

        // Show process button if not yet started and file is uploaded
        if (frm.doc.docstatus === 0 && frm.doc.file && !frm.doc.ocr_status) {
            frm.add_custom_button(__("Process via Nora OCR"), () => {
                start_ocr_processing(frm);
            }).addClass("btn-primary");
        }

        // Show retry button if failed
        if (frm.doc.docstatus === 0 && frm.doc.ocr_status === "Failed") {
            frm.add_custom_button(__("Retry OCR"), () => {
                // Clear previous state
                frm.set_value("ocr_status", "");
                frm.set_value("document_scan_name", "");
                frm.set_value("error", "");
                frm.save().then(() => {
                    start_ocr_processing(frm);
                });
            }).addClass("btn-primary");
        }
    },

    onload_post_render(frm) {
        // Resume polling if document was processing
        if (frm.doc.ocr_status === "Processing" && frm.doc.document_scan_name) {
            start_polling(frm);
        }
    },

    before_unload(frm) {
        // Clean up polling on form close
        if (frm._poll_interval) {
            clearInterval(frm._poll_interval);
            frm._poll_interval = null;
        }
    }
});

function start_ocr_processing(frm) {
    frappe.show_alert({
        message: __("Starting OCR processing..."),
        indicator: "blue"
    });

    frm.call({
        method: "start_ocr_processing",
        freeze: false,  // NO FREEZE - async processing
        callback: function(r) {
            if (r.message && r.message.status === "Processing") {
                frappe.show_alert({
                    message: __("OCR processing started. Please wait..."),
                    indicator: "blue"
                });
                frm.reload_doc().then(() => {
                    start_polling(frm);
                });
            }
        },
        error: function(r) {
            frappe.show_alert({
                message: __("Failed to start OCR processing"),
                indicator: "red"
            });
        }
    });
}

function start_polling(frm) {
    // Don't start if already polling
    if (frm._poll_interval) {
        return;
    }

    frm.dashboard.set_headline(__("OCR processing in progress..."), "blue");

    let poll_count = 0;
    const max_polls = 180;  // 6 minutes max (180 * 2 seconds)

    frm._poll_interval = setInterval(() => {
        poll_count++;

        // Safety: stop after max polls
        if (poll_count > max_polls) {
            clearInterval(frm._poll_interval);
            frm._poll_interval = null;
            frm.dashboard.set_headline(__("Processing timeout - please check Document Scan"), "orange");
            return;
        }

        frm.call({
            method: "check_processing_status",
            callback: function(r) {
                if (!r.message) return;

                if (r.message.status === "Completed") {
                    clearInterval(frm._poll_interval);
                    frm._poll_interval = null;

                    frappe.show_alert({
                        message: __("{0} transactions extracted!", [r.message.count || 0]),
                        indicator: "green"
                    });

                    frm.reload_doc();
                }
                else if (r.message.status === "Failed") {
                    clearInterval(frm._poll_interval);
                    frm._poll_interval = null;

                    frappe.msgprint({
                        title: __("OCR Failed"),
                        message: r.message.error || __("Unknown error"),
                        indicator: "red"
                    });

                    frm.reload_doc();
                }
                // else: still processing, continue polling
            },
            error: function() {
                // Network error - continue polling but log
                console.warn("Polling error - will retry");
            }
        });
    }, 2000);  // Poll every 2 seconds
}
