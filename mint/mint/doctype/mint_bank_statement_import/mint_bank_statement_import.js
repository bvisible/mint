// Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mint Bank Statement Import", {
    refresh(frm) {
        // Clean up any existing polling interval
        if (frm._poll_interval) {
            clearInterval(frm._poll_interval);
            frm._poll_interval = null;
        }

        // Clean up any existing overlay
        if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) {
            neoffice.processing_overlay.hide();
        }

        // Check if we just completed - don't restart polling
        if (frm._ocr_just_completed) {
            frm._ocr_just_completed = false;
            // Don't start polling, just continue with refresh
        }
        // If currently processing, start polling
        else if (frm.doc.ocr_status === "Processing") {
            frm.dashboard.set_headline(__("OCR processing in progress..."), "blue");
            start_polling(frm);
        }

        // Show Document Scan link if available
        if (frm.doc.document_scan_name) {
            frm.add_custom_button(__("View Document Scan"), () => {
                frappe.set_route("Form", "Document Scan", frm.doc.document_scan_name);
            });
        }

        // Show process button if not yet started and file is uploaded and document is saved
        if (frm.doc.docstatus === 0 && frm.doc.file && !frm.doc.ocr_status && !frm.is_new()) {
            frm.add_custom_button(__("Analyze and extract with Nora AI"), () => {
                start_ocr_processing(frm);
            }).addClass("btn-primary");
        }

        // Show save first message if document is new
        if (frm.doc.docstatus === 0 && frm.doc.file && !frm.doc.ocr_status && frm.is_new()) {
            frm.dashboard.set_headline(__("Save the document first to enable OCR processing"), "yellow");
        }

        // Show retry button if failed
        if (frm.doc.docstatus === 0 && frm.doc.ocr_status === "Failed") {
            frm.add_custom_button(__("Retry with Nora AI"), () => {
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
        // Clean up overlay if active
        if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) {
            neoffice.processing_overlay.hide();
        }
    }
});

function start_ocr_processing(frm, force_create = false) {
    frappe.show_alert({
        message: __("Starting OCR processing..."),
        indicator: "blue"
    });

    frappe.call({
        method: "mint.apis.nora_ocr.start_ocr_processing",
        args: {
            docname: frm.doc.name,
            force_create: force_create
        },
        freeze: false,  // NO FREEZE - we handle it ourselves
        callback: function(r) {
            if (r.message && r.message.status === "Processing") {
                frm.reload_doc().then(() => {
                    start_polling(frm);
                });
            }
            else if (r.message && r.message.status === "Duplicate") {
                // Show dialog with options
                show_duplicate_dialog(frm, r.message.existing_name);
            }
        },
        error: function(r) {
            frappe.show_alert({
                message: __("Failed to start OCR processing"),
                indicator: "red"
            });
            frm.reload_doc();
        }
    });
}

function show_duplicate_dialog(frm, existing_name) {
    const d = new frappe.ui.Dialog({
        title: __("Document Scan Already Exists"),
        fields: [
            {
                fieldtype: "HTML",
                options: `<p>${__("A Document Scan with the same name already exists:")}</p>
                          <p><strong>${existing_name}</strong></p>
                          <p>${__("What would you like to do?")}</p>`
            }
        ],
        primary_action_label: __("Scan Anyway"),
        primary_action: function() {
            d.hide();
            start_ocr_processing(frm, true);  // Force create with suffix
        },
        secondary_action_label: __("View Existing"),
        secondary_action: function() {
            d.hide();
            frappe.set_route("Form", "Document Scan", existing_name);
        }
    });
    d.show();
}

function start_polling(frm) {
    // Don't start if already polling
    if (frm._poll_interval) {
        return;
    }

    // Show freeze with skip button
    show_processing_freeze(frm);

    let poll_count = 0;
    const max_polls = 180;  // 6 minutes max (180 * 2 seconds)

    frm._poll_interval = setInterval(() => {
        poll_count++;

        // Safety: stop after max polls
        if (poll_count > max_polls) {
            stop_polling(frm);
            frm.dashboard.set_headline(__("Processing timeout - please check Document Scan"), "orange");
            return;
        }

        frappe.call({
            method: "mint.apis.nora_ocr.check_ocr_processing_status",
            args: {
                docname: frm.doc.name
            },
            callback: function(r) {
                if (!r.message) return;

                if (r.message.status === "Completed") {
                    // Mark as completed to prevent restart on reload
                    frm._ocr_just_completed = true;
                    stop_polling(frm);

                    frappe.show_alert({
                        message: __("{0} transactions extracted!", [r.message.count || 0]),
                        indicator: "green"
                    });

                    frm.reload_doc();
                }
                else if (r.message.status === "Failed") {
                    // Mark as completed to prevent restart on reload
                    frm._ocr_just_completed = true;
                    stop_polling(frm);

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

function stop_polling(frm) {
    if (frm._poll_interval) {
        clearInterval(frm._poll_interval);
        frm._poll_interval = null;
    }
    // Hide processing overlay
    if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) {
        neoffice.processing_overlay.hide();
    }
}

function show_processing_freeze(frm) {
    // Use neoffice processing overlay component
    if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) {
        neoffice.processing_overlay.show({
            message: __("Nora AI analysis in progress..."),
            button_label: __("Continue in background"),
            on_background: function() {
                frm.dashboard.set_headline(__("OCR processing in progress..."), "blue");
                frappe.show_alert({
                    message: __("Processing continues in background. The page will reload when done."),
                    indicator: "blue"
                });
            }
        });
    } else {
        // Fallback to dashboard headline if neoffice not available
        frm.dashboard.set_headline(__("OCR processing in progress..."), "blue");
    }
}
