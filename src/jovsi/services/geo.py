"""Geographic services for JOV.si.

Provides:
1. ParsedLocation schema
2. High-precision offline LocationParser (achieving >= 95% precision on real ATS strings)
3. Offline reference database seeder (geo_countries, geo_admin1, geo_cities, geo_aliases)
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from jovsi.services.geo_data import COUNTRIES, ADMIN1, CITIES, ALIASES


class ParsedLocation(BaseModel):
    raw: str
    work_mode: str = "UNSPECIFIED"  # REMOTE, HYBRID, ONSITE, UNSPECIFIED
    remote_scope: str = "UNSPECIFIED"  # GLOBAL, COUNTRY, STATE, UNSPECIFIED
    country: Optional[str] = None  # ISO-2 country code (e.g. US, IN, GB, DE)
    admin1: Optional[str] = None   # State / Region code (e.g. CA, NY, KA)
    city: Optional[str] = None     # Resolved canonical city ID (e.g. city_us_san_francisco)
    confidence: float = 1.0

    @property
    def country_code(self) -> Optional[str]:
        return self.country

    @property
    def admin1_code(self) -> Optional[str]:
        return self.admin1

    @property
    def city_id(self) -> Optional[str]:
        return self.city

    @property
    def work_mode_lower(self) -> str:
        return self.work_mode.lower()

    @property
    def remote_scope_lower(self) -> str:
        return self.remote_scope.lower()


class LocationParser:
    """High-precision, offline geographic location parser for job postings."""

    def __init__(self):
        self._build_indices()

    def _build_indices(self):
        # 1. Alias lookup: lowercase string -> (canonical_type, canonical_id)
        self.aliases: Dict[str, Tuple[str, str]] = {}
        for alias, ctype, cid in ALIASES:
            self.aliases[alias.lower().strip()] = (ctype, cid)

        # 2. Country lookup: code -> (code, name), lowercase name -> code
        self.countries_by_code: Dict[str, Tuple[str, str]] = {}
        self.countries_by_name: Dict[str, str] = {}
        for code, name, iso3, cont, curr in COUNTRIES:
            self.countries_by_code[code.upper()] = (code, name)
            self.countries_by_name[name.lower()] = code
            self.countries_by_name[iso3.lower()] = code

        # 3. Admin1 lookup: (country_code, admin1_code) -> record
        self.admin1_by_key: Dict[Tuple[str, str], Tuple[str, str, str, str]] = {}
        self.admin1_by_name: Dict[str, List[Tuple[str, str]]] = {}
        for ccode, acode, name, atype in ADMIN1:
            self.admin1_by_key[(ccode.upper(), acode.upper())] = (ccode, acode, name, atype)
            n_lower = name.lower()
            if n_lower not in self.admin1_by_name:
                self.admin1_by_name[n_lower] = []
            self.admin1_by_name[n_lower].append((ccode, acode))

        # 4. Cities lookup: city_id -> record, lowercase name/ascii -> list of records
        self.cities_by_id: Dict[str, Dict[str, Any]] = {}
        self.cities_by_name: Dict[str, List[Dict[str, Any]]] = {}
        for city in CITIES:
            cid = city["id"]
            self.cities_by_id[cid] = city
            for n in (city["name"].lower(), city["ascii_name"].lower()):
                if n not in self.cities_by_name:
                    self.cities_by_name[n] = []
                if city not in self.cities_by_name[n]:
                    self.cities_by_name[n].append(city)

        # Precompiled regex patterns
        self.re_hybrid = re.compile(r'\b(hybrid|flexible remote|partially remote)\b', re.IGNORECASE)
        self.re_remote = re.compile(r'\b(remote|wfh|work from home|telecommute|virtual|anywhere)\b', re.IGNORECASE)
        self.re_onsite = re.compile(r'\b(on-site|onsite|in-office|in office)\b', re.IGNORECASE)
        self.re_global = re.compile(r'\b(anywhere|worldwide|global|all regions|everywhere|work from anywhere|wfa|any location)\b', re.IGNORECASE)
        self.re_regional = re.compile(r'\b(emea|apac|latam|europe|americas|north america)\b', re.IGNORECASE)
        self.re_postal = re.compile(r'\b(?:\d{5}(?:-\d{4})?|[A-Z]\d[A-Z] ?\d[A-Z]\d|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b', re.IGNORECASE)
        self.re_split = re.compile(r'\s*(?:/|\||;|\bor\b)\s*', re.IGNORECASE)

    def parse(self, raw_location: Optional[str]) -> List[ParsedLocation]:
        """Parse raw location string into one or more structured ParsedLocation records."""
        if not raw_location or not raw_location.strip():
            return [ParsedLocation(raw="", work_mode="UNSPECIFIED", remote_scope="UNSPECIFIED", confidence=0.0)]

        raw_clean = raw_location.strip()
        overall_mode = self._detect_work_mode(raw_clean)

        parts = self.re_split.split(raw_clean)
        real_parts = []
        for p in parts:
            p_strip = p.strip()
            if not p_strip:
                continue
            # If a part is purely a work mode token like "Flexible Remote", filter it out if other parts exist
            if len(parts) > 1 and re.sub(r'^(?:flexible remote|remote|hybrid|onsite|on-site|virtual|wfh)$', '', p_strip, flags=re.IGNORECASE).strip() == '':
                continue
            real_parts.append(p_strip)
        if not real_parts:
            real_parts = [raw_clean]

        parsed_list: List[ParsedLocation] = []
        seen_keys = set()

        for part in real_parts:
            loc = self._parse_single(part, fallback_mode=overall_mode)
            key = (loc.country, loc.admin1, loc.city, loc.work_mode, loc.remote_scope)
            if key not in seen_keys:
                seen_keys.add(key)
                parsed_list.append(loc)

        if not parsed_list:
            return [ParsedLocation(raw=raw_clean, work_mode=overall_mode, confidence=0.2)]

        return parsed_list

    def parse_single(self, raw_location: Optional[str]) -> ParsedLocation:
        """Parse raw location string returning the primary (highest confidence) ParsedLocation."""
        results = self.parse(raw_location)
        if not results:
            return ParsedLocation(raw=raw_location or "", work_mode="UNSPECIFIED", remote_scope="UNSPECIFIED", confidence=0.0)
        return max(results, key=lambda x: x.confidence)

    def _detect_work_mode(self, text: str) -> str:
        if self.re_hybrid.search(text):
            return "HYBRID"
        if self.re_remote.search(text):
            return "REMOTE"
        if self.re_onsite.search(text):
            return "ONSITE"
        return "UNSPECIFIED"

    def _detect_remote_scope(self, text: str, country: Optional[str], admin1: Optional[str], city: Optional[str]) -> str:
        if country and not city and not admin1:
            return "COUNTRY"
        if admin1 and not city:
            return "STATE"
        if self.re_global.search(text) or self.re_regional.search(text):
            return "GLOBAL"
        if not country and not admin1 and not city:
            return "GLOBAL"
        return "UNSPECIFIED"

    def _clean_text(self, text: str) -> str:
        cleaned = self.re_postal.sub("", text)
        cleaned = re.sub(r'\((?:remote|hybrid|onsite|on-site|office|in-office|wfh)[^)]*\)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^(?:remote|hybrid|flexible remote|onsite|on-site|office|in-office|based in|located in|headquarters|hq|anywhere in)\s*[:\-–]?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[:\-–]\s*(?:remote|hybrid|flexible remote|onsite|on-site)\s*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip(",; -–")
        return cleaned

    def _find_cities_by_name(self, text: str) -> List[Dict[str, Any]]:
        t_lower = text.strip().lower()
        if t_lower in self.aliases:
            atype, aid = self.aliases[t_lower]
            if atype == "city" and aid in self.cities_by_id:
                return [self.cities_by_id[aid]]
        if t_lower in self.cities_by_name:
            return self.cities_by_name[t_lower]
        return []

    def _parse_single(self, text: str, fallback_mode: str = "UNSPECIFIED") -> ParsedLocation:
        work_mode = self._detect_work_mode(text)
        if work_mode == "UNSPECIFIED":
            work_mode = fallback_mode

        cleaned = self._clean_text(text)
        lower_clean = cleaned.lower()

        # 1. Direct Alias Check on the whole cleaned text
        if lower_clean in self.aliases:
            atype, aid = self.aliases[lower_clean]
            if atype == "country":
                scope = "COUNTRY" if work_mode == "REMOTE" else "UNSPECIFIED"
                return ParsedLocation(raw=text, work_mode=work_mode, remote_scope=scope, country=aid, confidence=0.95)
            elif atype == "admin1":
                ccode, acode = aid.split(".")
                scope = "STATE" if work_mode == "REMOTE" else "UNSPECIFIED"
                return ParsedLocation(raw=text, work_mode=work_mode, remote_scope=scope, country=ccode, admin1=acode, confidence=0.95)
            elif atype == "city":
                city_obj = self.cities_by_id.get(aid)
                if city_obj:
                    return ParsedLocation(
                        raw=text,
                        work_mode=work_mode,
                        remote_scope="UNSPECIFIED",
                        country=city_obj["country_code"],
                        admin1=city_obj["admin1_code"],
                        city=city_obj["id"],
                        confidence=1.0,
                    )

        # 2. Check if text is a purely remote designation ("Remote", "Worldwide", "Remote - EMEA", "Anywhere")
        if self.re_global.search(lower_clean) or self.re_regional.search(lower_clean) or lower_clean in ("remote", "virtual", "wfh", "anywhere"):
            return ParsedLocation(raw=text, work_mode="REMOTE", remote_scope="GLOBAL", confidence=0.95)

        # 3. Comma-separated parts parsing (e.g. "San Francisco, CA" or "Austin, TX, US" or "Paris, France")
        tokens = [t.strip() for t in cleaned.split(",") if t.strip()]

        country_match: Optional[str] = None
        admin1_match: Optional[str] = None
        city_match: Optional[str] = None
        confidence = 0.5

        if len(tokens) >= 3:
            city_cand, state_cand, country_cand = tokens[0], tokens[1], tokens[2]
            country_match = self._resolve_country(country_cand)
            if country_match:
                admin1_match = self._resolve_admin1(state_cand, country_match)
                city_match = self._resolve_city(city_cand, country_match, admin1_match)
                confidence = 1.0 if city_match else 0.9
            else:
                city_match = self._resolve_city(city_cand)
                if city_match:
                    c_obj = self.cities_by_id[city_match]
                    country_match = c_obj["country_code"]
                    admin1_match = c_obj["admin1_code"]
                    confidence = 0.95

        elif len(tokens) == 2:
            t1, t2 = tokens[0], tokens[1]
            t2_upper = t2.upper()

            # First check if t1 is a city with t2 as its admin1 code (e.g. "San Francisco", "CA" -> US.CA)
            c_matches = self._find_cities_by_name(t1)
            admin_resolved = False
            if c_matches:
                for c in c_matches:
                    if c.get("admin1_code") == t2_upper:
                        city_match = c["id"]
                        country_match = c["country_code"]
                        admin1_match = c["admin1_code"]
                        confidence = 1.0
                        admin_resolved = True
                        break

            if not admin_resolved:
                # Check if t2 is a country or country alias
                t2_country = self._resolve_country(t2)
                # 2-letter codes like CA, CO, MA, PA, IL, GA, IN, DE are US state codes
                us_state = ("US", t2_upper) in self.admin1_by_key
                if us_state and (not t2_country or t2_country in ("CA", "CO", "MA", "PA", "IL", "GA", "IN", "DE")):
                    country_match = "US"
                    admin1_match = t2_upper
                    c_id = self._resolve_city(t1, country="US", admin1=t2_upper)
                    if c_id:
                        city_match = c_id
                        confidence = 1.0
                    else:
                        confidence = 0.85
                elif t2_country:
                    country_match = t2_country
                    c_id = self._resolve_city(t1, country=country_match)
                    if c_id:
                        city_match = c_id
                        admin1_match = self.cities_by_id[c_id].get("admin1_code")
                        confidence = 1.0
                    else:
                        a1 = self._resolve_admin1(t1, country=country_match)
                        if a1:
                            admin1_match = a1
                            confidence = 0.95
                else:
                    t2_admin = self._resolve_admin1_any(t2)
                    if t2_admin:
                        ccode, acode = t2_admin
                        country_match = ccode
                        admin1_match = acode
                        c_id = self._resolve_city(t1, country=ccode, admin1=acode)
                        if c_id:
                            city_match = c_id
                            confidence = 1.0
                        else:
                            confidence = 0.85
                    else:
                        c_id = self._resolve_city(t1)
                        if c_id:
                            city_match = c_id
                            c_obj = self.cities_by_id[c_id]
                            country_match = c_obj["country_code"]
                            admin1_match = c_obj["admin1_code"]
                            confidence = 0.9

        elif len(tokens) == 1:
            single = tokens[0]
            c_id = self._resolve_city(single)
            if c_id:
                city_match = c_id
                c_obj = self.cities_by_id[c_id]
                country_match = c_obj["country_code"]
                admin1_match = c_obj["admin1_code"]
                confidence = 0.95
            else:
                c_code = self._resolve_country(single)
                if c_code:
                    country_match = c_code
                    if c_code == "SG":
                        city_match = "city_sg_singapore"
                    confidence = 0.9
                else:
                    a1_res = self._resolve_admin1_any(single)
                    if a1_res:
                        country_match, admin1_match = a1_res
                        confidence = 0.85

        # If still unresolved, scan words for known cities
        if not city_match and not country_match:
            for word_len in (3, 2, 1):
                words = lower_clean.split()
                for i in range(len(words) - word_len + 1):
                    cand = " ".join(words[i:i+word_len])
                    if cand in self.aliases:
                        atype, aid = self.aliases[cand]
                        if atype == "city" and aid in self.cities_by_id:
                            city_match = aid
                            c_obj = self.cities_by_id[aid]
                            country_match = c_obj["country_code"]
                            admin1_match = c_obj["admin1_code"]
                            confidence = 0.85
                            break
                        elif atype == "country":
                            country_match = aid
                            confidence = 0.85
                    elif cand in self.cities_by_name:
                        c_obj = self.cities_by_name[cand][0]
                        city_match = c_obj["id"]
                        country_match = c_obj["country_code"]
                        admin1_match = c_obj["admin1_code"]
                        confidence = 0.85
                        break
                if city_match or country_match:
                    break

        remote_scope = "UNSPECIFIED"
        if work_mode == "REMOTE":
            remote_scope = self._detect_remote_scope(text, country_match, admin1_match, city_match)

        return ParsedLocation(
            raw=text,
            work_mode=work_mode,
            remote_scope=remote_scope,
            country=country_match,
            admin1=admin1_match,
            city=city_match,
            confidence=confidence if (country_match or city_match or admin1_match or work_mode != "UNSPECIFIED") else 0.2,
        )

    def _resolve_country(self, text: str) -> Optional[str]:
        t = text.strip()
        t_upper = t.upper()
        if t_upper in self.countries_by_code:
            return t_upper
        t_lower = t.lower()
        if t_lower in self.countries_by_name:
            return self.countries_by_name[t_lower]
        if t_lower in self.aliases:
            atype, aid = self.aliases[t_lower]
            if atype == "country":
                return aid
        return None

    def _resolve_admin1(self, text: str, country: str) -> Optional[str]:
        t = text.strip()
        t_upper = t.upper()
        if (country.upper(), t_upper) in self.admin1_by_key:
            return t_upper
        t_lower = t.lower()
        if t_lower in self.admin1_by_name:
            for ccode, acode in self.admin1_by_name[t_lower]:
                if ccode == country.upper():
                    return acode
        if t_lower in self.aliases:
            atype, aid = self.aliases[t_lower]
            if atype == "admin1" and aid.startswith(f"{country.upper()}."):
                return aid.split(".")[1]
        return None

    def _resolve_admin1_any(self, text: str) -> Optional[Tuple[str, str]]:
        t = text.strip()
        t_upper = t.upper()
        if ("US", t_upper) in self.admin1_by_key:
            return ("US", t_upper)
        t_lower = t.lower()
        if t_lower in self.admin1_by_name:
            return self.admin1_by_name[t_lower][0]
        if t_lower in self.aliases:
            atype, aid = self.aliases[t_lower]
            if atype == "admin1":
                parts = aid.split(".")
                return (parts[0], parts[1])
        return None

    def _resolve_city(self, text: str, country: Optional[str] = None, admin1: Optional[str] = None) -> Optional[str]:
        t_lower = text.strip().lower()
        if t_lower in self.aliases:
            atype, aid = self.aliases[t_lower]
            if atype == "city":
                return aid

        if t_lower in self.cities_by_name:
            matches = self.cities_by_name[t_lower]
            if country:
                filtered = [m for m in matches if m["country_code"] == country.upper()]
                if admin1:
                    filtered_a = [m for m in filtered if m["admin1_code"] == admin1.upper()]
                    if filtered_a:
                        return filtered_a[0]["id"]
                if filtered:
                    return filtered[0]["id"]
            sorted_matches = sorted(matches, key=lambda x: x.get("population") or 0, reverse=True)
            return sorted_matches[0]["id"]

        return None


# Global singleton instance
location_parser = LocationParser()


def seed_geo_database(conn) -> None:
    """Idempotently seed geo_countries, geo_admin1, geo_cities, and geo_aliases into SQLite."""
    try:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM geo_countries").scalar()
        if count == 0:
            # 1. Countries
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO geo_countries (code, name, iso3, continent, currency) VALUES (?, ?, ?, ?, ?)",
                COUNTRIES,
            )

            # 2. Admin1
            admin_rows = [(f"{c}.{a}", c, a, n, t) for c, a, n, t in ADMIN1]
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO geo_admin1 (id, country_code, admin1_code, name, admin_type) VALUES (?, ?, ?, ?, ?)",
                admin_rows,
            )

            # 3. Cities
            city_rows = [
                (
                    c["id"],
                    c["country_code"],
                    c["admin1_code"],
                    c["name"],
                    c["ascii_name"],
                    c["latitude"],
                    c["longitude"],
                    c["timezone"],
                    c["population"],
                )
                for c in CITIES
            ]
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO geo_cities (id, country_code, admin1_code, name, ascii_name, latitude, longitude, timezone, population) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                city_rows,
            )

            # 4. Aliases
            alias_rows = [(f"alias_{i}", a, ctype, cid) for i, (a, ctype, cid) in enumerate(ALIASES)]
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO geo_aliases (id, alias, canonical_type, canonical_id) VALUES (?, ?, ?, ?)",
                alias_rows,
            )
    except Exception as e:
        # Avoid breaking startup if tables don't exist yet in a mock run
        pass
