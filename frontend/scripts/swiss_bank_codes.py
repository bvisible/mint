# //// Neoffice — added file (no upstream equivalent): writes swissBankCodes.ts from SIX's bank master.
"""Write swissBankCodes.ts: the bank of every Swiss and Liechtenstein IID, from SIX's bank master.

The IID - the 5th to 9th character of a CH or LI IBAN - names the bank of an account. Mint keys
the Swiss bank logos on the first four letters of the bank's BIC (logos.ts), so an account whose
Bank record has no BIC, or was named by hand ("Banque", "BCVS"), still shows its bank's logo.
QR-IIDs (30000-31999) are listed too: a QR-IBAN names its bank the same way.

    python3 frontend/scripts/swiss_bank_codes.py             # from SIX's public API
    python3 frontend/scripts/swiss_bank_codes.py saved.json  # from a saved copy of it

Run it again when SIX publishes new IIDs (a bank opens, merges, or changes its BIC).
"""

import collections
import json
import pathlib
import sys
import urllib.request

URL = "https://api.six-group.com/api/epcd/bankmaster/v3/bankmaster.json"
OUT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src/components/features/BankReconciliation/swissBankCodes.ts"
)
# An IID listed twice keeps the code of its head office first, then of a main branch.
RANK = {"HEADQUARTERS": 0, "MAIN_BRANCH": 1, "QR_IID": 2}


def load():
    if len(sys.argv) > 1:
        return json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    request = urllib.request.Request(URL, headers={"User-Agent": "mint-swiss-bank-codes"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    data = load()
    entries = sorted(data["entries"], key=lambda e: RANK.get(e.get("iidType"), 3))
    code_of = {}
    for entry in entries:
        bic, iid = (entry.get("bic") or "").strip().upper(), entry.get("iid")
        if len(bic) >= 4 and iid is not None:
            code_of.setdefault(int(iid), bic[:4])
    by_code = collections.defaultdict(list)
    for iid, code in sorted(code_of.items()):
        by_code[code].append(iid)
    rows = "\n".join(
        f"\t{code}: [{', '.join(str(iid) for iid in iids)}]," for code, iids in sorted(by_code.items())
    )
    OUT.write_text(
        "//// Neoffice — added file (no upstream equivalent), written by frontend/scripts/swiss_bank_codes.py:\n"
        f"//// do not edit by hand. SIX bank master valid on {data.get('validOn')}, {len(code_of)} IIDs.\n"
        "//// For each bank, the first four letters of its BIC and the IIDs (5th to 9th character of a CH or\n"
        "//// LI IBAN) that name it, QR-IIDs included: logos.ts finds a Swiss bank by its IBAN with it.\n"
        "const IIDS_BY_CODE: Record<string, number[]> = {\n"
        f"{rows}\n"
        "}\n\n"
        "export const SWISS_IID_BANK_CODES: Map<number, string> = new Map(\n"
        "\tObject.entries(IIDS_BY_CODE).flatMap(([code, iids]) => iids.map((iid): [number, string] => [iid, code]))\n"
        ")\n",
        encoding="utf-8",
    )
    print(f"{OUT.name}: {len(code_of)} IIDs, {len(by_code)} banks")


if __name__ == "__main__":
    main()
