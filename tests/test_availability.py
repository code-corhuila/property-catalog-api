"""HU-CAT-003: a search by dates leaves out a Propiedad already booked on them.

Scenario 2 assumes Catalog already applied the ReservaCreada event; the consumer that
does it is of tanda 3, so here the taken range is loaded directly. Scenario 1 (the
window before the event arrives) is Booking's: it still rejects the dates (INV-001).
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from catalog.adapter.inbound.http.app import create_app
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
from catalog.application.usecase.catalog import CatalogService
from catalog.domain.model.busqueda import RangoFechas
from conftest import propiedad

BOOKED = "00000000-0000-4000-8000-000000000001"
FREE = "00000000-0000-4000-8000-000000000002"


@pytest.fixture
def client() -> TestClient:
    repository = InMemoryPropiedadRepository([
        propiedad(BOOKED, unavailable_ranges=(("2026-12-10", "2026-12-15"),)),
        propiedad(FREE),
    ])
    return TestClient(create_app(CatalogService(repository), repository.ping))


def found(client, inicio: str, fin: str) -> set[str]:
    response = client.get(f"/api/v1/propiedades?ciudad=Cartagena&fechaInicio={inicio}&fechaFin={fin}")
    assert response.status_code == 200
    return {p["id"] for p in response.json()["data"]}


@pytest.mark.parametrize("inicio, fin", [
    ("2026-12-10", "2026-12-15"),   # the same dates
    ("2026-12-08", "2026-12-11"),   # ends inside the taken range
    ("2026-12-14", "2026-12-20"),   # starts on its last night
    ("2026-12-01", "2026-12-31"),   # contains it
])
def test_dates_that_overlap_a_taken_range_leave_the_propiedad_out(client, inicio, fin):
    assert found(client, inicio, fin) == {FREE}


@pytest.mark.parametrize("inicio, fin", [
    ("2026-12-15", "2026-12-18"),   # arrives the day the other guest leaves
    ("2026-12-05", "2026-12-10"),   # leaves the day the other guest arrives
])
def test_a_stay_that_only_touches_a_taken_range_does_not_overlap_it(client, inicio, fin):
    assert found(client, inicio, fin) == {BOOKED, FREE}


def test_without_dates_availability_does_not_filter(client):
    assert client.get("/api/v1/propiedades").json()["meta"]["total"] == 2


def test_the_overlap_is_half_open():
    stay = RangoFechas(date(2026, 12, 10), date(2026, 12, 15))
    assert stay.se_superpone_con(date(2026, 12, 14), date(2026, 12, 16))
    assert not stay.se_superpone_con(date(2026, 12, 15), date(2026, 12, 16))
    assert not stay.se_superpone_con(date(2026, 12, 1), date(2026, 12, 10))
