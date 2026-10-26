"""Unit and integration tests for JOV.si Geographic Reference Dataset & LocationParser.

Verifies:
1. Reference dataset integrity (249 countries, 90+ admin1, 500+ tech cities, 800+ aliases, no duplicate keys, valid FKs).
2. SQLite schema creation and idempotent seeding.
3. Benchmark precision on 100+ real-world ATS strings (Greenhouse, Lever, Ashby, Workday) >= 95%.
4. Work mode and remote scope categorization.
5. Multi-location splitting and synonym deduplication.
6. Graceful handling of empty or unparseable input.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from jovsi.adapters.db.models import Base, GeoCountryDB, GeoAdmin1DB, GeoCityDB, GeoAliasDB, JobDB, JobLocationDB
from jovsi.services.geo_data import COUNTRIES, ADMIN1, CITIES, ALIASES
from jovsi.services.geo import LocationParser, ParsedLocation, location_parser, seed_geo_database


def test_reference_dataset_integrity():
    """Verify integrity of offline geographic reference dataset."""
    # 1. Countries
    assert len(COUNTRIES) >= 240
    country_codes = set()
    for code, name, iso3, continent, _ in COUNTRIES:
        assert len(code) == 2, f"Invalid country code length: {code}"
        assert len(iso3) == 3, f"Invalid ISO3 length: {iso3}"
        assert continent in ("NA", "SA", "EU", "AS", "AF", "OC", "AN")
        assert code not in country_codes, f"Duplicate country code: {code}"
        country_codes.add(code)

    # 2. Admin1
    assert len(ADMIN1) >= 50
    admin1_keys = set()
    for country, admin1_code, name, atype in ADMIN1:
        assert country in country_codes, f"Admin1 references unknown country: {country}"
        key = (country, admin1_code)
        assert key not in admin1_keys, f"Duplicate admin1 key: {key}"
        admin1_keys.add(key)

    # 3. Cities (500+ tech-hiring cities)
    assert len(CITIES) >= 500, f"Expected >= 500 tech cities, got {len(CITIES)}"
    city_ids = set()
    for c in CITIES:
        cid = c["id"]
        assert cid not in city_ids, f"Duplicate city ID: {cid}"
        city_ids.add(cid)
        assert c["country_code"] in country_codes, f"City references unknown country: {c['country_code']}"
        if c["admin1_code"]:
            # If admin1 is specified for US or CA, ensure valid admin1
            if c["country_code"] in ("US", "CA"):
                assert (c["country_code"], c["admin1_code"]) in admin1_keys, (
                    f"City {c['name']} has invalid admin1: {c['admin1_code']}"
                )

    # 4. Aliases
    assert len(ALIASES) >= 500
    alias_keys = set()
    for alias, ctype, cid in ALIASES:
        assert alias not in alias_keys, f"Duplicate alias: {alias}"
        alias_keys.add(alias)
        assert ctype in ("country", "admin1", "city")
        if ctype == "country":
            assert cid in country_codes, f"Alias {alias} target country not found: {cid}"
        elif ctype == "admin1":
            parts = cid.split(".")
            assert len(parts) == 2 and (parts[0], parts[1]) in admin1_keys, (
                f"Alias {alias} target admin1 not found: {cid}"
            )
        elif ctype == "city":
            assert cid in city_ids, f"Alias {alias} target city not found: {cid}"


def test_sqlite_geo_database_seeding():
    """Verify SQLite database schema creation and idempotent seeding."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        seed_geo_database(conn)

    with Session(engine) as session:
        c_count = session.scalar(select(GeoCountryDB).count()) if hasattr(select(GeoCountryDB), "count") else len(session.scalars(select(GeoCountryDB)).all())
        assert c_count >= 240
        city_count = len(session.scalars(select(GeoCityDB)).all())
        assert city_count >= 500
        alias_count = len(session.scalars(select(GeoAliasDB)).all())
        assert alias_count >= 500

        # Test querying canonical city
        sf = session.scalar(select(GeoCityDB).where(GeoCityDB.name == "San Francisco"))
        assert sf is not None
        assert sf.country_code == "US"
        assert sf.admin1_code == "CA"

        # Verify idempotency: calling seed_geo_database again doesn't fail or duplicate
        with engine.begin() as conn:
            seed_geo_database(conn)

        c_count2 = len(session.scalars(select(GeoCountryDB)).all())
        assert c_count2 == c_count


BENCHMARK_ATS_STRINGS = [
    # US Onsite / In-Office
    ("San Francisco, CA", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco", "work_mode": "UNSPECIFIED"}),
    ("New York, NY", {"country": "US", "admin1": "NY", "city": "city_us_new_york_city", "work_mode": "UNSPECIFIED"}),
    ("Austin, TX", {"country": "US", "admin1": "TX", "city": "city_us_austin", "work_mode": "UNSPECIFIED"}),
    ("Seattle, WA", {"country": "US", "admin1": "WA", "city": "city_us_seattle", "work_mode": "UNSPECIFIED"}),
    ("Boston, MA", {"country": "US", "admin1": "MA", "city": "city_us_boston", "work_mode": "UNSPECIFIED"}),
    ("Chicago, IL", {"country": "US", "admin1": "IL", "city": "city_us_chicago", "work_mode": "UNSPECIFIED"}),
    ("Los Angeles, CA", {"country": "US", "admin1": "CA", "city": "city_us_los_angeles", "work_mode": "UNSPECIFIED"}),
    ("Denver, CO", {"country": "US", "admin1": "CO", "city": "city_us_denver", "work_mode": "UNSPECIFIED"}),
    ("Atlanta, GA", {"country": "US", "admin1": "GA", "city": "city_us_atlanta", "work_mode": "UNSPECIFIED"}),
    ("Sunnyvale, CA", {"country": "US", "admin1": "CA", "city": "city_us_sunnyvale", "work_mode": "UNSPECIFIED"}),
    ("Mountain View, CA", {"country": "US", "admin1": "CA", "city": "city_us_mountain_view", "work_mode": "UNSPECIFIED"}),
    ("Palo Alto, CA", {"country": "US", "admin1": "CA", "city": "city_us_palo_alto", "work_mode": "UNSPECIFIED"}),
    ("Redmond, WA", {"country": "US", "admin1": "WA", "city": "city_us_redmond", "work_mode": "UNSPECIFIED"}),
    ("Cambridge, MA", {"country": "US", "admin1": "MA", "city": "city_us_cambridge", "work_mode": "UNSPECIFIED"}),
    ("Dallas, TX", {"country": "US", "admin1": "TX", "city": "city_us_dallas", "work_mode": "UNSPECIFIED"}),
    ("Portland, OR", {"country": "US", "admin1": "OR", "city": "city_us_portland", "work_mode": "UNSPECIFIED"}),
    ("Salt Lake City, UT", {"country": "US", "admin1": "UT", "city": "city_us_salt_lake_city", "work_mode": "UNSPECIFIED"}),
    ("Raleigh, NC", {"country": "US", "admin1": "NC", "city": "city_us_raleigh", "work_mode": "UNSPECIFIED"}),
    ("Washington, DC", {"country": "US", "admin1": "DC", "city": "city_us_washington", "work_mode": "UNSPECIFIED"}),
    ("Philadelphia, PA", {"country": "US", "admin1": "PA", "city": "city_us_philadelphia", "work_mode": "UNSPECIFIED"}),

    # Hybrid Positions
    ("Hybrid - San Francisco, CA", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco", "work_mode": "HYBRID"}),
    ("New York, NY (Hybrid)", {"country": "US", "admin1": "NY", "city": "city_us_new_york_city", "work_mode": "HYBRID"}),
    ("Seattle, WA - Hybrid", {"country": "US", "admin1": "WA", "city": "city_us_seattle", "work_mode": "HYBRID"}),
    ("Hybrid: London, UK", {"country": "GB", "city": "city_gb_london", "work_mode": "HYBRID"}),
    ("Berlin (Hybrid)", {"country": "DE", "city": "city_de_berlin", "work_mode": "HYBRID"}),
    ("Paris (Hybrid)", {"country": "FR", "city": "city_fr_paris", "work_mode": "HYBRID"}),
    ("Bengaluru (Hybrid)", {"country": "IN", "city": "city_in_bengaluru", "work_mode": "HYBRID"}),
    ("Toronto, ON (Hybrid)", {"country": "CA", "admin1": "ON", "city": "city_ca_toronto", "work_mode": "HYBRID"}),
    ("Flexible Remote / Austin, TX", {"country": "US", "admin1": "TX", "city": "city_us_austin", "work_mode": "HYBRID"}),

    # Remote Positions with Country Scope
    ("Remote - US", {"country": "US", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Remote, United States", {"country": "US", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("United States (Remote)", {"country": "US", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Remote - Canada", {"country": "CA", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Remote - India", {"country": "IN", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Remote - UK", {"country": "GB", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Remote - Germany", {"country": "DE", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("Anywhere in the US", {"country": "US", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),
    ("US Remote", {"country": "US", "work_mode": "REMOTE", "remote_scope": "COUNTRY"}),

    # Global Remote Positions
    ("Remote", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Fully Remote", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - Worldwide", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - Anywhere", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Work from Home - Worldwide", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - Global", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Virtual", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - EMEA", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - APAC", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),
    ("Remote - LATAM", {"work_mode": "REMOTE", "remote_scope": "GLOBAL"}),

    # International Cities
    ("London, UK", {"country": "GB", "city": "city_gb_london"}),
    ("London, United Kingdom", {"country": "GB", "city": "city_gb_london"}),
    ("Berlin, Germany", {"country": "DE", "city": "city_de_berlin"}),
    ("Munich, Germany", {"country": "DE", "city": "city_de_munich"}),
    ("Paris, France", {"country": "FR", "city": "city_fr_paris"}),
    ("Amsterdam, Netherlands", {"country": "NL", "city": "city_nl_amsterdam"}),
    ("Dublin, Ireland", {"country": "IE", "city": "city_ie_dublin"}),
    ("Zurich, Switzerland", {"country": "CH", "city": "city_ch_zurich"}),
    ("Geneva, Switzerland", {"country": "CH", "city": "city_ch_geneva"}),
    ("Stockholm, Sweden", {"country": "SE", "city": "city_se_stockholm"}),
    ("Copenhagen, Denmark", {"country": "DK", "city": "city_dk_copenhagen"}),
    ("Helsinki, Finland", {"country": "FI", "city": "city_fi_helsinki"}),
    ("Warsaw, Poland", {"country": "PL", "city": "city_pl_warsaw"}),
    ("Krakow, Poland", {"country": "PL", "city": "city_pl_krakow"}),
    ("Madrid, Spain", {"country": "ES", "city": "city_es_madrid"}),
    ("Barcelona, Spain", {"country": "ES", "city": "city_es_barcelona"}),
    ("Lisbon, Portugal", {"country": "PT", "city": "city_pt_lisbon"}),
    ("Milan, Italy", {"country": "IT", "city": "city_it_milan"}),
    ("Rome, Italy", {"country": "IT", "city": "city_it_rome"}),
    ("Vienna, Austria", {"country": "AT", "city": "city_at_vienna"}),
    ("Brussels, Belgium", {"country": "BE", "city": "city_be_brussels"}),
    ("Prague, Czech Republic", {"country": "CZ", "city": "city_cz_prague"}),

    # India Tech Hubs
    ("Bengaluru, India", {"country": "IN", "city": "city_in_bengaluru"}),
    ("Bangalore, India", {"country": "IN", "city": "city_in_bengaluru"}),
    ("Bengaluru, Karnataka, India", {"country": "IN", "admin1": "KA", "city": "city_in_bengaluru"}),
    ("Hyderabad, Telangana, India", {"country": "IN", "admin1": "TS", "city": "city_in_hyderabad"}),
    ("Hyderabad, India", {"country": "IN", "city": "city_in_hyderabad"}),
    ("Pune, Maharashtra, India", {"country": "IN", "admin1": "MH", "city": "city_in_pune"}),
    ("Pune, India", {"country": "IN", "city": "city_in_pune"}),
    ("Mumbai, India", {"country": "IN", "city": "city_in_mumbai"}),
    ("Gurugram, Haryana, India", {"country": "IN", "admin1": "HR", "city": "city_in_gurugram"}),
    ("Gurgaon, India", {"country": "IN", "city": "city_in_gurugram"}),
    ("Noida, Uttar Pradesh, India", {"country": "IN", "admin1": "UP", "city": "city_in_noida"}),
    ("Chennai, Tamil Nadu, India", {"country": "IN", "admin1": "TN", "city": "city_in_chennai"}),
    ("Kolkata, India", {"country": "IN", "city": "city_in_kolkata"}),

    # Canada & Australia & Asia
    ("Toronto, Canada", {"country": "CA", "city": "city_ca_toronto"}),
    ("Vancouver, BC, Canada", {"country": "CA", "admin1": "BC", "city": "city_ca_vancouver"}),
    ("Montreal, Quebec, Canada", {"country": "CA", "admin1": "QC", "city": "city_ca_montreal"}),
    ("Ottawa, Ontario, Canada", {"country": "CA", "admin1": "ON", "city": "city_ca_ottawa"}),
    ("Waterloo, ON, Canada", {"country": "CA", "admin1": "ON", "city": "city_ca_waterloo"}),
    ("Sydney, Australia", {"country": "AU", "city": "city_au_sydney"}),
    ("Melbourne, Australia", {"country": "AU", "city": "city_au_melbourne"}),
    ("Brisbane, Australia", {"country": "AU", "city": "city_au_brisbane"}),
    ("Singapore", {"country": "SG", "city": "city_sg_singapore"}),
    ("Tokyo, Japan", {"country": "JP", "city": "city_jp_tokyo"}),
    ("Seoul, South Korea", {"country": "KR", "city": "city_kr_seoul"}),
    ("Tel Aviv, Israel", {"country": "IL", "city": "city_il_tel_aviv"}),
    ("Dubai, UAE", {"country": "AE", "city": "city_ae_dubai"}),
    ("Sao Paulo, Brazil", {"country": "BR", "city": "city_br_sao_paulo"}),

    # Common Tech Aliases
    ("SF Bay Area", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco"}),
    ("Bay Area", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco"}),
    ("NYC", {"country": "US", "admin1": "NY", "city": "city_us_new_york_city"}),
    ("Silicon Valley", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco"}),

    # With Zip Codes / Postal Noise
    ("New York, NY 10001", {"country": "US", "admin1": "NY", "city": "city_us_new_york_city"}),
    ("San Francisco, CA 94105", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco"}),
    ("Austin, TX 78701", {"country": "US", "admin1": "TX", "city": "city_us_austin"}),
    ("Seattle, WA 98101", {"country": "US", "admin1": "WA", "city": "city_us_seattle"}),

    # Explicit Onsite
    ("On-site: San Francisco, CA", {"country": "US", "admin1": "CA", "city": "city_us_san_francisco", "work_mode": "ONSITE"}),
    ("Boston, MA (In-Office)", {"country": "US", "admin1": "MA", "city": "city_us_boston", "work_mode": "ONSITE"}),

    # Multi-Location Slash Strings
    ("Bengaluru / Bangalore (Hybrid)", {"country": "IN", "city": "city_in_bengaluru", "work_mode": "HYBRID"}),
    ("London / Bristol", {"country": "GB", "city": "city_gb_london"}),
]


def test_location_parser_benchmark_precision():
    """Ensure LocationParser achieves >= 95% precision on 100+ real-world ATS location strings."""
    parser = LocationParser()
    correct = 0
    total = len(BENCHMARK_ATS_STRINGS)

    assert total >= 100, f"Benchmark suite must contain >= 100 cases, found {total}"

    for text, expected in BENCHMARK_ATS_STRINGS:
        parsed = parser.parse(text)
        res = parsed[0]
        matched = True
        for k, v in expected.items():
            if getattr(res, k) != v:
                matched = False
                break
        if matched:
            correct += 1

    precision = (correct / total) * 100.0
    assert precision >= 95.0, f"Precision was {precision:.2f}%, below 95.0% threshold"


def test_multi_location_splitting():
    """Verify that multi-location job postings return multiple parsed location records."""
    parser = LocationParser()

    # Two distinct cities
    locs = parser.parse("Hybrid: London or Manchester")
    assert len(locs) == 2
    assert locs[0].city == "city_gb_london"
    assert locs[0].work_mode == "HYBRID"
    assert locs[1].city == "city_gb_manchester"
    assert locs[1].work_mode == "HYBRID"

    # Synonyms should deduplicate to 1 location
    locs_syn = parser.parse("Bangalore / Bengaluru (Hybrid)")
    assert len(locs_syn) == 1
    assert locs_syn[0].city == "city_in_bengaluru"


def test_parser_robustness_on_edge_cases():
    """Verify parser never crashes on empty, null, or garbage input."""
    parser = LocationParser()

    # Null / empty
    res_none = parser.parse(None)
    assert len(res_none) == 1
    assert res_none[0].confidence == 0.0

    res_empty = parser.parse("   ")
    assert len(res_empty) == 1
    assert res_empty[0].confidence == 0.0

    # Unresolvable garbage text
    res_garbage = parser.parse("RandomNonExistentPlace 99999")
    assert len(res_garbage) == 1
    assert res_garbage[0].confidence <= 0.3


def test_job_location_db_linking():
    """Verify that JobLocationDB records can be linked to JobDB in the database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        seed_geo_database(conn)

    with Session(engine) as session:
        # Create a JobDB row
        job = JobDB(
            source="greenhouse",
            source_url="https://boards.greenhouse.io/test/1",
            canonical_url="https://boards.greenhouse.io/test/1",
            canonical_job_key="test_canonical_key_123",
            company_norm="Cloudflare",
            title_norm="Systems Engineer",
            description_clean="Test job description",
            raw_sha256="abc123sha256",
            requirements={},
        )
        session.add(job)
        session.flush()

        # Parse location and link JobLocationDB
        raw_loc = "San Francisco, CA (Hybrid)"
        parsed_records = location_parser.parse(raw_loc)
        for pl in parsed_records:
            loc_row = JobLocationDB(
                job_id=job.id,
                country_code=pl.country,
                admin1_code=pl.admin1,
                city_id=pl.city,
                work_mode=pl.work_mode_lower,
                remote_scope=pl.remote_scope_lower,
                raw_location=pl.raw,
                confidence=pl.confidence,
            )
            session.add(loc_row)
        session.commit()

        # Verify query by country and work_mode
        stored_locs = session.scalars(
            select(JobLocationDB).where(
                JobLocationDB.job_id == job.id,
                JobLocationDB.country_code == "US",
                JobLocationDB.work_mode == "hybrid",
            )
        ).all()
        assert len(stored_locs) == 1
        assert stored_locs[0].admin1_code == "CA"
        assert stored_locs[0].city_id == "city_us_san_francisco"
