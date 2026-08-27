"""Resolve a raw ATS location string to Canadian gazetteer places.

Pure functions, no I/O — the gazetteer is injected, so every collision in the
production data is a unit test. Replaces the keyword matching in
``location_filter.py``, whose substring lists could not tell Saskatchewan's
``sk`` from Slovakia's, or Ontario the province from Ontario, California.

Statuses:
    resolved     one or more Canadian places, with coordinates
    countrywide  Canadian but no city (``Canada``, ``Remote - Canada``)
    foreign      confidently not Canadian — rejected at ingest
    unresolved   cannot confirm Canadian — rejected at ingest, kept if already stored
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador", "NS": "Nova Scotia",
    "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon", "NT": "Northwest Territories",
    "NU": "Nunavut",
}

PROVINCE_BY_TOKEN: dict[str, str] = {}
for _code, _name in PROVINCES.items():
    PROVINCE_BY_TOKEN[_code.lower()] = _code
    PROVINCE_BY_TOKEN[_name.lower()] = _code
PROVINCE_BY_TOKEN.update({
    "que": "QC", "queb": "QC", "quebec": "QC", "pq": "QC",
    "ont": "ON", "alta": "AB", "sask": "SK", "man": "MB",
    "newfoundland": "NL", "newfoundland & labrador": "NL",
    "b.c.": "BC", "p.e.i.": "PE", "pei": "PE",
})

CANADA_TOKENS = {"ca", "can", "canada", "cad", "ca.", "canada."}

# Non-Canadian country markers. Deliberately excludes bare two-letter codes that
# collide with province abbreviations (sk, nt, ab, on, ns, nb, pe, nl, bc, mb, yt);
# those are handled by requiring the city to actually exist in the claimed province.
FOREIGN_COUNTRY_TOKENS = {
    "us", "usa", "u.s.", "u.s.a.", "united states", "united states of america",
    "uk", "u.k.", "united kingdom", "england", "scotland", "wales", "ireland",
    "au", "aus", "australia", "nz", "new zealand", "de", "germany", "deutschland",
    "fr", "france", "es", "spain", "it", "italy", "nl", "netherlands",
    "pl", "poland", "cz", "czechia", "czech republic", "at", "austria",
    "ch", "switzerland", "pt", "portugal", "se", "sweden", "no", "norway",
    "dk", "denmark", "fi", "finland", "ie", "in", "india", "cn", "china",
    "jp", "japan", "kr", "south korea", "sg", "singapore", "hk", "hong kong",
    "tw", "taiwan", "ph", "philippines", "id", "indonesia", "th", "thailand",
    "vn", "vietnam", "my", "malaysia", "il", "israel", "ae",
    "united arab emirates", "sa", "saudi arabia", "tr", "turkey", "eg", "egypt",
    "za", "south africa", "ke", "kenya", "ng", "nigeria", "ma", "morocco",
    "mx", "mexico", "br", "brazil", "ar", "argentina", "cl", "chile",
    "co", "colombia", "pe", "peru", "uy", "uruguay", "cr", "costa rica",
    "ro", "romania", "hu", "hungary", "bg", "bulgaria", "hr", "croatia",
    "rs", "serbia", "ua", "ukraine", "gr", "greece", "sk", "slovakia",
    "si", "slovenia", "lt", "lithuania", "lv", "latvia", "ee", "estonia",
    "be", "belgium", "lu", "luxembourg", "is", "iceland", "mt", "malta",
}
# These collide with province abbreviations, so they only count as foreign when
# they appear as a full country name, never as the bare code.
_PROVINCE_COLLIDING = {"sk", "nt", "ab", "on", "ns", "nb", "pe", "nl", "bc", "mb", "yt", "nu", "qc"}
FOREIGN_COUNTRY_TOKENS -= _PROVINCE_COLLIDING

US_STATE_TOKENS = {
    "al", "ak", "az", "ar", "co", "ct", "dc", "de", "fl", "ga", "hi", "ia",
    "id", "il", "ks", "ky", "la", "md", "me", "mi", "mn", "mo", "ms", "mt",
    "nc", "nd", "ne", "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa",
    "ri", "sc", "sd", "tn", "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy",
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
}
FOREIGN_COUNTRY_TOKENS |= US_STATE_TOKENS
FOREIGN_COUNTRY_TOKENS -= _PROVINCE_COLLIDING | CANADA_TOKENS

REMOTE_TOKENS = {"remote", "remotely", "work from home", "wfh", "anywhere",
                 "distributed", "virtual", "telecommute", "home based", "home-based"}

# Stripped from the end of a segment before city lookup.
NOISE_WORDS = {
    "office", "offices", "headquarters", "hq", "hybrid", "onsite", "on-site",
    "campus", "branch", "location", "area", "region", "metro", "downtown",
    "greater", "city", "the", "and", "or", "remote", "canada", "based",
}

# Cities that exist in Canada and are far better known elsewhere. Without a
# province or an explicit Canada marker these stay unresolved rather than being
# claimed for Canada.
AMBIGUOUS_BARE_CITIES = {
    "london", "hamilton", "waterloo", "victoria", "windsor", "cambridge",
    "kingston", "richmond", "chatham", "stratford", "woodstock", "peterborough",
    "sarnia", "delta", "surrey", "aurora", "milton", "newmarket", "essex",
    "bradford", "orange", "birmingham",
}

# Hand-maintained forms the gazetteer cannot know about.
MANUAL_ALIASES: dict[str, list[tuple[str, str]]] = {
    "greater toronto": [("Toronto", "ON")],
    "greater toronto area": [("Toronto", "ON")],
    "gta": [("Toronto", "ON")],
    "toronto gta": [("Toronto", "ON")],
    "greater montreal": [("Montréal", "QC")],
    "greater vancouver": [("Vancouver", "BC")],
    "metro vancouver": [("Vancouver", "BC")],
    "greater edmonton": [("Edmonton", "AB")],
    "greater calgary": [("Calgary", "AB")],
    "greater ottawa": [("Ottawa", "ON")],
    "national capital region": [("Ottawa", "ON")],
    "kitchener waterloo": [("Kitchener", "ON"), ("Waterloo", "ON")],
    "kitchener-waterloo": [("Kitchener", "ON"), ("Waterloo", "ON")],
    "waterloo kitchener": [("Kitchener", "ON"), ("Waterloo", "ON")],
    "kw": [("Kitchener", "ON"), ("Waterloo", "ON")],
    "tri-cities": [("Kitchener", "ON"), ("Waterloo", "ON"), ("Cambridge", "ON")],
    "gtha": [("Toronto", "ON"), ("Hamilton", "ON")],
    "st johns": [("St. John's", "NL")],
    "quebec city": [("Québec", "QC")],
    "ville de quebec": [("Québec", "QC")],
}

# " or " needs surrounding whitespace: a bare \bor\b splits Val-d'Or and Oréleans.
# "/" is a *part* separator ("Waterloo / Ontario" is one place), handled in _clean_segment.
SEGMENT_SPLIT = re.compile(r"[;|]|\s+or\s+", re.IGNORECASE)
PARENTHETICAL = re.compile(r"\([^)]*\)")

STATUS_RESOLVED = "resolved"
STATUS_COUNTRYWIDE = "countrywide"
STATUS_FOREIGN = "foreign"
STATUS_UNRESOLVED = "unresolved"


def fold(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


@dataclass
class Place:
    slug: str
    name: str
    province: str
    latitude: float
    longitude: float
    population: int


@dataclass
class Resolution:
    status: str
    slugs: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def is_canadian(self) -> bool:
        return self.status in (STATUS_RESOLVED, STATUS_COUNTRYWIDE)


class Gazetteer:
    """Name+province lookup over the places table."""

    def __init__(self, places: list[Place]):
        self.by_slug: dict[str, Place] = {}
        self._by_name_province: dict[tuple[str, str], Place] = {}
        self._by_name: dict[str, list[Place]] = {}

        for place in places:
            self.by_slug[place.slug] = place
            key = fold(place.name)
            self._by_name_province.setdefault((key, place.province), place)
            self._by_name.setdefault(key, []).append(place)

        for candidates in self._by_name.values():
            candidates.sort(key=lambda p: -p.population)

    @classmethod
    def from_rows(cls, rows) -> "Gazetteer":
        return cls([
            Place(
                slug=row["slug"],
                name=row["name"],
                province=row["province"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                population=int(row["population"] or 0),
            )
            for row in rows
        ])

    def lookup(self, name: str, province: str | None) -> Place | None:
        key = fold(name)
        if province:
            return self._by_name_province.get((key, province))
        candidates = self._by_name.get(key)
        return candidates[0] if candidates else None

    def exists_anywhere(self, name: str) -> bool:
        return fold(name) in self._by_name


def _clean_segment(segment: str) -> str:
    # Keep what is inside the parentheses as its own comma part — dropping it
    # loses the country in "Remote (Canada)".
    segment = PARENTHETICAL.sub(lambda m: ", " + m.group(0)[1:-1] + ", ", segment)
    segment = segment.replace("–", "-").replace("—", "-")
    segment = segment.replace("/", ",").replace(":", ",")
    return re.sub(r"\s+", " ", segment).strip(" \t-,")


def _strip_noise(token: str) -> str:
    words = [w for w in fold(token).split() if w and any(ch.isalnum() for ch in w)]
    while words and words[-1] in NOISE_WORDS:
        words.pop()
    while words and words[0] in NOISE_WORDS:
        words.pop(0)
    return " ".join(words)


def _expand_candidate(token: str) -> list[str]:
    """A candidate plus its hyphen parts, so 'CA-ON-Toronto' yields 'toronto'."""
    out = [token]
    if "-" in token:
        for piece in token.split("-"):
            piece = piece.strip()
            if piece and piece not in CANADA_TOKENS and piece not in PROVINCE_BY_TOKEN:
                out.append(piece)
    return out


def _resolve_segment(segment: str, gazetteer: Gazetteer) -> tuple[str, list[Place], str]:
    """Return (status, places, reason) for one comma-delimited segment."""
    cleaned = _clean_segment(segment)
    if not cleaned:
        return STATUS_UNRESOLVED, [], "empty segment"

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    folded = [fold(p) for p in parts]
    if not folded:
        return STATUS_UNRESOLVED, [], "empty segment"

    # Province-wide ("Ontario, Canada") — but not when the leading token is also a
    # real city in that province, which is exactly the case for "Québec, QC".
    non_country = [t for t in folded if t not in CANADA_TOKENS]
    if non_country and all(t in PROVINCE_BY_TOKEN for t in non_country):
        if not gazetteer.lookup(non_country[0], PROVINCE_BY_TOKEN[non_country[-1]]):
            return STATUS_COUNTRYWIDE, [], f"province only ({PROVINCE_BY_TOKEN[non_country[0]]})"

    whole = fold(cleaned)
    words = set(re.split(r"[^a-z0-9.]+", whole))
    is_remote = any(token in whole for token in REMOTE_TOKENS)

    # An explicit foreign country anywhere in the segment settles it. This is what
    # catches 'Ontario, CA, US' and 'Vancouver, WA, US', where a Canadian-looking
    # token sits beside an unambiguous foreign one.
    for token in folded:
        if token in FOREIGN_COUNTRY_TOKENS:
            return STATUS_FOREIGN, [], f"foreign country token '{token}'"

    # Checked at word level too, so "Remote - Canada" and "Anywhere in Canada"
    # register even though they are a single comma part.
    has_canada_marker = bool(words & CANADA_TOKENS) or any(t in CANADA_TOKENS for t in folded)

    # The leading part is almost always the city, even when it doubles as a
    # province name ("Québec, QC"), so scan for the province after it first.
    province = None
    for token in folded[1:] or folded:
        code = PROVINCE_BY_TOKEN.get(token)
        if code:
            province = code
            break
    if province is None and len(folded) == 1:
        province = PROVINCE_BY_TOKEN.get(folded[0])

    candidates: list[str] = []
    for index, token in enumerate(folded):
        if token in CANADA_TOKENS:
            continue
        if index > 0 and PROVINCE_BY_TOKEN.get(token):
            continue
        for form in (token.rstrip(". "), _strip_noise(token)):
            if not form:
                continue
            for expanded in _expand_candidate(form):
                if expanded and expanded not in candidates:
                    candidates.append(expanded)

    for candidate in candidates:
        if candidate in MANUAL_ALIASES:
            places = [gazetteer.lookup(name, prov) for name, prov in MANUAL_ALIASES[candidate]]
            places = [p for p in places if p]
            if places:
                return STATUS_RESOLVED, places, f"alias '{candidate}'"

    for candidate in candidates:
        if province:
            place = gazetteer.lookup(candidate, province)
            if place:
                return STATUS_RESOLVED, [place], f"'{candidate}' in {province}"
        else:
            if candidate in AMBIGUOUS_BARE_CITIES and not has_canada_marker:
                continue
            place = gazetteer.lookup(candidate, None)
            if place:
                return STATUS_RESOLVED, [place], f"'{candidate}' (no province given)"

    # No city matched. A claimed province whose city exists nowhere in Canada is
    # the Slovakia case: 'Košice, Košický kraj, sk' claims SK but Košice is not
    # a Canadian city. An explicit Canada marker means the intent was Canadian
    # and the string is merely junk, so that stays reviewable instead.
    if province and candidates and not has_canada_marker:
        if not any(gazetteer.exists_anywhere(c) for c in candidates):
            return STATUS_FOREIGN, [], f"no Canadian city named {candidates[0]!r} in {province}"

    if is_remote and (has_canada_marker or province):
        return STATUS_COUNTRYWIDE, [], "remote within Canada"
    if has_canada_marker and not any(gazetteer.exists_anywhere(c) for c in candidates):
        if not candidates:
            return STATUS_COUNTRYWIDE, [], "country only"
        return STATUS_UNRESOLVED, [], "Canadian marker but no known city"
    if has_canada_marker or province:
        return STATUS_UNRESOLVED, [], "Canadian marker but no known city"
    if is_remote:
        return STATUS_UNRESOLVED, [], "remote with no country given"
    return STATUS_UNRESOLVED, [], "no Canadian signal"


# Segment statuses are combined so one confident Canadian hit wins over noise:
# 'US-NYC; US-SF; Canada-Toronto' is a Toronto job, not a New York one.
_PRIORITY = {STATUS_RESOLVED: 3, STATUS_COUNTRYWIDE: 2, STATUS_UNRESOLVED: 1, STATUS_FOREIGN: 0}


def resolve(raw: str | None, gazetteer: Gazetteer) -> Resolution:
    """Resolve a raw ATS location string."""
    if not raw or not raw.strip():
        return Resolution(STATUS_UNRESOLVED, [], "empty")

    segments = [s for s in SEGMENT_SPLIT.split(raw) if s and s.strip()]
    if not segments:
        segments = [raw]

    places: list[Place] = []
    seen: set[str] = set()
    best_status = STATUS_FOREIGN
    reasons: list[str] = []

    for segment in segments:
        status, found, reason = _resolve_segment(segment, gazetteer)
        if _PRIORITY[status] > _PRIORITY[best_status]:
            best_status = status
        for place in found:
            if place.slug not in seen:
                seen.add(place.slug)
                places.append(place)
        reasons.append(reason)

    if places:
        return Resolution(STATUS_RESOLVED, [p.slug for p in places], "; ".join(reasons[:3]))
    return Resolution(best_status, [], "; ".join(reasons[:3]))
