"""The repository against the real engine, with the database catalog of
property-catalog-db applied: collections, roles and the seed (Annex C, level
"Integración"). Skipped, not failed, when TEST_DATABASE_URL is not set.

catalog_app may not delete, so these tests only read the listings of the seed.
"""
import os

import pytest

from apps.api.__main__ import build_repository
from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
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
