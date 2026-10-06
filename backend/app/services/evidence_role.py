"""Evidence roles.

Stance answers "does this document agree with the claim?". Role answers "what
is this document's job in the adjudication?", which is derived from its
provenance class, whether it is a republication of something already seen, and
its stance.

The role weight is what stops article volume from becoming confidence: a
republication, an encyclopedia entry and a topically-related article all carry
zero, so no number of them can support a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.evidence_stance import normalise_stance
from app.services.provenance import (
    ProvenanceClass,
    is_authoritative,
    never_sole_support,
    provenance_value,
)


class EvidenceRole(str, Enum):
    #: An authoritative record confirms the proposition.
    PRIMARY_CONFIRMATION = "primary_confirmation"
    #: An authoritative record conflicts with the proposition.
    CONTRADICTORY_OFFICIAL = "contradictory_official"
    #: A separate group reports the same finding.
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    #: Reporting conflicts with the proposition.
    CONTRADICTORY_REPORTING = "contradictory_reporting"
    #: A prior adjudication addressed this claim.
    FACT_CHECK_VERDICT = "fact_check_verdict"
    #: Scholarly or credentialed expert analysis.
    EXPERT_ASSERTION = "expert_assertion"
    #: Opinion or an encyclopedia entry; can never be the sole support.
    WEAK_CORROBORATION = "weak_corroboration"
    #: Related to the topic without bearing on the proposition.
    TOPICALLY_RELATED = "topically_related"
    #: A republication of a document already in the pool.
    DERIVED_REPUBLICATION = "derived_republication"
    UNKNOWN = "unknown"


#: How much a role may contribute toward support or contradiction.
#:
#: Zero means the document cannot influence a verdict in that direction at any
#: quantity. This is the single most important table in the system: it is what
#: makes "many articles" and "much evidence" different quantities.
ROLE_WEIGHT: dict[EvidenceRole, float] = {
    EvidenceRole.PRIMARY_CONFIRMATION: 1.0,
    EvidenceRole.CONTRADICTORY_OFFICIAL: 1.0,
    # A separate outlet reporting the same finding is worth less than the record
    # itself, so corroboration accumulates but never substitutes for authority.
    EvidenceRole.INDEPENDENT_CORROBORATION: 0.6,
    EvidenceRole.FACT_CHECK_VERDICT: 0.9,
    EvidenceRole.EXPERT_ASSERTION: 0.8,
    EvidenceRole.CONTRADICTORY_REPORTING: 0.7,
    EvidenceRole.WEAK_CORROBORATION: 0.0,
    EvidenceRole.TOPICALLY_RELATED: 0.0,
    EvidenceRole.DERIVED_REPUBLICATION: 0.0,
    EvidenceRole.UNKNOWN: 0.0,
}

#: Roles that indicate the underlying record itself was consulted.
OFFICIAL_ROLES = frozenset(
    {
        EvidenceRole.PRIMARY_CONFIRMATION,
        EvidenceRole.CONTRADICTORY_OFFICIAL,
    }
)

PROBATIVE_ROLES = frozenset(role for role, weight in ROLE_WEIGHT.items() if weight > 0)


@dataclass(frozen=True)
class RoleAssignment:
    role: EvidenceRole
    reason: str


def role_value(assignment: RoleAssignment | EvidenceRole | str | None) -> str:
    if assignment is None:
        return EvidenceRole.UNKNOWN.value
    if isinstance(assignment, RoleAssignment):
        return assignment.role.value
    return str(getattr(assignment, "value", assignment))


def weight_for(role: EvidenceRole | str | None) -> float:
    """Contribution weight for a role, defaulting to zero when unrecognised."""
    try:
        key = EvidenceRole(role_value(role))  # type: ignore[arg-type]
    except ValueError:
        return 0.0
    return ROLE_WEIGHT.get(key, 0.0)


def classify_role(
    *,
    stance: str | None,
    provenance: object = None,
    is_derived: bool = False,
    is_expert: bool = False,
) -> RoleAssignment:
    """Assign an evidence role from provenance, derivation and stance.

    Derivation is checked first and unconditionally: a republished article is a
    republication whatever it says, so it cannot add weight to either direction.
    """

    if is_derived:
        return RoleAssignment(
            EvidenceRole.DERIVED_REPUBLICATION,
            "Republished from a document already in the evidence pool.",
        )

    normalised = normalise_stance(stance)
    if normalised in {"context", "neutral", "unknown"}:
        return RoleAssignment(
            EvidenceRole.TOPICALLY_RELATED,
            "Related to the topic but not probative for the proposition.",
        )

    try:
        provenance_class = ProvenanceClass(provenance_value(provenance))  # type: ignore[arg-type]
    except ValueError:
        provenance_class = ProvenanceClass.UNKNOWN

    if normalised == "contradicts":
        if is_authoritative(provenance_class):
            return RoleAssignment(
                EvidenceRole.CONTRADICTORY_OFFICIAL,
                "An authoritative record conflicts with the claim.",
            )
        return RoleAssignment(
            EvidenceRole.CONTRADICTORY_REPORTING,
            "Reporting conflicts with the claim.",
        )

    # Supporting.
    if provenance_class == ProvenanceClass.EXISTING_FACT_CHECK:
        return RoleAssignment(
            EvidenceRole.FACT_CHECK_VERDICT,
            "A prior adjudication of this claim.",
        )
    if is_authoritative(provenance_class):
        return RoleAssignment(
            EvidenceRole.PRIMARY_CONFIRMATION,
            "An authoritative record confirms the claim.",
        )
    if provenance_class == ProvenanceClass.PEER_REVIEWED or is_expert:
        return RoleAssignment(
            EvidenceRole.EXPERT_ASSERTION,
            "Scholarly or credentialed expert analysis.",
        )
    if never_sole_support(provenance_class):
        return RoleAssignment(
            EvidenceRole.WEAK_CORROBORATION,
            "Opinion or tertiary source; cannot be the sole basis for support.",
        )
    if provenance_class == ProvenanceClass.NEWS_REPORTING:
        return RoleAssignment(
            EvidenceRole.INDEPENDENT_CORROBORATION,
            "Independent reporting consistent with the claim.",
        )

    return RoleAssignment(
        EvidenceRole.UNKNOWN,
        "Source class could not be established, so it carries no weight.",
    )


def has_weight(role: EvidenceRole | str | None) -> bool:
    return weight_for(role) > 0


def is_official(role: EvidenceRole | str | None) -> bool:
    try:
        return EvidenceRole(role_value(role)) in OFFICIAL_ROLES  # type: ignore[arg-type]
    except ValueError:
        return False