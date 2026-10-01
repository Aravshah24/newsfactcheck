from __future__ import annotations

"""Stance value helpers.

The earlier version of this module contained a hardcoded list of event verbs
(``land``, ``touch down``, ``opened``, ``won``, ...) together with regexes for
object and event slots. Those rules only worked for the specific examples they
were written against and silently returned "supports" for propositions they did
not recognise, which turned topical relevance into support.

Propositional comparison now lives in :mod:`app.services.entailment`, which
compares a decomposed claim against a document along generic dimensions. This
module keeps only value normalisation helpers for stance labels.
"""

SUPPORTING = "supports"
CONTRADICTING = "contradicts"
CONTEXTUAL = "context"
NEUTRAL = "neutral"
UNKNOWN = "unknown"

PROBATIVE_STANCES = {SUPPORTING, CONTRADICTING}
NON_PROBATIVE_STANCES = {CONTEXTUAL, NEUTRAL, UNKNOWN}
ALL_STANCES = PROBATIVE_STANCES | NON_PROBATIVE_STANCES


def stance_value(stance: object) -> str:
    """Return the lowercase string value of a stance, enum or plain string."""
    if stance is None:
        return UNKNOWN
    return str(getattr(stance, "value", stance)).strip().lower()


def normalise_stance(stance: object) -> str:
    """Coerce any stance input into one of the five known stance values."""
    value = stance_value(stance)
    return value if value in ALL_STANCES else UNKNOWN


def is_probative(stance: object) -> bool:
    return normalise_stance(stance) in PROBATIVE_STANCES
