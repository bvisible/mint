# //// Neoffice — added file (no upstream equivalent): no request for transactions without a bank account.
"""The bank reconciliation asks for transactions only once a bank account is chosen (neoffice-maintenance#2973).

`get_bank_transactions` requires its account. The page asked for the unreconciled transactions whatever was chosen: the
server answered a 500 each time the page opened before the account was known, and all along on a company without a bank
account (every new Neoffice Go). This reads the hooks of the page: each call of that method must have a key that is null
without an account (SWR then makes no request). It fails where a merge of upstream brings the old key back.
"""

import os
import re
import unittest

import mint

UTILS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(mint.__file__))),
    "frontend/src/components/features/BankReconciliation/utils.ts",
)
METHOD = "mint.apis.transactions.get_bank_transactions"


def _calls(source):
    """The text of each hook that calls METHOD, from its name to the end of its arrow function."""
    hooks = re.findall(r"export const \w+ = \([^)]*\) => \{\n.*?\n\}\n", source, re.S)
    return [hook for hook in hooks if METHOD in hook]


class TestNoBankAccountNoCall(unittest.TestCase):
    def test_every_call_waits_for_the_account(self):
        with open(UTILS, encoding="utf-8") as handle:
            calls = _calls(handle.read())
        self.assertEqual(len(calls), 2, "the hooks that ask for the transactions of an account")
        for call in calls:
            name = re.match(r"export const (\w+)", call).group(1)
            self.assertRegex(call, r"\}, bankAccount \? `[^`]+` : null", name)


PICKER = UTILS.replace("utils.ts", "BankPicker.tsx")


class TestTheAccountFollowsTheCompany(unittest.TestCase):
    """The company changed on the page: the account of the one left stayed on screen, its transactions under the other's
    name, when the new one had none. The list of the company decides, whether it was asked again or came from the cache."""

    def test_the_account_is_chosen_from_the_list_on_screen_and_dropped_when_it_has_none(self):
        with open(PICKER, encoding="utf-8") as handle:
            source = handle.read()
        picker = source[source.index("const BankPicker = ") : source.index("export default BankPicker")]
        self.assertIn("useGetBankAccounts()", picker, "an onSuccess is not called for a list in the cache")
        effect = re.search(r"useEffect\(\(\) => \{(.*?)\}, \[banks, isLoading, setSelectedBank\]\)", picker, re.S)
        self.assertTrue(effect, "the effect on the list of the company")
        self.assertIn("banks.some((bank) => bank.name === current.name)", effect.group(1))
        self.assertIn("?? null", effect.group(1), "no account of this company: none is chosen")
