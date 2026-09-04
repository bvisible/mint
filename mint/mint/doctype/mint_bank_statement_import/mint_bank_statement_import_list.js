////// Neoffice — added file (no upstream equivalent): list view settings for Mint Bank
////// Statement Import (6d264d7). Upstream ships no list JS — the list showed only the
////// processing status, so a cancelled import and a submitted one looked the same. This
////// renders the docstatus as its own badge and colours the OCR states. Wired in hooks.py.
// Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

frappe.listview_settings["Mint Bank Statement Import"] = {
    add_fields: ["status", "ocr_status", "docstatus"],

    get_indicator: function(doc) {
        // Show indicator based on docstatus first, then processing status
        if (doc.docstatus === 0) {
            // Draft - show processing status with blue/gray tones
            if (doc.status === "Error" || doc.ocr_status === "Failed") {
                return [__("Draft - Error"), "red", "docstatus,=,0"];
            }
            if (doc.ocr_status === "Processing") {
                return [__("Draft - Processing"), "blue", "docstatus,=,0"];
            }
            if (doc.status === "Completed") {
                return [__("Draft - Ready"), "orange", "docstatus,=,0"];
            }
            return [__("Draft"), "gray", "docstatus,=,0"];
        }
        else if (doc.docstatus === 1) {
            // Submitted
            if (doc.status === "Completed") {
                return [__("Submitted"), "green", "docstatus,=,1"];
            }
            return [__("Submitted"), "green", "docstatus,=,1"];
        }
        else if (doc.docstatus === 2) {
            // Cancelled
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
    },

    formatters: {
        // Show document status as a separate column indicator
        status: function(value, df, doc) {
            // Add docstatus badge before processing status
            let docstatus_badge = "";
            if (doc.docstatus === 0) {
                docstatus_badge = `<span class="indicator-pill whitespace-nowrap gray">${__("Draft")}</span> `;
            } else if (doc.docstatus === 1) {
                docstatus_badge = `<span class="indicator-pill whitespace-nowrap green">${__("Submitted")}</span> `;
            } else if (doc.docstatus === 2) {
                docstatus_badge = `<span class="indicator-pill whitespace-nowrap red">${__("Cancelled")}</span> `;
            }

            // Processing status
            let status_color = "gray";
            let status_label = value;
            if (value === "Completed") {
                status_color = "green";
                status_label = __("Completed");
            } else if (value === "Error") {
                status_color = "red";
                status_label = __("Error");
            } else if (value === "Not Started") {
                status_color = "gray";
                status_label = __("Not Started");
            }

            return docstatus_badge + `<span class="indicator-pill whitespace-nowrap ${status_color}">${status_label}</span>`;
        }
    }
};
