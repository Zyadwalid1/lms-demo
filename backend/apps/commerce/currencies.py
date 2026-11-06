"""ISO 4217 reference list (active currencies), loaded by migration 0003.
Admins can edit everything afterwards (activate, rate source, Stripe support)."""

# code: name
ISO_4217 = {
    "AED": "UAE Dirham", "AFN": "Afghani", "ALL": "Lek", "AMD": "Armenian Dram", "ANG": "Netherlands Antillean Guilder",
    "AOA": "Kwanza", "ARS": "Argentine Peso", "AUD": "Australian Dollar", "AWG": "Aruban Florin",
    "AZN": "Azerbaijan Manat", "BAM": "Convertible Mark", "BBD": "Barbados Dollar", "BDT": "Taka",
    "BGN": "Bulgarian Lev", "BHD": "Bahraini Dinar", "BIF": "Burundi Franc", "BMD": "Bermudian Dollar",
    "BND": "Brunei Dollar", "BOB": "Boliviano", "BRL": "Brazilian Real", "BSD": "Bahamian Dollar",
    "BTN": "Ngultrum", "BWP": "Pula", "BYN": "Belarusian Ruble", "BZD": "Belize Dollar", "CAD": "Canadian Dollar",
    "CDF": "Congolese Franc", "CHF": "Swiss Franc", "CLP": "Chilean Peso", "CNY": "Yuan Renminbi",
    "COP": "Colombian Peso", "CRC": "Costa Rican Colon", "CUP": "Cuban Peso", "CVE": "Cabo Verde Escudo",
    "CZK": "Czech Koruna", "DJF": "Djibouti Franc", "DKK": "Danish Krone", "DOP": "Dominican Peso",
    "DZD": "Algerian Dinar", "EGP": "Egyptian Pound", "ERN": "Nakfa", "ETB": "Ethiopian Birr", "EUR": "Euro",
    "FJD": "Fiji Dollar", "FKP": "Falkland Islands Pound", "GBP": "Pound Sterling", "GEL": "Lari",
    "GHS": "Ghana Cedi", "GIP": "Gibraltar Pound", "GMD": "Dalasi", "GNF": "Guinean Franc", "GTQ": "Quetzal",
    "GYD": "Guyana Dollar", "HKD": "Hong Kong Dollar", "HNL": "Lempira", "HTG": "Gourde", "HUF": "Forint",
    "IDR": "Rupiah", "ILS": "New Israeli Sheqel", "INR": "Indian Rupee", "IQD": "Iraqi Dinar", "IRR": "Iranian Rial",
    "ISK": "Iceland Krona", "JMD": "Jamaican Dollar", "JOD": "Jordanian Dinar", "JPY": "Yen", "KES": "Kenyan Shilling",
    "KGS": "Som", "KHR": "Riel", "KMF": "Comorian Franc", "KPW": "North Korean Won", "KRW": "Won",
    "KWD": "Kuwaiti Dinar", "KYD": "Cayman Islands Dollar", "KZT": "Tenge", "LAK": "Lao Kip", "LBP": "Lebanese Pound",
    "LKR": "Sri Lanka Rupee", "LRD": "Liberian Dollar", "LSL": "Loti", "LYD": "Libyan Dinar", "MAD": "Moroccan Dirham",
    "MDL": "Moldovan Leu", "MGA": "Malagasy Ariary", "MKD": "Denar", "MMK": "Kyat", "MNT": "Tugrik", "MOP": "Pataca",
    "MRU": "Ouguiya", "MUR": "Mauritius Rupee", "MVR": "Rufiyaa", "MWK": "Malawi Kwacha", "MXN": "Mexican Peso",
    "MYR": "Malaysian Ringgit", "MZN": "Mozambique Metical", "NAD": "Namibia Dollar", "NGN": "Naira",
    "NIO": "Cordoba Oro", "NOK": "Norwegian Krone", "NPR": "Nepalese Rupee", "NZD": "New Zealand Dollar",
    "OMR": "Rial Omani", "PAB": "Balboa", "PEN": "Sol", "PGK": "Kina", "PHP": "Philippine Peso", "PKR": "Pakistan Rupee",
    "PLN": "Zloty", "PYG": "Guarani", "QAR": "Qatari Rial", "RON": "Romanian Leu", "RSD": "Serbian Dinar",
    "RUB": "Russian Ruble", "RWF": "Rwanda Franc", "SAR": "Saudi Riyal", "SBD": "Solomon Islands Dollar",
    "SCR": "Seychelles Rupee", "SDG": "Sudanese Pound", "SEK": "Swedish Krona", "SGD": "Singapore Dollar",
    "SHP": "Saint Helena Pound", "SLE": "Leone", "SOS": "Somali Shilling", "SRD": "Surinam Dollar",
    "SSP": "South Sudanese Pound", "STN": "Dobra", "SYP": "Syrian Pound", "SZL": "Lilangeni", "THB": "Baht",
    "TJS": "Somoni", "TMT": "Turkmenistan Manat", "TND": "Tunisian Dinar", "TOP": "Pa'anga", "TRY": "Turkish Lira",
    "TTD": "Trinidad and Tobago Dollar", "TWD": "New Taiwan Dollar", "TZS": "Tanzanian Shilling",
    "UAH": "Hryvnia", "UGX": "Uganda Shilling", "USD": "US Dollar", "UYU": "Peso Uruguayo", "UZS": "Uzbekistan Sum",
    "VES": "Bolivar Soberano", "VND": "Dong", "VUV": "Vatu", "WST": "Tala", "XAF": "CFA Franc BEAC",
    "XCD": "East Caribbean Dollar", "XOF": "CFA Franc BCEAO", "XPF": "CFP Franc", "YER": "Yemeni Rial",
    "ZAR": "Rand", "ZMW": "Zambian Kwacha", "ZWG": "Zimbabwe Gold",
}  # fmt: skip

ZERO_DECIMAL = {"BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "VND", "VUV",
                "XAF", "XOF", "XPF"}  # fmt: skip
THREE_DECIMAL = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
# Not payable through Stripe (sanctions or no support). Admin-editable.
STRIPE_UNSUPPORTED = {
    "BYN",
    "CUP",
    "ERN",
    "IRR",
    "KPW",
    "LYD",
    "SDG",
    "SSP",
    "SYP",
    "VES",
    "ZWG",
    "IQD",
    "BTN",
    "TMT",
}
# Published daily by the European Central Bank
ECB = {"AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "HKD", "HUF", "IDR", "ILS", "INR", "ISK",
       "JPY", "KRW", "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR"}  # fmt: skip

# Udemy-style GBP price tiers (pence). Free is a course setting, not a tier.
TIERS_GBP = [
    1499,
    1999,
    2499,
    2999,
    3499,
    3999,
    4499,
    4999,
    5499,
    5999,
    6499,
    6999,
    7499,
    7999,
    8499,
    8999,
    9499,
    9999,
]
