"""Compiler configuration: bench connection, bookkeeping ids, module constants."""

from dataclasses import dataclass

# The instance a person opens, not the API endpoint: this is the link the report
# and the MCF header print, and the one the README lists. `Config.url` appends
# the endpoint, so the two can't drift.
BENCHES = {
    "prod": "https://developmentfinance.wikibase.cloud",
    "testing": "https://dfo-testing-2.wikibase.cloud",
    "dev": "https://dfo-dev.wikibase.cloud",
}
API_PATH = "/w/api.php"
# Temporary: Data Commons cannot resolve a custom namespace yet, so we mint under
# theirs. Reverting the commit that set this undoes the switch everywhere.
PREFIX = "dcid"
ITEM_NAMESPACE = 120
PROPERTY_NAMESPACE = 122
BATCH_SIZE = 50  # wbgetentities ids per call
PAGE_LIMIT = 500  # allpages aplimit
CLASSIFICATION_CODE_ID = "classificationCode"
DAC_CODE_ID = "dacCode"
IMF_ECONOMY_CODE_ID = "imfEconomyCode"
ISO_ALPHA_CODE_ID = "iso4217AlphaCode"
M49_CODE_ID = "m49Code"
WB_CODE_ID = "wbCode"
WB_COUNTERPART_CODE_ID = "wbCounterpartCode"
WB_ECONOMY_CODE_ID = "wbEconomyCode"
# Code-bearing properties: their codes flow into codes.csv and the report's
# coverage section. Uniqueness stays per-property — G9 checks only
# classificationCode, where the code is the value's identity. The rest record a
# code a thing carries in someone else's register, where duplicates are legal.
CODE_PROPERTY_IDS = (
    CLASSIFICATION_CODE_ID,
    DAC_CODE_ID,
    IMF_ECONOMY_CODE_ID,
    ISO_ALPHA_CODE_ID,
    M49_CODE_ID,
    WB_CODE_ID,
    WB_COUNTERPART_CODE_ID,
    WB_ECONOMY_CODE_ID,
)
# G10 and G11's vocabulary: nationalCurrencyOf names a place whose national
# currency this is. It sits only on a currency whose currencyStatus is current
# (G10), and each place is named by at most one currency (G11).
NATIONAL_CURRENCY_OF_ID = "nationalCurrencyOf"
CURRENCY_STATUS_ID = "currencyStatus"
CURRENCY_STATUS_CURRENT_ID = "CurrencyStatusCurrent"
# A node flagged isProvisional → True is not final yet. True is a Data Commons
# node, so the flag is matched on the bare dcid of its target.
IS_PROVISIONAL_ID = "isProvisional"
TRUE_ID = "True"


@dataclass(frozen=True)
class Config:
    """Bench connection and bookkeeping property ids.

    Every bench shares all settings but the URL, so only the bench name is an
    input; `site` and `url` derive from it.
    """

    bench: str
    id_property: str = "P1"
    dcid_property: str = "P2"
    prefix: str = PREFIX
    namespaces: tuple[int, ...] = (ITEM_NAMESPACE, PROPERTY_NAMESPACE)
    batch_size: int = BATCH_SIZE

    @property
    def site(self) -> str:
        """The instance's browsable URL."""
        return BENCHES[self.bench]

    @property
    def url(self) -> str:
        """The instance's api.php endpoint."""
        return f"{self.site}{API_PATH}"

    @property
    def provenance(self) -> str:
        """The line naming this bench, carried by both the report and the MCF."""
        return f"bench: {self.bench} ({self.site})"
