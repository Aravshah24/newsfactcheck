"""Editorial-lean labels for media outlets, with the reviewer behind each label.

The point of this table is *auditability*, not completeness. Every label records
which independent reviewer assigned it and where it can be checked. Outlets not
in the table are reported in the ``unknown`` bucket rather than guessed.

Notes on use:
- A publisher's lean describes the shape of coverage, never its truthfulness.
- Labels are a snapshot: ``LEAN_AS_OF`` states the rating period consulted.
- Different reviewers disagree on some outlets; where so, one is cited and the
  other is left for the reader to consult.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_LEAN_AS_OF = "2026-10"

_ALLSIDES = "https://www.allsides.com/media-bias/media-bias-ratings"
_MBFC = "https://mediabiasfactcheck.com/"
_AD_FONTES = "https://adfontesmedia.com/interactive-media-bias-chart/"


@dataclass(frozen=True)
class OutletLean:
    label: str
    source: str
    reference: str
    as_of: str = field(default=_LEAN_AS_OF)


def _allsides(label: str) -> OutletLean:
    return OutletLean(label=label, source="AllSides", reference=_ALLSIDES)


def _mbfc(label: str) -> OutletLean:
    return OutletLean(label=label, source="Media Bias/Fact Check", reference=_MBFC)


def _afm(label: str) -> OutletLean:
    return OutletLean(label=label, source="Ad Fontes Media", reference=_AD_FONTES)


#: Public version of the rating period, for methodology copy.
LEAN_AS_OF: str = _LEAN_AS_OF


#: Maps a substring token used to match a publisher name to its lean record.
#: Tokens are matched in insertion order, so more specific phrases come first.
OUTLET_LEAN: dict[str, OutletLean] = {
    # --- LEFT ----------------------------------------------------------
    "mother jones": _allsides("LEFT"),
    "democracy now": _allsides("LEFT"),
    "democracynow": _allsides("LEFT"),
    "the intercept": _allsides("LEFT"),
    "the nation": _allsides("LEFT"),
    "the new republic": _allsides("LEFT"),
    "commondreams": _allsides("LEFT"),
    "truthout": _mbfc("LEFT"),
    "buzzfeed news": _allsides("LEFT"),
    "vice news": _allsides("LEFT"),
    "vice": _allsides("LEFT"),
    "slate": _allsides("LEFT"),
    "salon": _allsides("LEFT"),
    "the daily beast": _allsides("LEFT"),
    "msnbc": _mbfc("LEFT"),
    "huffpost": _mbfc("LEFT"),
    "huffington post": _mbfc("LEFT"),
    "vox": _allsides("LEFT"),
    "the atlantic": _allsides("LEFT"),
    "the new yorker": _allsides("LEFT"),
    "the nytimes": _allsides("LEFT"),
    "new york times": _allsides("LEFT"),
    "washington post": _allsides("LEFT"),
    "the guardian": _allsides("LEFT"),
    "guardian": _allsides("LEFT"),
    "politico": _allsides("LEFT"),
    "politics usa": _allsides("LEFT"),
    "the independent": _allsides("LEFT"),
    "independent": _allsides("LEFT"),
    "rolling stone": _allsides("LEFT"),
    "time magazine": _allsides("LEFT"),
    "thedailybeast": _allsides("LEFT"),
    "haaretz": _allsides("LEFT"),
    "elpais": _allsides("LEFT"),
    "el pais": _allsides("LEFT"),
    "the wire india": _mbfc("LEFT"),
    "the hindu": _mbfc("LEFT"),
    "cnn": _allsides("LEFT"),
    # --- CENTER --------------------------------------------------------
    "associated press": _allsides("CENTER"),
    "ap news": _allsides("CENTER"),
    "ap wire": _allsides("CENTER"),
    "reuters": _allsides("CENTER"),
    "bbc": _allsides("CENTER"),
    "bbc.co": _allsides("CENTER"),
    "npr": _allsides("CENTER"),
    "pbs newshour": _allsides("CENTER"),
    "pbs": _allsides("CENTER"),
    "cbs news": _allsides("CENTER"),
    "abc news": _allsides("CENTER"),
    "nbc news": _allsides("CENTER"),
    "usa today": _mbfc("CENTER"),
    "usatoday": _mbfc("CENTER"),
    "cnbc": _allsides("CENTER"),
    "bloomberg": _allsides("CENTER"),
    "forbes": _allsides("CENTER"),
    "axios": _allsides("CENTER"),
    "the hill": _allsides("CENTER"),
    "the week": _allsides("CENTER"),
    "newsweek": _allsides("CENTER"),
    "business insider": _allsides("CENTER"),
    "marketwatch": _allsides("CENTER"),
    "qz.com": _allsides("CENTER"),
    "quartz": _allsides("CENTER"),
    "france 24": _allsides("CENTER"),
    "france24": _allsides("CENTER"),
    "deutsche welle": _allsides("CENTER"),
    "dw.com": _allsides("CENTER"),
    "al jazeera": _allsides("CENTER"),
    "aljazeera": _allsides("CENTER"),
    "kathimerini": _mbfc("CENTER"),
    "rte": _mbfc("CENTER"),
    "sky news": _mbfc("CENTER"),
    "channel 4 news": _mbfc("CENTER"),
    "itv news": _mbfc("CENTER"),
    "the economist": _mbfc("CENTER"),
    "economist": _mbfc("CENTER"),
    "financial times": _mbfc("CENTER"),
    "ft.com": _mbfc("CENTER"),
    "times of india": _mbfc("CENTER"),
    "hindustan times": _mbfc("CENTER"),
    "indian express": _mbfc("CENTER"),
    "india today": _mbfc("CENTER"),
    "india tv": _mbfc("CENTER"),
    "ndtv": _mbfc("CENTER"),
    "the quint": _mbfc("CENTER"),
    "sunday atlantic": _mbfc("CENTER"),
    "straits times": _mbfc("CENTER"),
    "channel newsasia": _mbfc("CENTER"),
    "japan times": _mbfc("CENTER"),
    "kyodo": _mbfc("CENTER"),
    "nhk": _mbfc("CENTER"),
    "mint": _mbfc("CENTER"),
    "livemint": _mbfc("CENTER"),
    "the hindu businessline": _mbfc("CENTER"),
    # --- RIGHT ---------------------------------------------------------
    "fox news": _allsides("RIGHT"),
    "foxbusiness": _allsides("RIGHT"),
    "fox business": _allsides("RIGHT"),
    "breitbart": _allsides("RIGHT"),
    "the daily wire": _allsides("RIGHT"),
    "daily wire": _allsides("RIGHT"),
    "the federalist": _allsides("RIGHT"),
    "national review": _allsides("RIGHT"),
    "the american conservative": _allsides("RIGHT"),
    "american conservative": _allsides("RIGHT"),
    "reason": _allsides("RIGHT"),
    "reason.com": _allsides("RIGHT"),
    "washington examiner": _allsides("RIGHT"),
    "washington times": _allsides("RIGHT"),
    "the blaze": _allsides("RIGHT"),
    "townhall": _allsides("RIGHT"),
    "redstate": _allsides("RIGHT"),
    "the daily caller": _allsides("RIGHT"),
    "new york post": _allsides("RIGHT"),
    "newyorkpost": _allsides("RIGHT"),
    "newsmax": _mbfc("RIGHT"),
    "one america news": _mbfc("RIGHT"),
    "oann": _mbfc("RIGHT"),
    "the epoch times": _mbfc("RIGHT"),
    "epoch times": _mbfc("RIGHT"),
    "gateway pundit": _mbfc("RIGHT"),
    "the daily signal": _allsides("RIGHT"),
    "daily signal": _allsides("RIGHT"),
    "zero hedge": _mbfc("RIGHT"),
    "the telegraph": _allsides("RIGHT"),
    "telegraph": _allsides("RIGHT"),
    "the times": _allsides("RIGHT"),
    "the sun": _allsides("RIGHT"),
    "daily mail": _allsides("RIGHT"),
    "dailymail": _allsides("RIGHT"),
    "the spectator": _allsides("RIGHT"),
    "spectator": _allsides("RIGHT"),
    "firstpost": _mbfc("RIGHT"),
    "republic world": _mbfc("RIGHT"),
    "opindia": _mbfc("RIGHT"),
    "rt.com": _mbfc("RIGHT"),
    "rt international": _mbfc("RIGHT"),
    "sputnik": _mbfc("RIGHT"),
    "china daily": _mbfc("RIGHT"),
    "the wall street journal": _allsides("RIGHT"),
    "wall street journal": _allsides("RIGHT"),
    "wsj": _allsides("RIGHT"),
}