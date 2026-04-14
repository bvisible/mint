// Inject CSS to prevent Frappe from hiding transactions section
(function() {
    if (!document.getElementById('mint-bsi-style')) {
        var style = document.createElement('style');
        style.id = 'mint-bsi-style';
        style.textContent = '[data-page-container="true"] [data-fieldname="section_break_xml"].empty-section { display: flex !important; }';
        document.head.appendChild(style);
    }
})();

// Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
// For license information, please see license.txt

let bsi_wizard_showing = false;
let bsi_wizard_bypass = false;

frappe.ui.form.on("Mint Bank Statement Import", {
    onload_post_render(frm) {
        if (frm.doc.__islocal && !bsi_wizard_showing && !bsi_wizard_bypass) {
            show_import_wizard(frm);
        }
        if (frm.doc.ocr_status === "Processing" && frm.doc.document_scan_name) {
            start_polling(frm);
        }
    },

    refresh(frm) {
        if (frm._poll_interval) { clearInterval(frm._poll_interval); frm._poll_interval = null; }
        if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) { neoffice.processing_overlay.hide(); }

        render_file_info(frm);

        if (frm.doc.file && frm.doc.docstatus === 0 && !frm.is_new()) {
            detect_file_type(frm);
        } else {
            toggle_file_type_fields(frm);
        }

        if (frm.doc.import_summary && frm.doc.docstatus === 1) {
            frm.dashboard.set_headline(frm.doc.import_summary, "green");
        }

        if (frm.doc.docstatus === 0 && frm.doc.file && !frm.is_new()) {
            // XML
            if (frm.doc.file_type === "XML") {
                if (frm.doc.transactions && frm.doc.transactions.length > 0) {
                    frm.add_custom_button(__("Reprocess File"), () => start_xml_parsing(frm));
                }
            }
            // PDF
            if (frm.doc.file_type === "PDF") {
                if (frm._ocr_just_completed) { frm._ocr_just_completed = false; }
                else if (frm.doc.ocr_status === "Processing") {
                    frm.dashboard.set_headline(__("Analysis in progress..."), "blue");
                    start_polling(frm);
                }
                if (frm.doc.document_scan_name) {
                    frm.add_custom_button(__("View Document Scan"), () => frappe.set_route("Form", "Document Scan", frm.doc.document_scan_name));
                }
                if (!frm.doc.ocr_status && (!frm.doc.transactions || frm.doc.transactions.length === 0)) {
                    frm.add_custom_button(__("Analyze with Nora AI"), () => start_ocr_processing(frm)).addClass("btn-primary");
                }
                if (frm.doc.ocr_status === "Failed") {
                    frm.add_custom_button(__("Retry Analysis"), () => {
                        frm.set_value("ocr_status", ""); frm.set_value("document_scan_name", ""); frm.set_value("error", "");
                        frm.save().then(() => start_ocr_processing(frm));
                    }).addClass("btn-primary");
                }
            }
        }




    },

    file(frm) {
        if (frm.doc.file) { detect_file_type(frm); render_file_info(frm); }
    },
    file_type(frm) { toggle_file_type_fields(frm); },
    before_unload(frm) {
        if (frm._poll_interval) { clearInterval(frm._poll_interval); frm._poll_interval = null; }
        if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) { neoffice.processing_overlay.hide(); }
    }
});

// =============================================
// IMPORT WIZARD
// =============================================

function show_import_wizard(frm) {
    if (bsi_wizard_showing) return;
    bsi_wizard_showing = true;

    let wizard_file = null;  // Stored file object

    const wizard = new frappe.ui.Dialog({
        title: __("Import Bank Statement"),
        size: "large",
        fields: [{ fieldtype: "HTML", fieldname: "wizard_html" }],
        primary_action_label: __("Process"),
        primary_action: () => {
            // Validate
            const bank_account = bankAccountControl?.get_value();
            if (!bank_account) {
                frappe.show_alert({ message: __("Please select a bank account"), indicator: "orange" });
                return;
            }
            if (!wizard_file) {
                frappe.show_alert({ message: __("Please attach a file"), indicator: "orange" });
                return;
            }
            // All good — process
            frm.set_value('bank_account', bank_account);
            wizard.hide();
            bsi_wizard_showing = false;
            bsi_wizard_bypass = true;
            handle_wizard_file(frm, wizard_file);
        }
    });

    // Disable primary button initially
    wizard.get_primary_btn().prop('disabled', true);

    wizard.fields_dict.wizard_html.$wrapper.html(`
        <div style="padding: 20px;">
            <!-- Bank Account -->
            <div style="margin-bottom: 20px;">
                <label style="font-size: 13px; font-weight: 600; color: var(--text-color); margin-bottom: 6px; display: block;">
                    ${__("Bank Account")} <span class="text-danger">*</span>
                </label>
                <div id="mint-wizard-bank-account"></div>
            </div>

            <!-- Drop Zone -->
            <div class="mint-wizard-drop" id="mint-wizard-drop" style="
                border: 2px dashed var(--border-color);
                border-radius: 12px;
                padding: 45px 40px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s ease;
                background: var(--fg-color);
                margin-bottom: 20px;
            ">
                <svg viewBox="0 0 24 24" fill="currentColor" width="48" height="48" style="color: var(--primary); margin-bottom: 12px;">
                    <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
                </svg>
                <div style="font-size: 16px; font-weight: 600; color: var(--text-color); margin-bottom: 8px;">
                    ${__("Drag and drop your bank file here")}
                </div>
                <div style="font-size: 13px; color: var(--text-muted);">
                    ${__("or click to browse")}
                </div>
            </div>

            <!-- File selected display (hidden initially) -->
            <div id="mint-wizard-file-info" style="display: none; margin-bottom: 20px; padding: 12px 18px; background: var(--control-bg); border-radius: 10px;">
            </div>

            <input type="file" id="mint-wizard-file-input" accept=".pdf,.xml,.camt,.camt053" style="display: none;" />

            <!-- Explanation -->
            <div style="display: flex; gap: 15px;">
                <div style="flex: 1; padding: 15px; border-radius: 10px; background: var(--control-bg); border: 1px solid var(--border-color);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 22px;">📄</span>
                        <span style="font-weight: 600; font-size: 14px;">${__("XML file")}</span>
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.6;">
                        ${__("CAMT 053/054 file downloaded from your bank portal. Transactions are extracted automatically with bank references, amounts and party details.")}
                    </div>
                </div>
                <div style="flex: 1; padding: 15px; border-radius: 10px; background: var(--control-bg); border: 1px solid var(--border-color);">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 22px;">📑</span>
                        <span style="font-weight: 600; font-size: 14px;">${__("PDF bank statement")}</span>
                    </div>
                    <div style="font-size: 12px; color: var(--text-muted); line-height: 1.6;">
                        ${__("Scanned or downloaded bank statement. Nora AI analyzes the document and extracts transactions using artificial intelligence (OCR).")}
                    </div>
                </div>
            </div>
        </div>
    `);

    // Bank account Link field
    const bankAccountControl = frappe.ui.form.make_control({
        df: {
            fieldtype: 'Link',
            fieldname: 'bank_account',
            options: 'Bank Account',
            placeholder: __('Select a bank account'),
            get_query: () => ({ filters: { is_company_account: 1 } }),
            change: () => check_wizard_ready()
        },
        parent: wizard.$wrapper.find('#mint-wizard-bank-account'),
        render_input: true
    });

    if (frm.doc.bank_account) {
        bankAccountControl.set_value(frm.doc.bank_account);
    }

    function check_wizard_ready() {
        const has_bank = !!bankAccountControl?.get_value();
        const has_file = !!wizard_file;
        wizard.get_primary_btn().prop('disabled', !(has_bank && has_file));
    }

    function show_file_selected(file) {
        const isXml = file.name.toLowerCase().match(/\.(xml|camt|camt053)$/);
        const icon = isXml ? '📄' : '📑';
        const typeLabel = isXml ? __('XML file — automatic processing') : __('PDF — analyzed by Nora AI');
        const fileSize = (file.size / 1024).toFixed(1);

        wizard.$wrapper.find('#mint-wizard-drop').hide();
        wizard.$wrapper.find('#mint-wizard-file-info').show().html(`
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 28px;">${icon}</span>
                    <div>
                        <div style="font-weight: 600; font-size: 14px;">${file.name}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${typeLabel} — ${fileSize} KB</div>
                    </div>
                </div>
                <button class="btn btn-sm btn-default" id="mint-wizard-change-file">${__("Change")}</button>
            </div>
        `);

        wizard.$wrapper.find('#mint-wizard-change-file').on('click', () => {
            wizard_file = null;
            wizard.$wrapper.find('#mint-wizard-drop').show();
            wizard.$wrapper.find('#mint-wizard-file-info').hide();
            check_wizard_ready();
        });
    }

    // Drop zone interactions
    const dropZone = wizard.$wrapper.find('#mint-wizard-drop');
    const fileInput = wizard.$wrapper.find('#mint-wizard-file-input');

    dropZone.on('click', () => fileInput.trigger('click'));

    fileInput.on('change', function() {
        if (this.files.length > 0) {
            wizard_file = this.files[0];
            show_file_selected(wizard_file);
            check_wizard_ready();
        }
    });

    dropZone.on('dragover', (e) => {
        e.preventDefault(); e.stopPropagation();
        dropZone.css({ 'border-color': 'var(--primary)', 'background': 'var(--control-bg)' });
    });
    dropZone.on('dragleave', (e) => {
        e.preventDefault(); e.stopPropagation();
        dropZone.css({ 'border-color': 'var(--border-color)', 'background': 'var(--fg-color)' });
    });
    dropZone.on('drop', (e) => {
        e.preventDefault(); e.stopPropagation();
        dropZone.css({ 'border-color': 'var(--border-color)', 'background': 'var(--fg-color)' });
        if (e.originalEvent.dataTransfer.files.length > 0) {
            wizard_file = e.originalEvent.dataTransfer.files[0];
            show_file_selected(wizard_file);
            check_wizard_ready();
        }
    });

    // Close → back to list
    wizard.$wrapper.find('.btn-modal-close').on('click', () => {
        bsi_wizard_showing = false;
        if (frm.is_new()) frappe.set_route("List", "Mint Bank Statement Import");
    });

    wizard.show();
    wizard.$wrapper.find('.modal-dialog').css('max-width', '700px');
}

// =============================================
// FILE HANDLING
// =============================================

function handle_wizard_file(frm, file) {
    const wrapper = frm.fields_dict.upload_area?.$wrapper;
    if (wrapper) {
        wrapper.html(`
            <div style="padding: 30px; text-align: center; background: var(--control-bg); border-radius: 12px;">
                <div class="spinner-border text-primary" role="status" style="width: 2rem; height: 2rem;"></div>
                <div style="margin-top: 10px; font-size: 14px; color: var(--text-muted);">${__("Uploading")} ${file.name}...</div>
            </div>
        `);
    }

    if (frm.is_new()) {
        frm.save().then(() => upload_and_process(frm, file));
    } else {
        upload_and_process(frm, file);
    }
}

function upload_and_process(frm, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doctype', frm.doctype);
    formData.append('docname', frm.doc.name);
    formData.append('is_private', 1);

    fetch('/api/method/upload_file', {
        method: 'POST',
        body: formData,
        headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token }
    })
    .then(r => r.json())
    .then(data => {
        if (data.message && data.message.file_url) {
            frm.set_value('file', data.message.file_url);
            frm.dirty();
            frm.save().then(() => {
                // After save, detect type and start processing
                detect_file_type(frm);
                // Small delay to let file_type be set
                setTimeout(() => {
                    if (frm.doc.file_type === "XML") {
                        start_xml_parsing(frm);
                    } else if (frm.doc.file_type === "PDF") {
                        start_ocr_processing(frm);
                    }
                }, 500);
            });
        }
    })
    .catch(() => {
        frappe.show_alert({ message: __("Failed to upload file"), indicator: "red" });
        render_file_info(frm);
    });
}

// =============================================
// FILE INFO (in form)
// =============================================

function render_file_info(frm) {
    const wrapper = frm.fields_dict.upload_area?.$wrapper;
    if (!wrapper) return;

    frm.fields_dict.section_break_upload?.$wrapper?.find('.section-head')?.hide();

    if (frm.doc.file) {
        const fname = frm.doc.file.split('/').pop();
        const typeLabel = frm.doc.file_type === 'XML' ? __('XML file — automatic processing') : __('PDF — analyzed by Nora AI');
        const icon = frm.doc.file_type === 'XML' ? '📄' : '📑';

        wrapper.html(`
            <div style="padding: 12px 18px; background: var(--control-bg); border-radius: 10px; display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 24px;">${icon}</span>
                    <div>
                        <div style="font-weight: 600; font-size: 13px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${fname}">${fname}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">${typeLabel}</div>
                    </div>
                </div>
                ${frm.doc.docstatus === 0 ? `<button class="btn btn-sm btn-default mint-change-file">${__("Change")}</button>` : ''}
            </div>
        `);
        wrapper.find('.mint-change-file').on('click', () => show_import_wizard(frm));
    } else if (frm.doc.docstatus === 0) {
        wrapper.html(`
            <div style="padding: 20px; text-align: center; border: 1px dashed var(--border-color); border-radius: 10px; cursor: pointer;" onclick="show_import_wizard(cur_frm)">
                <span style="color: var(--text-muted); font-size: 13px;">${__("Click here to import a bank file")}</span>
            </div>
        `);
    } else {
        wrapper.html('');
    }
}

// =============================================
// OCR (PDF)
// =============================================

function start_ocr_processing(frm, force_create = false) {
    frappe.show_alert({ message: __("Starting analysis..."), indicator: "blue" });
    frappe.call({
        method: "mint.apis.nora_ocr.start_ocr_processing",
        args: { docname: frm.doc.name, force_create: force_create },
        freeze: false,
        callback: function(r) {
            if (r.message?.status === "Processing") { frm.reload_doc().then(() => start_polling(frm)); }
            else if (r.message?.status === "Duplicate") {
                frappe.confirm(__("A Document Scan with the same file already exists: {0}. Process anyway?", [r.message.existing_name]),
                    () => start_ocr_processing(frm, true),
                    () => frappe.set_route("Form", "Document Scan", r.message.existing_name));
            }
            else if (r.message?.status === "Error") { frappe.msgprint({ title: __("Error"), message: r.message.error, indicator: "red" }); }
        },
        error: () => frappe.show_alert({ message: __("Failed to start analysis"), indicator: "red" })
    });
}

function start_polling(frm) {
    if (frm._poll_interval) return;
    show_processing_freeze(frm);
    let n = 0;
    frm._poll_interval = setInterval(() => {
        if (++n > 180) { stop_polling(frm); frm.dashboard.set_headline(__("Timeout — check Document Scan"), "orange"); return; }
        frappe.call({
            method: "mint.apis.nora_ocr.check_ocr_processing_status", args: { docname: frm.doc.name },
            callback: function(r) {
                if (!r.message) return;
                if (r.message.status === "Completed") {
                    frm._ocr_just_completed = true; stop_polling(frm);
                    frappe.show_alert({ message: __("{0} transactions found", [r.message.count || 0]), indicator: "green" });
                    frm.reload_doc();
                } else if (r.message.status === "Failed") {
                    frm._ocr_just_completed = true; stop_polling(frm);
                    frappe.msgprint({ title: __("Analysis Failed"), message: r.message.error, indicator: "red" });
                    frm.reload_doc();
                }
            }
        });
    }, 2000);
}

function stop_polling(frm) {
    if (frm._poll_interval) { clearInterval(frm._poll_interval); frm._poll_interval = null; }
    if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) { neoffice.processing_overlay.hide(); }
}

function show_processing_freeze(frm) {
    if (typeof neoffice !== 'undefined' && neoffice.processing_overlay) {
        neoffice.processing_overlay.show({
            message: __("Nora AI analysis in progress..."),
            button_label: __("Continue in background"),
            on_background: () => {
                frm.dashboard.set_headline(__("Analysis in progress..."), "blue");
                frappe.show_alert({ message: __("Processing continues in background. Page will reload when done."), indicator: "blue" });
            }
        });
    } else { frm.dashboard.set_headline(__("Analysis in progress..."), "blue"); }
}

// =============================================
// XML
// =============================================

function start_xml_parsing(frm) {
    frappe.show_alert({ message: __("Processing file..."), indicator: "blue" });
    frappe.call({
        method: "mint.mint.doctype.mint_bank_statement_import.mint_bank_statement_import.parse_xml_content",
        args: { docname: frm.doc.name },
        freeze: true,
        freeze_message: __("Processing bank file..."),
        callback: function(r) {
            if (r.message?.success) {
                let msg = __("{0} transactions found", [r.message.transaction_count]);
                let indicator = "green";
                if (r.message.duplicate_count > 0) {
                    msg += " — " + __("{0} new, {1} already imported", [r.message.new_count, r.message.duplicate_count]);
                    indicator = "blue";
                }
                frappe.show_alert({ message: msg, indicator: indicator });
                frm.reload_doc();
            }
        },
        error: () => { frappe.show_alert({ message: __("Failed to process file"), indicator: "red" }); frm.reload_doc(); }
    });
}

// =============================================
// FILE TYPE DETECTION
// =============================================

function detect_file_type(frm) {
    const url = frm.doc.file;
    const u = url.toLowerCase();
    if (u.endsWith('.xml') || u.endsWith('.camt') || u.endsWith('.camt053')) { frm.set_value('file_type', 'XML'); toggle_file_type_fields(frm); return; }
    if (u.endsWith('.pdf')) { frm.set_value('file_type', 'PDF'); toggle_file_type_fields(frm); return; }

    frappe.call({
        method: "frappe.client.get_value",
        args: { doctype: "File", filters: { file_url: url }, fieldname: "file_name" },
        async: false,
        callback: function(r) {
            if (r.message?.file_name) {
                const f = r.message.file_name.toLowerCase();
                frm.set_value('file_type', (f.endsWith('.xml') || f.endsWith('.camt') || f.endsWith('.camt053')) ? 'XML' : 'PDF');
            } else { frm.set_value('file_type', 'PDF'); }
            toggle_file_type_fields(frm);
        }
    });
}

function toggle_file_type_fields(frm) {
    const is_xml = frm.doc.file_type === "XML";
    const is_pdf = frm.doc.file_type === "PDF";
    const has_file = !!frm.doc.file;

    frm.toggle_display("section_break_ocr", is_pdf && has_file);
    frm.toggle_display("section_break_xml", is_xml && has_file);
    frm.toggle_reqd("bank_account", is_pdf);
    frm.toggle_display("section_break_sttk", has_file);

    // Force show transactions section (Frappe hides it with empty-section class)
    if (has_file) {
        const txn_section = frm.fields_dict.section_break_txn?.$wrapper;
        if (txn_section) {
            txn_section.removeClass("empty-section");
            txn_section.show();
        }
    }
}

window.show_import_wizard = show_import_wizard;
