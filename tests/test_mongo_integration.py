"""The repository against the real engine, with the database catalog of
property-catalog-db applied: collections, roles and the seed (Annex C, level
"Integración"). Skipped, not failed, when TEST_DATABASE_URL is not set.

catalog_app may not delete, so these tests read the listings of the seed; the one that
loads a taken range removes it with $pull, an update catalog_writer allows.
"""
import os
from datetime import date

import pytest
from pymongo import MongoClient

from apps.api.__main__ import build_repository
from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
from catalog.domain.model.busqueda import Busqueda, RangoFechas
from conftest import CANDELARIA, MISSING, VILLA

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="TEST_DATABASE_URL is not set (Annex C)")


@pytest.fixture(scope="module")
def repository() -> MongoPropiedadRepository:
    return build_repository({"DATABASE_URL": os.environ.get("TEST_DATABASE_URL", ""),
                             "DATABASE_USER": os.environ.get("TEST_DATABASE_USER", "catalog_app"),
                             "DATABASE_PASSWORD": os.environ.get("TEST_DATABASE_PASSWORD", "")})


def test_the_database_answers_as_catalog_app(repository):
    assert repository.ping() is True


def test_a_listing_of_the_seed_comes_back_with_its_types(repository):
    villa = repository.find_by_id(VILLA)
    assert villa.title == "Apartamento en Villa Del Mar" and villa.city == "Cartagena"
    assert villa.price_per_night_cents == 50_000_000 and type(villa.price_per_night_cents) is int
    assert villa.capacity == 6 and villa.rating == 4.9 and villa.currency == "COP"
    assert villa.host.display_name == "Charith Chavarro" and villa.host.host_since == 2021
    assert villa.amenities == ("wifi", "pool", "parking") and villa.unavailable_ranges == ()


def test_a_listing_without_the_optional_fields_maps_them_to_none(repository):
    candelaria = repository.find_by_id(CANDELARIA)
    assert candelaria.capacity == 1 and candelaria.rating is None and candelaria.bedrooms is None


def test_an_unknown_id_is_none(repository):
    assert repository.find_by_id(MISSING) is None


def test_search_by_city_ignores_case_and_accents_with_the_collation_of_the_index(repository):
    page = repository.search(Busqueda(ciudad="BOGOTA"))
    assert page.total == 6 and {p.city for p in page.items} == {"Bogotá"}


def test_search_by_capacity_and_pages_newest_first(repository):
    assert repository.search(Busqueda(huespedes=8)).total == 4     # capacities 8, 12, 10 and 8
    first = repository.search(Busqueda(limit=5))
    assert first.total == 24 and first.items[0].id == VILLA and len(first.items) == 5
    last = repository.search(Busqueda(page=5, limit=5))
    assert len(last.items) == 4 and last.items[-1].id == CANDELARIA     # the oldest listing


def test_search_by_dates_leaves_out_a_listing_with_an_overlapping_range(repository):
    """HU-CAT-003, scenario 2, with the range loaded as the consumer of tanda 3 will."""
    client = MongoClient(os.environ["TEST_DATABASE_URL"], username=os.environ.get("TEST_DATABASE_USER", "catalog_app"),
                         password=os.environ.get("TEST_DATABASE_PASSWORD"))
    properties = client.get_default_database()["properties"]
    taken = {"reservationId": "ffffffff-ffff-4fff-8fff-000000000147", "startDate": "2027-03-10", "endDate": "2027-03-15"}
    properties.update_one({"_id": VILLA}, {"$push": {"unavailableRanges": taken}})
    try:
        def ids(inicio, fin):
            page = repository.search(Busqueda(ciudad="Cartagena", fechas=RangoFechas(inicio, fin)))
            return {p.id for p in page.items}
        assert VILLA not in ids(date(2027, 3, 14), date(2027, 3, 16))
        assert VILLA in ids(date(2027, 3, 15), date(2027, 3, 18))       # arrives the day the other leaves
        assert len(ids(date(2027, 3, 14), date(2027, 3, 16))) == 5        # the other five of Cartagena
    finally:
        properties.update_one({"_id": VILLA}, {"$pull": {"unavailableRanges": {"reservationId": taken["reservationId"]}}})
        client.close()
