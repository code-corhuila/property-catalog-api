"""E-05 GET /propiedades over HTTP, with the in-memory repository (HU-CAT-001)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from catalog.adapter.inbound.http.app import create_app
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
from catalog.application.usecase.catalog import CatalogService
from catalog.domain.model.busqueda import Busqueda, RangoFechas, fold
from conftest import propiedad

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
# (city, capacity): 25 listings, the i-th created i days after START, so the last is the newest.
CITIES = [("Bogotá", 2), ("Cartagena", 6), ("Medellín", 4), ("Cartagena", 2), ("Cali", 8)] * 5


def listing(i: int, city: str, capacity: int):
    return propiedad(f"00000000-0000-4000-8000-{i:012d}", title=f"Listing {i}", city=city,
                     capacity=capacity, created_at=START + timedelta(days=i))


@pytest.fixture
def client() -> TestClient:
    repository = InMemoryPropiedadRepository(listing(i, c, n) for i, (c, n) in enumerate(CITIES))
    return TestClient(create_app(CatalogService(repository), repository.ping))


def ids(response) -> list[int]:
    return [int(p["id"][-12:]) for p in response.json()["data"]]


def test_a_search_by_city_and_dates_returns_a_page_of_summaries(client):
    """Scenario 1: each result shows a photo, the location and the price per night."""
    response = client.get("/api/v1/propiedades?ciudad=Cartagena&fechaInicio=2026-12-01&fechaFin=2026-12-05")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"page": 1, "limit": 20, "total": 10, "totalPages": 1}
    first = body["data"][0]
    assert set(first) == {"id", "titulo", "ciudad", "pais", "precioNocheCents", "moneda", "calificacion", "fotoPrincipal"}
    assert first["ciudad"] == "Cartagena" and first["precioNocheCents"] == 50_000_000


def test_the_city_matches_ignoring_case_and_accents(client):
    assert client.get("/api/v1/propiedades?ciudad=BOGOTA").json()["meta"]["total"] == 5
    assert client.get("/api/v1/propiedades?ciudad=medellin").json()["meta"]["total"] == 5


def test_huespedes_is_the_minimum_capacity(client):
    assert client.get("/api/v1/propiedades?huespedes=6").json()["meta"]["total"] == 10
    assert client.get("/api/v1/propiedades?ciudad=Cartagena&huespedes=3").json()["meta"]["total"] == 5


def test_no_match_is_200_with_an_empty_list_and_the_metadata(client):
    """Scenario 2."""
    response = client.get("/api/v1/propiedades?ciudad=Leticia")
    assert response.status_code == 200
    assert response.json() == {"data": [], "meta": {"page": 1, "limit": 20, "total": 0, "totalPages": 0}}


def test_the_list_goes_from_the_newest_to_the_oldest_in_bounded_pages(client):
    assert ids(client.get("/api/v1/propiedades")) == list(range(24, 4, -1))
    second = client.get("/api/v1/propiedades?page=2&limit=10")
    assert ids(second) == list(range(14, 4, -1))
    assert second.json()["meta"] == {"page": 2, "limit": 10, "total": 25, "totalPages": 3}
    assert len(client.get("/api/v1/propiedades?limit=100").json()["data"]) == 25


@pytest.mark.parametrize("query, field", [
    ("fechaInicio=2026-12-05&fechaFin=2026-12-05", "fechaFin"),     # scenario 3: end not after start
    ("fechaInicio=2026-12-05&fechaFin=2026-12-01", "fechaFin"),
    ("limit=101", "limit"),                                         # scenario 3: page size above 100
    ("limit=0", "limit"),
    ("page=0", "page"),
    ("huespedes=21", "huespedes"),
    ("huespedes=0", "huespedes"),
    ("huespedes=dos", "huespedes"),
    ("fechaInicio=2026-12-01", "fechaFin"),                         # both or neither
    ("fechaFin=2026-12-01", "fechaInicio"),
    ("fechaInicio=2026-02-30&fechaFin=2026-03-02", "fechaInicio"),  # not a real day
    ("fechaInicio=1/12/2026&fechaFin=2026-12-05", "fechaInicio"),
    ("ciudad=", "ciudad"),
    ("ciudad=%20%20", "ciudad"),
])
def test_an_invalid_search_is_400_naming_the_field(client, query, field):
    response = client.get(f"/api/v1/propiedades?{query}")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR" and field in [d["field"] for d in body["details"]]


def test_fold_ignores_case_and_accents():
    assert fold("Bogotá") == fold("BOGOTA") == "bogota"


def test_a_range_ends_after_it_starts():
    with pytest.raises(ValueError):
        RangoFechas(date(2026, 12, 5), date(2026, 12, 5))


def test_busqueda_admite_by_city_and_capacity():
    villa = propiedad("00000000-0000-4000-8000-000000000001")
    assert Busqueda(ciudad="cartagena", huespedes=6).admite(villa)
    assert not Busqueda(huespedes=7).admite(villa)
    assert not Busqueda(ciudad="Cali").admite(villa)
