"""Rule-based witness classification.

A document's *provenance class* records what kind of witness it is, not how
trustworthy it is. The distinction matters: a court record and a news report
are not more or less reliable in the abstract, they are different kinds of
evidence that are allowed to play different roles. Reliability scoring, with its
own auditable inputs, is deliberately not part of this module.

Classification is deterministic and every result carries the rule that produced
it, so a reviewer can inspect and disagree with any single decision. No model is
consulted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


class ProvenanceClass(str, Enum):
    OFFICIAL_STATISTIC = "official_statistic"
    COURT_RECORD = "court_record"
    REGULATORY_FILING = "regulatory_filing"
    PEER_REVIEWED = "peer_reviewed"
    PRIMARY_RECORD = "primary_record"
    EXISTING_FACT_CHECK = "existing_fact_check"
    NEWS_REPORTING = "news_reporting"
    OPINION = "opinion"
    ENCYCLOPEDIC = "encyclopedic"
    UNKNOWN = "unknown"


#: Classes that are the record of the event itself rather than a report about it.
AUTHORITATIVE_CLASSES = frozenset(
    {
        ProvenanceClass.OFFICIAL_STATISTIC,
        ProvenanceClass.COURT_RECORD,
        ProvenanceClass.REGULATORY_FILING,
        ProvenanceClass.PRIMARY_RECORD,
    }
)

#: Classes that describe reporting rather than the underlying record.
SECONDARY_CLASSES = frozenset(
    {
        ProvenanceClass.NEWS_REPORTING,
        ProvenanceClass.OPINION,
        ProvenanceClass.ENCYCLOPEDIC,
    }
)

#: Classes that must never be the sole basis for supporting a claim.
NON_SOLE_SUPPORT_CLASSES = frozenset(
    {
        ProvenanceClass.OPINION,
        ProvenanceClass.ENCYCLOPEDIC,
        ProvenanceClass.UNKNOWN,
    }
)


@dataclass(frozen=True)
class ProvenanceAssessment:
    """A classification plus the rule that produced it."""

    provenance_class: ProvenanceClass
    rule: str
    basis: str


# Ordered most specific first. A host is matched by exact name or by suffix, so
# "justice.gov" cannot be captured by a broader "gov" rule placed above it.
_HOST_RULES: tuple[tuple[ProvenanceClass, str, tuple[str, ...]], ...] = (
    # --- courts -------------------------------------------------------
    (
        ProvenanceClass.COURT_RECORD,
        "host_known_court",
        (
            "courtlistener.com",
            "supremecourt.gov",
            "uscourts.gov",
            "law.justia.com",
            "judiciary.uk",
            "courts.gov",
            "eurojust.europa.eu",
            "curia.europa.eu",
            "canlii.org",
            "bailii.org",
            "indiankanoon.org",
        ),
    ),
    # --- regulatory filings -------------------------------------------
    (
        ProvenanceClass.REGULATORY_FILING,
        "host_known_filing_registry",
        (
            "sec.gov",
            "companieshouse.gov.uk",
            "find-and-update.company-information.service.gov.uk",
            "edgar.sec.gov",
            "annualreports.com",
            "mca.gov.in",
            "rbi.org.in",
            "sebi.gov.in",
        ),
    ),
    # --- official statistics ------------------------------------------
    (
        ProvenanceClass.OFFICIAL_STATISTIC,
        "host_known_statistics_body",
        (
            "census.gov",
            "bls.gov",
            "ons.gov.uk",
            "eurostat.ec.europa.eu",
            "data.gov",
            "data.gov.uk",
            "stats.gov.cn",
            "stats.gov.in",
            "worldbank.org",
            "imf.org",
            "oecd.org",
            "who.int",
            "un.org",
            "unfpa.org",
            "unicef.org",
            "nasa.gov",
            "noaa.gov",
            "usgs.gov",
            "esa.int",
            "isro.gov.in",
            "pib.gov.in",
            "eci.gov",
        ),
    ),
    # --- prior adjudication -------------------------------------------
    (
        ProvenanceClass.EXISTING_FACT_CHECK,
        "host_known_fact_checker",
        (
            "snopes.com",
            "factcheck.org",
            "politifact.com",
            "fullfact.org",
            "factchecker.org",
            "reuters.com",
            "apnews.com",
            "boomlive.in",
            "afp.com",
            "leadstories.com",
        ),
    ),
    # --- scholarly literature -----------------------------------------
    (
        ProvenanceClass.PEER_REVIEWED,
        "host_known_scholarly",
        (
            "doi.org",
            "arxiv.org",
            "biorxiv.org",
            "medrxiv.org",
            "nature.com",
            "science.org",
            "cell.com",
            "thelancet.com",
            "bmj.com",
            "jamanetwork.com",
            "ncbi.nlm.nih.gov",
            "springer.com",
            "sciencedirect.com",
            "plos.org",
            "ieee.org",
            "acm.org",
            "ssrn.com",
            "jstor.org",
        ),
    ),
    # --- encyclopedic --------------------------------------------------
    (
        ProvenanceClass.ENCYCLOPEDIC,
        "host_known_encyclopedic",
        (
            "wikipedia.org",
            "wikidata.org",
            "wikisource.org",
            "britannica.com",
            "encyclopedia.com",
            "encyclopaedia.com",
        ),
    ),
)

#: Government domains that are official but not a statistics body.
_GOVERNMENT_SUFFIXES = (".gov", ".gov.uk", ".gov.in", ".gov.au", ".mil", ".int")

#: Publishers that are wire services or national newsrooms, which report rather
#: than originate the record.
_KNOWN_NEWS = (
    "reuters.com",
    "apnews.com",
    "bbc.co.uk",
    "bbc.com",
    "npr.org",
    "aljazeera.com",
    "theguardian.com",
    "nytimes.com",
    "washingtonpost.com",
    "wsi.com",
    "ft.com",
    "economist.com",
    "timesofindia.indiatimes.com",
    "thehindu.com",
    "ndtv.com",
    "pib.gov.in",
    "space.com",
    "nasa.gov",
    "nature.com",
    "abc.net.au",
)

#: Title markers for editorial and opinion writing. Kept narrow on purpose: a
#: false positive would silently remove a document's ability to support a claim.
_OPINION_TITLE_MARKERS = (
    "opinion",
    "editorial:",
    "oped",
    "op-ed",
    "comment:",
    "commentary:",
    "letters to the editor",
    "why i",
    "we are wrong",
    "opinion:",
)


def _host_of(url: str | None) -> str:
    if not url:
        return ""
    candidate = url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        host = urlsplit(candidate).hostname or ""
    except ValueError:
        return ""
    host = host.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _host_matches(host: str, candidate: str) -> bool:
    return host == candidate or host.endswith(f".{candidate}")


def classify(
    url: str | None = None,
    *,
    source_type: str | None = None,
    publisher: str | None = None,
    title: str | None = None,
    document_class: str | None = None,
) -> ProvenanceAssessment:
    """Classify a document from its URL and, failing that, weaker signals.

    Domain rules take precedence because the registrable domain is the only
    signal a retriever cannot freely assert. Everything else is a fallback and
    is reported as such in ``rule``.
    """

    host = _host_of(url)

    # The primary-source retriever declares its own provenance explicitly.
    declared = str(source_type or document_class or "").strip().lower()
    if declared in {"court_record", "official_statistic", "regulatory_filing"}:
        return ProvenanceAssessment(ProvenanceClass(declared), "declared_source_type", host or declared)

    if host:
        for provenance_class, rule, hosts in _HOST_RULES:
            for candidate in hosts:
                if _host_matches(host, candidate):
                    return ProvenanceAssessment(provenance_class, rule, host)

        # apnews.com and reuters.com carry both reporting and fact-check desks;
        # a check in the path is the more specific signal.
        if _host_matches(host, "apnews.com") and "/fact-check" in (url or "").lower():
            return ProvenanceAssessment(
                ProvenanceClass.EXISTING_FACT_CHECK, "fact_check_path", host
            )
        if _host_matches(host, "reuters.com") and "/fact-check" in (url or "").lower():
            return ProvenanceAssessment(
                ProvenanceClass.EXISTING_FACT_CHECK, "fact_check_path", host
            )

        if any(host.endswith(suffix) for suffix in _GOVERNMENT_SUFFIXES):
            return ProvenanceAssessment(ProvenanceClass.OFFICIAL_STATISTIC, "government_domain", host)

        for candidate in _KNOWN_NEWS:
            if _host_matches(host, candidate):
                return ProvenanceAssessment(ProvenanceClass.NEWS_REPORTING, "host_known_news", host)

    lowered_title = (title or "").strip().lower()
    if lowered_title:
        for marker in _OPINION_TITLE_MARKERS:
            if marker in lowered_title:
                return ProvenanceAssessment(ProvenanceClass.OPINION, "opinion_title_marker", lowered_title[:80])

    if declared in {"primary"}:
        return ProvenanceAssessment(ProvenanceClass.PRIMARY_RECORD, "declared_primary", host or declared)
    if declared in {"authoritative", "press_release", "official"}:
        return ProvenanceAssessment(ProvenanceClass.PRIMARY_RECORD, "declared_authoritative", host or declared)
    if declared in {"blog", "social"}:
        return ProvenanceAssessment(ProvenanceClass.OPINION, "declared_non_reporting", host or declared)

    # Retrieved web results declare "news". Falling through to UNKNOWN here would
    # make every ordinary article weigh nothing, so a declared reporting result
    # is classified as reporting even when its domain is not on the known list.
    if declared in {"news", "reporting", "other"}:
        return ProvenanceAssessment(
            ProvenanceClass.NEWS_REPORTING, "declared_reporting", host or declared
        )

    if publisher and _host_of(publisher):
        publisher_host = _host_of(publisher)
        for provenance_class, rule, hosts in _HOST_RULES:
            for candidate in hosts:
                if _host_matches(publisher_host, candidate):
                    return ProvenanceAssessment(provenance_class, f"publisher_{rule}", publisher_host)

    return ProvenanceAssessment(ProvenanceClass.UNKNOWN, "unclassified", host or publisher or "")


def provenance_value(assessment_or_class: ProvenanceAssessment | ProvenanceClass | str | None) -> str:
    """Return the stored string value for an assessment or class."""
    if assessment_or_class is None:
        return ProvenanceClass.UNKNOWN.value
    if isinstance(assessment_or_class, ProvenanceAssessment):
        return assessment_or_class.provenance_class.value
    return str(getattr(assessment_or_class, "value", assessment_or_class))


def is_authoritative(value: object) -> bool:
    key = provenance_value(value)  # type: ignore[arg-type]
    return ProvenanceClass(key) in AUTHORITATIVE_CLASSES


def never_sole_support(value: object) -> bool:
    key = provenance_value(value)  # type: ignore[arg-type]
    return ProvenanceClass(key) in NON_SOLE_SUPPORT_CLASSES