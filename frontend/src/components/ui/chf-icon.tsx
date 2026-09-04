////// Neoffice — added file (no upstream equivalent): a CHF glyph meant to replace the dollar
////// sign in the transaction list for the Swiss market (58eeb8c). WARNING, DEAD CODE: nothing
////// imports it any more — the v1.5.0 hand-port (89e7929) restored upstream's
////// BankTransactionList and the icon was lost with it. Decide at the merge: re-wire or drop.
import { SVGProps } from "react"

export const ChfIcon = (props: SVGProps<SVGSVGElement>) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {/* C */}
      <path d="M 7 8 Q 5 8 5 10 L 5 14 Q 5 16 7 16" />
      {/* H */}
      <line x1="10" y1="8" x2="10" y2="16" />
      <line x1="14" y1="8" x2="14" y2="16" />
      <line x1="10" y1="12" x2="14" y2="12" />
      {/* F */}
      <line x1="17" y1="8" x2="17" y2="16" />
      <line x1="17" y1="8" x2="20" y2="8" />
      <line x1="17" y1="12" x2="19" y2="12" />
    </svg>
  )
}
