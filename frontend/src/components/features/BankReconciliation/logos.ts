//// Neoffice — added: SWISS_IID_BANK_CODES (the bank of a Swiss IBAN, from SIX's bank master).
import { SWISS_IID_BANK_CODES } from './swissBankCodes'

//// Neoffice — the entry type is ours: upstream inlines `{ keywords, logo }`. `bic` (first four
//// letters of a BIC) finds a Swiss bank by its BIC or IBAN (findBankLogo, at the bottom);
//// `mark` says the file is the bank's symbol alone, shown beside its name, not as a logo.
export interface BankLogo {
    keywords: string[]
    logo: string
    bic?: string[]
    mark?: boolean
}

export const BANK_LOGOS: BankLogo[] = [
    // US + International
    {
        keywords: ['American Express', 'Amex'],
        logo: 'assets/bank-logos/Amex.svg'
    },
    {
        keywords: ['Bank of America', 'BOA'],
        logo: 'assets/bank-logos/Bank_of_America.png'
    },
    {
        keywords: ['Barclays'],
        logo: 'assets/bank-logos/Barclays.svg'
    },
    {
        keywords: ['BNP Paribas'],
        logo: 'assets/bank-logos/BNP_Paribas.svg'
    },
    {
        keywords: ['Bank of New York Mellon', 'BNY Mellon', 'BNY'],
        logo: 'assets/bank-logos/BNY_Mellon.svg'
    },
    {
        keywords: ['Capital One'],
        logo: 'assets/bank-logos/Capital_One.png'
    },
    {
        keywords: ['Charles Schwab', 'Schwab'],
        logo: 'assets/bank-logos/Charles_Schwab_Corporation.png'
    },
    {
        keywords: ['Chase'],
        logo: 'assets/bank-logos/chase.svg'
    },
    {
        keywords: ['Citi', 'Citibank', 'Citi Group', 'Citi Financial Services'],
        logo: 'assets/bank-logos/Citi.svg'
    },
    {
        keywords: ['Deutsche Bank'],
        logo: 'assets/bank-logos/Deutsche_Bank.svg'
    },
    {
        keywords: ['Goldman Sachs'],
        logo: 'assets/bank-logos/Goldman_Sachs.svg'
    },
    {
        keywords: ['HSBC'],
        logo: 'assets/bank-logos/HSBC.svg'
    },
    {
        keywords: ['JPMorgan Chase', 'JPMorgan', 'JP Morgan', 'JP Morgan Chase', 'JPMorgan Chase & Co', 'JPM', 'JPMC'],
        logo: 'assets/bank-logos/jpmc.svg'
    },
    {
        keywords: ['Morgan Stanley'],
        logo: 'assets/bank-logos/Morgan_Stanley.png'
    },
    {
        keywords: ['PNC', 'PNC Financial Services Group', 'PNC Financial Services', 'Pittsburgh National Corporation'],
        logo: 'assets/bank-logos/PNC.png'
    },
    {
        keywords: ['Santander'],
        logo: 'assets/bank-logos/Santander.svg'
    },
    {
        keywords: ['TD Bank', 'Toronto Dominion Bank'],
        logo: 'assets/bank-logos/Toronto_Dominion_Bank.png'
    },
    {
        keywords: ['Truist'],
        logo: 'assets/bank-logos/Truist.svg'
    },
    // Switzerland
    {
        keywords: ['UBS'],
        //// Neoffice — bic added (01.10): a Swiss bank is found by its BIC or IBAN before its name.
        bic: ['UBSW'],
        logo: 'assets/bank-logos/UBS.svg'
    },
    //// Neoffice — added (dd20206, 01.10): the Swiss banks, matched by BIC and by the IID of the
    //// IBAN before their name (findBankLogo). The keywords were too narrow: « Raiffeisen » alone
    //// matched nothing and « BCVS » took the Vaud bank's logo (fleet survey, 01.10). The order
    //// matters: Valais before Vaud, Swiss Raiffeisen before upstream's German Raiffeisenbanken.
    //// Upstream's list has no Swiss bank but UBS. Keep both lists at the merge; the SVG files live
    //// in frontend/public/assets/bank-logos/, each with its source and licence in a comment.
    {
        keywords: ['Credit Suisse', 'Crédit Suisse', 'CS'],
        bic: ['CRES'],
        logo: 'assets/bank-logos/Credit_Suisse.svg'
    },
    {
        keywords: ['PostFinance', 'Post Finance', 'Postfinance'],
        bic: ['POFI'],
        logo: 'assets/bank-logos/PostFinance.svg'
    },
    {
        keywords: ['Raiffeisen'],
        bic: ['RAIF'],
        logo: 'assets/bank-logos/Raiffeisen_Schweiz.svg'
    },
    {
        keywords: ['Zürcher Kantonalbank', 'ZKB', 'Zurcher Kantonalbank', 'Zuercher Kantonalbank'],
        bic: ['ZKBK'],
        logo: 'assets/bank-logos/Zuercher_Kantonalbank.svg'
    },
    {
        keywords: ['Banque Cantonale du Valais', 'Walliser Kantonalbank', 'BCVs', 'BCVS', 'WKB'],
        bic: ['BCVS'],
        logo: 'assets/bank-logos/Banque_Cantonale_du_Valais.svg'
    },
    {
        keywords: ['Banque Cantonale Vaudoise', 'BCV'],
        bic: ['BCVL'],
        logo: 'assets/bank-logos/BCV.svg'
    },
    {
        keywords: ['Cembra', 'Cembra Money Bank'],
        bic: ['CMBN'],
        logo: 'assets/bank-logos/Cembra.svg'
    },
    {
        keywords: ['Aargauische Kantonalbank', 'AKB'],
        bic: ['KBAG'],
        logo: 'assets/bank-logos/Aargauische_Kantonalbank.svg'
    },
    {
        keywords: ['Appenzeller Kantonalbank', 'APPKB'],
        bic: ['AIKA'],
        logo: 'assets/bank-logos/Appenzeller_Kantonalbank.svg'
    },
    {
        keywords: ['Basellandschaftliche Kantonalbank', 'BLKB'],
        bic: ['BLKB'],
        logo: 'assets/bank-logos/Basellandschaftliche_Kantonalbank.svg'
    },
    {
        keywords: ['Basler Kantonalbank', 'BKB'],
        bic: ['BKBB'],
        logo: 'assets/bank-logos/Basler_Kantonalbank.svg'
    },
    {
        keywords: ['Berner Kantonalbank', 'Banque Cantonale Bernoise', 'BEKB', 'BCBE'],
        bic: ['KBBE'],
        logo: 'assets/bank-logos/Berner_Kantonalbank.svg'
    },
    {
        keywords: ['Banque Cantonale de Fribourg', 'Freiburger Kantonalbank', 'BCF', 'FKB'],
        bic: ['BEFR'],
        logo: 'assets/bank-logos/Banque_Cantonale_de_Fribourg.svg'
    },
    {
        keywords: ['Banque Cantonale de Genève', 'Banque Cantonale de Geneve', 'BCGE'],
        bic: ['BCGE'],
        logo: 'assets/bank-logos/Banque_Cantonale_de_Geneve_icon.svg',
        mark: true
    },
    {
        keywords: ['Glarner Kantonalbank', 'GLKB'],
        bic: ['GLKB'],
        logo: 'assets/bank-logos/Glarner_Kantonalbank.svg'
    },
    {
        keywords: ['Graubündner Kantonalbank', 'Graubuendner Kantonalbank', 'GKB'],
        bic: ['GRKB'],
        logo: 'assets/bank-logos/Graubuendner_Kantonalbank.svg'
    },
    {
        keywords: ['Banque Cantonale du Jura', 'BCJ'],
        bic: ['BCJU'],
        logo: 'assets/bank-logos/Banque_Cantonale_du_Jura.svg'
    },
    {
        keywords: ['Luzerner Kantonalbank', 'LUKB'],
        bic: ['LUKB'],
        logo: 'assets/bank-logos/Luzerner_Kantonalbank.svg'
    },
    {
        keywords: ['Banque Cantonale Neuchâteloise', 'Banque Cantonale Neuchateloise', 'BCN'],
        bic: ['BCNN'],
        logo: 'assets/bank-logos/Banque_Cantonale_Neuchateloise.svg'
    },
    {
        keywords: ['Nidwaldner Kantonalbank', 'NKB'],
        bic: ['NIKA'],
        logo: 'assets/bank-logos/Nidwaldner_Kantonalbank.svg'
    },
    {
        keywords: ['Obwaldner Kantonalbank', 'OKB'],
        bic: ['OBWK'],
        logo: 'assets/bank-logos/Obwaldner_Kantonalbank.svg'
    },
    {
        keywords: ['St. Galler Kantonalbank', 'St.Galler Kantonalbank', 'SGKB'],
        bic: ['KBSG'],
        logo: 'assets/bank-logos/St_Galler_Kantonalbank.svg'
    },
    {
        keywords: ['Schaffhauser Kantonalbank', 'SHKB'],
        bic: ['SHKB'],
        logo: 'assets/bank-logos/Schaffhauser_Kantonalbank.svg'
    },
    {
        keywords: ['Schwyzer Kantonalbank', 'SZKB'],
        bic: ['KBSZ'],
        logo: 'assets/bank-logos/Schwyzer_Kantonalbank.svg'
    },
    {
        keywords: ['Thurgauer Kantonalbank', 'TKB'],
        bic: ['KBTG'],
        logo: 'assets/bank-logos/Thurgauer_Kantonalbank.svg'
    },
    {
        keywords: ['BancaStato', 'Banca dello Stato', 'Tessiner Kantonalbank'],
        bic: ['BSCT'],
        logo: 'assets/bank-logos/BancaStato.svg'
    },
    {
        keywords: ['Urner Kantonalbank', 'UKB'],
        bic: ['URKN'],
        logo: 'assets/bank-logos/Urner_Kantonalbank.svg'
    },
    {
        keywords: ['Zuger Kantonalbank', 'Zuger KB'],
        bic: ['KBZG'],
        logo: 'assets/bank-logos/Zuger_Kantonalbank.svg'
    },
    {
        keywords: ['Migros Bank', 'Banque Migros', 'Banca Migros'],
        bic: ['MIGR'],
        logo: 'assets/bank-logos/Migros_Bank.svg'
    },
    {
        keywords: ['Bank Cler', 'Banque Cler', 'Banca Cler'],
        bic: ['BCLR'],
        logo: 'assets/bank-logos/Bank_Cler.svg'
    },
    {
        keywords: ['WIR Bank', 'Banque WIR'],
        bic: ['WIRB'],
        logo: 'assets/bank-logos/WIR_Bank.svg'
    },
    {
        keywords: ['Swissquote'],
        bic: ['SWQB'],
        logo: 'assets/bank-logos/Swissquote.svg'
    },
    {
        keywords: ['Julius Bär', 'Julius Baer'],
        bic: ['BAER'],
        logo: 'assets/bank-logos/Julius_Baer.svg'
    },
    {
        keywords: ['Vontobel'],
        bic: ['VONT'],
        logo: 'assets/bank-logos/Vontobel.svg'
    },
    {
        keywords: ['Lombard Odier'],
        bic: ['LOCY'],
        logo: 'assets/bank-logos/Lombard_Odier.svg'
    },
    {
        keywords: ['EFG Bank', 'EFG International'],
        bic: ['EFGB'],
        logo: 'assets/bank-logos/EFG.svg'
    },
    {
        keywords: ['US Bank', 'USBank', 'U.S. Bank', 'U.S. Bancorp'],
        logo: 'assets/bank-logos/USBank.svg'
    },
    {
        keywords: ['Wells Fargo', 'Wells Fargo'],
        logo: 'assets/bank-logos/Wells_Fargo.svg'
    },
    {
        keywords: ['OakStar', 'Oakstar', 'Oakstar'],
        logo: 'assets/bank-logos/Oakstar.png'
    },
    {
        keywords: ['PlainsCapital', 'Plains Capital'],
        logo: 'assets/bank-logos/PlainsCapitalBank.png'
    },
    {
        keywords: ["Standard Chartered"],
        logo: 'assets/bank-logos/Standard_Chartered.png'
    },
    // India
    {
        keywords: ['HDFC Bank', 'HDFC'],
        logo: 'assets/bank-logos/HDFC.svg'
    },
    {
        keywords: ['ICICI Bank', 'ICICI'],
        logo: 'assets/bank-logos/ICICI.svg'
    },
    {
        keywords: ['SBI', 'State Bank of India'],
        logo: 'assets/bank-logos/State_Bank_of_India.svg'
    },
    {
        keywords: ['Punjab National Bank', 'PNB'],
        logo: 'assets/bank-logos/Punjab_National_Bank.svg'
    },
    {
        keywords: ['Union Bank of India', 'Union Bank'],
        logo: 'assets/bank-logos/Union_Bank_of_India.svg'
    },
    {
        keywords: ['Yes Bank', 'Yes'],
        logo: 'assets/bank-logos/Yes_Bank.svg'
    },
    {
        keywords: ['RBL Bank', 'RBL'],
        logo: 'assets/bank-logos/RBL_Bank.svg'
    },
    {
        keywords: ['Axis Bank', 'Axis'],
        logo: 'assets/bank-logos/Axis_Bank.svg'
    },
    {
        keywords: ['Bank of Baroda', 'BOB'],
        logo: 'assets/bank-logos/Bank_of_Baroda.svg'
    },
    {
        keywords: ['Bank of India', 'BOI'],
        logo: 'assets/bank-logos/Bank_of_India.svg'
    },
    {
        keywords: ['Bank of Maharashtra', 'BOM'],
        logo: 'assets/bank-logos/Bank_of_Maharashtra.svg'
    },
    {
        keywords: ['Kotak Mahindra Bank', 'Kotak'],
        logo: 'assets/bank-logos/Kotak_Mahindra.svg'
    },
    {
        keywords: ['IndusInd Bank', 'IndusInd'],
        logo: 'assets/bank-logos/IndusInd_Bank.svg'
    },
    {
        keywords: ['IDBI Bank', 'IDBI'],
        logo: 'assets/bank-logos/IDBI_Bank.svg'
    },
    {
        keywords: ['IDFC First Bank', 'IDFC First'],
        logo: 'assets/bank-logos/IDFC_First_Bank.svg'
    },
    {
        keywords: ['Federal Bank'],
        logo: 'assets/bank-logos/Federal_Bank.svg'
    },
    {
        keywords: ['Fi Bank'],
        logo: 'assets/bank-logos/Fi_Bank.svg'
    },
    {
        keywords: ['RazorpayX'],
        logo: 'assets/bank-logos/RazorpayX.webp'
    },
    {
        keywords: ['Revolut'],
        logo: 'assets/bank-logos/Revolut.png'
    },
    {
        keywords: ['Starling Bank'],
        logo: 'assets/bank-logos/Starling_Bank.png'
    },
    // Australia and New Zealand
    {
        keywords: ["Commonwealth Bank", "CBA"],
        logo: "assets/bank-logos/Commonwealth_Bank.svg"
    },
    {
        keywords: ["Airwallex"],
        logo: "assets/bank-logos/Airwallex.png"
    },
    {
        keywords: ["Judo Bank"],
        logo: "assets/bank-logos/JudoBank.png"
    },
    {
        keywords: ["Alpha"], // This might conflict with Alpha Bank in Greece
        logo: "assets/bank-logos/AlphaGroupInternational.png"
    },
    {
        keywords: ["Australian Tax Office", "Australian Taxation Office"],
        logo: "assets/bank-logos/Australian_Tax_Office.png"
    },
    {
        keywords: ["Westpac"],
        logo: "assets/bank-logos/Westpac.png"
    },
    {
        keywords: ["ANZ", "ANZ Bank", "Australia and New Zealand Banking Group"],
        logo: "assets/bank-logos/ANZ.png"
    },
    {
        keywords: ["Macquarie Group", "Macquarie Bank"],
        logo: "assets/bank-logos/Macquarie.png"
    },
    // Nicaragua
    {
        keywords: ["Banco Atlantida", "Banco Atlántida"],
        logo: "assets/bank-logos/Banco_Atlantida.png"
    },
    {
        keywords: ["Banco de Finanzas"],
        logo: "assets/bank-logos/Banco_de_Finanzas.svg"
    },
    {
        keywords: ["Avanz"],
        logo: "assets/bank-logos/Avanz.svg"
    },
    {
        keywords: ["Ficohsa"],
        logo: "assets/bank-logos/Ficohsa.svg"
    },
    {
        keywords: ["BAC", "BAC Credomatic"],
        logo: "assets/bank-logos/BAC_Credomatic.svg"
    },
    {
        keywords: ["Banco Lafise"],
        logo: "assets/bank-logos/Banco_Lafise.png"
    },
    // German
    {
        keywords: ["Sparkasse"],
        logo: "assets/bank-logos/Sparkasse.png"
    },
    {
        keywords: ["Volksbank", "Raiffeisenbank", "VR-Bank"],
        logo: "assets/bank-logos/Volksbanken_Raiffeisenbanken.svg"
    },
    // Kenya
    {
        keywords: ["KCB Bank", "KCB"],
        logo: "assets/bank-logos/KCB_Bank_Kenya.png"
    },
    {
        keywords: ["Equity Bank"],
        logo: "assets/bank-logos/Equity_Bank.png"
    },
    {
        keywords: ["I&M"],
        logo: "assets/bank-logos/I&M_Logo.jpg"
    },
    {
        keywords: ["ABSA"],
        logo: "assets/bank-logos/ABSA.png"
    },
    {
        keywords: ["Stanbic"],
        logo: "assets/bank-logos/Stanbic.png"
    },
    {
        keywords: ["DTB", "Diamond Trust Bank"],
        logo: "assets/bank-logos/Diamond_Trust_Bank.jpg"
    },
    {
        keywords: ["Prime Bank"],
        logo: "assets/bank-logos/Prime_Bank.png"
    }
]

//// Neoffice — added (01.10): the logo of a bank account, for every place Mint shows one. A Swiss
//// bank is found by the BIC of its Bank record first, then by the IID of the account's IBAN
//// (swissBankCodes.ts), and only then by its name: the fleet's banks are named « Raiffeisen »,
//// « BCVS », « Banque Cantonal du Valais », « Banque »... A keyword of four letters or fewer is an
//// acronym and matches a whole word only (« BCV » is not in « BCVS », « CS » not in a word).
export const findBankLogo = (bank: { bank?: string | null, bic?: string | null, iban?: string | null }) => {
    for (const code of [bicBankCode(bank.bic), ibanBankCode(bank.iban)]) {
        const byCode = code ? BANK_LOGOS.find((entry) => entry.bic?.includes(code)) : undefined
        if (byCode) return byCode
    }
    const name = (bank.bank ?? '').toLowerCase()
    if (!name) return undefined
    return BANK_LOGOS.find((entry) => entry.keywords.some((keyword) => nameHas(name, keyword.toLowerCase())))
}

const bicBankCode = (bic?: string | null) => {
    const code = (bic ?? '').replace(/\s/g, '').slice(0, 4).toUpperCase()
    return /^[A-Z]{4}$/.test(code) ? code : undefined
}

// The 5th to 9th character of a Swiss or Liechtenstein IBAN name its bank.
const ibanBankCode = (iban?: string | null) => {
    const compact = (iban ?? '').replace(/\s/g, '').toUpperCase()
    if (!/^(CH|LI)\d{7}/.test(compact)) return undefined
    return SWISS_IID_BANK_CODES.get(Number(compact.slice(4, 9)))
}

const nameHas = (name: string, keyword: string) => {
    if (keyword.length > 4) return name.includes(keyword)
    const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}($|[^\\p{L}\\p{N}])`, 'u').test(name)
}
