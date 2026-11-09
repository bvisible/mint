# //// Neoffice — added file (no upstream equivalent): a statement file that cannot be read (#1490).
"""
A statement file that cannot be read says so in one sentence, and says nothing of the server.

On an empty file the import screen showed the error of the reader as it came, which quoted a folder of the server with
the e-mail address of the user that owns it. ``get_data`` now turns what the readers raise into « The file could not be
read » (the original goes to the Error Log with its traceback), says « The file is empty » for a file with no cell, and
leaves a refusal of permission alone. None of this needs a site: ``get_data`` is run against a stand-in for frappe.

Run with:
    python -m pytest mint/apis/test_statement_import_unreadable_file.py -v
or, on a bench:
    bench --site prodclone.local run-tests --app mint --module mint.apis.test_statement_import_unreadable_file
"""

import contextlib
import traceback
import unittest
import zipfile
from unittest import mock

import frappe as real_frappe

from mint.apis import statement_import

# a private folder is named after the user that owns it, e-mail address included
FILE_URL = "/private/files/Jane Roe (jane.roe@example.com)/Statements/october.csv"


def _identity(text, *args, **kwargs):
    return text


class _Case(unittest.TestCase):
    def setUp(self):
        self.file_doc = mock.MagicMock()
        self.file_doc.get_extension.return_value = ("october", ".csv")
        self.file_doc.get_content.return_value = b"Date,Amount\n2026-10-01,12.50\n"

        self.frappe = mock.MagicMock()
        # the classes the code catches must be real classes, and a throw must really raise
        self.frappe.PermissionError = real_frappe.PermissionError
        self.frappe.DoesNotExistError = real_frappe.DoesNotExistError
        self.frappe.throw.side_effect = self._throw
        self.frappe.get_traceback.side_effect = traceback.format_exc
        self.frappe.get_doc.return_value = self.file_doc

        for patcher in (
            mock.patch.object(statement_import, "frappe", self.frappe),
            mock.patch.object(statement_import, "_", side_effect=_identity),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _throw(message, title=None, **kwargs):
        raise real_frappe.ValidationError(message)

    def read(self, **readers):
        """get_data on FILE_URL, the readers named in `readers` replaced (read_csv_content=..., ...)."""
        with contextlib.ExitStack() as stack:
            for name, reader in readers.items():
                stack.enter_context(mock.patch.object(statement_import, name, reader))
            return statement_import.get_data(FILE_URL)

    def assert_could_not_be_read(self, raised):
        message = str(raised.exception)
        self.assertEqual(message, "The file could not be read")
        # nothing of the server, and no one's address, reaches the person who uploaded the file
        self.assertNotIn("/", message)
        self.assertNotIn("@", message)
        # the original error is kept where staff reads it: a short title first, the traceback in the message
        self.frappe.log_error.assert_called_once()
        title, details = self.frappe.log_error.call_args.args
        self.assertLessEqual(len(title), 140)
        self.assertIn(FILE_URL, details)
        return details


class TestAnUnreadableStatementFile(_Case):
    def test_a_file_the_disk_refuses_is_a_clear_sentence_and_the_original_is_logged(self):
        self.file_doc.get_content.side_effect = FileNotFoundError(
            f"[Errno 2] No such file or directory: '/home/app/sites/site/{FILE_URL.lstrip('/')}'"
        )
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read()
        details = self.assert_could_not_be_read(raised)
        self.assertIn("jane.roe@example.com", details)  # kept in the log, never on the screen

    def test_a_workbook_the_reader_refuses_is_a_clear_sentence(self):
        self.file_doc.get_extension.return_value = ("october", ".xlsx")
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read(read_xlsx_file_from_attached_file=mock.Mock(side_effect=zipfile.BadZipFile("File is not a zip file")))
        self.assert_could_not_be_read(raised)

    def test_a_csv_the_reader_refuses_is_a_clear_sentence(self):
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read(read_csv_content=mock.Mock(side_effect=UnicodeError(f"cannot decode {FILE_URL}")))
        self.assert_could_not_be_read(raised)

    def test_a_file_record_that_does_not_exist_is_a_clear_sentence(self):
        self.frappe.get_doc.side_effect = real_frappe.DoesNotExistError(f"File {{'file_url': '{FILE_URL}'}} not found")
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read()
        self.assert_could_not_be_read(raised)

    def test_a_refusal_of_permission_is_not_turned_into_a_read_error(self):
        self.file_doc.check_permission.side_effect = real_frappe.PermissionError("No permission for File")
        with self.assertRaises(real_frappe.PermissionError):
            self.read()
        self.frappe.log_error.assert_not_called()

    def test_a_permission_error_of_the_reader_is_not_turned_into_a_read_error(self):
        self.file_doc.get_content.side_effect = real_frappe.PermissionError("No permission")
        with self.assertRaises(real_frappe.PermissionError):
            self.read()
        self.frappe.log_error.assert_not_called()


class TestAnEmptyStatementFile(_Case):
    def test_a_file_with_no_row_is_said_to_be_empty(self):
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read(read_csv_content=mock.Mock(return_value=[]))
        self.assertEqual(str(raised.exception), "The file is empty")
        self.frappe.log_error.assert_not_called()

    def test_a_file_whose_cells_are_all_blank_is_said_to_be_empty(self):
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read(read_csv_content=mock.Mock(return_value=[[None, ""], [], ["", None]]))
        self.assertEqual(str(raised.exception), "The file is empty")

    def test_a_file_with_a_zero_is_not_empty(self):
        rows = [["Date", "Amount"], ["2026-10-01", 0]]
        self.assertEqual(self.read(read_csv_content=mock.Mock(return_value=rows)), rows)


class TestAReadableStatementFile(_Case):
    def test_the_rows_come_back_as_before(self):
        rows = [["Date", "Amount"], ["2026-10-01", "12.50"]]
        for extension, reader in (
            (".csv", "read_csv_content"),
            (".xlsx", "read_xlsx_file_from_attached_file"),
            (".xls", "read_xls_file_from_attached_file"),
        ):
            with self.subTest(extension=extension):
                self.file_doc.get_extension.return_value = ("october", extension.upper())
                self.assertEqual(self.read(**{reader: mock.Mock(return_value=rows)}), rows)
        self.frappe.log_error.assert_not_called()
        self.frappe.throw.assert_not_called()

    def test_a_file_of_another_type_is_refused_as_before(self):
        self.file_doc.get_extension.return_value = ("october", ".pdf")
        with self.assertRaises(real_frappe.ValidationError) as raised:
            self.read()
        self.assertEqual(str(raised.exception), "Import template should be of type .csv, .xlsx or .xls")
        self.frappe.log_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
