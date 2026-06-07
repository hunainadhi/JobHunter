# Terms safe to substring-match (unique to Canada, won't match other countries)
SUBSTRING_MATCHES = {
    "canada",
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick",
    "newfoundland", "prince edward island", "northwest territories",
    "nunavut", "yukon",
    "toronto", "vancouver", "montreal", "montréal", "calgary", "edmonton",
    "ottawa", "winnipeg", "quebec city", "kitchener",
    "mississauga", "brampton", "markham",
    "richmond hill", "scarborough", "north york", "etobicoke",
    "remote - canada", "remote (canada)", "remote, canada",
    "remote - ca", "anywhere in canada",
}

# Cities that exist in other countries — only match if accompanied by a Canadian province/abbrev
AMBIGUOUS_CITIES = {
    "waterloo", "london", "hamilton", "halifax", "victoria",
    "saskatoon", "regina", "st. john's",
}

CANADIAN_PROVINCES = {
    "ontario", "quebec", "british columbia", "alberta", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick",
    "newfoundland", "prince edward island", "northwest territories",
    "nunavut", "yukon",
}

CANADIAN_PROVINCE_ABBREVS = {"on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "nt", "nu", "yt"}

NON_CANADIAN_INDICATORS = {"uk", "england", "australia", "new zealand", "united kingdom", "nigeria"}


def is_canadian_location(location_str: str | None, country_iso: str | None = None) -> bool:
    if country_iso and country_iso.upper() == "CA":
        return True

    if not location_str:
        return False

    normalized = location_str.lower().strip()

    for indicator in NON_CANADIAN_INDICATORS:
        if indicator in normalized:
            return False

    for loc in SUBSTRING_MATCHES:
        if loc in normalized:
            return True

    parts = [p.strip() for p in normalized.split(",")]

    # Province abbreviations are always a strong Canadian signal
    for part in parts:
        if part in CANADIAN_PROVINCE_ABBREVS:
            return True

    # Ambiguous cities require a Canadian province or abbreviation alongside them
    has_ambiguous_city = any(part in AMBIGUOUS_CITIES for part in parts)
    if has_ambiguous_city:
        has_province = any(
            part in CANADIAN_PROVINCES or part in CANADIAN_PROVINCE_ABBREVS
            for part in parts
        )
        if has_province or "canada" in normalized:
            return True

    if "us & canada" in normalized or "us/canada" in normalized or "u.s. & canada" in normalized:
        return True
    if "remote - global" in normalized or "remote (global)" in normalized:
        return True

    return False
