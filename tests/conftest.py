import pytest
from fastapi.testclient import TestClient

from catalog.adapter.inbound.http.app import create_app
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
from catalog.application.usecase.catalog import CatalogService
from catalog.domain.model.propiedad import Anfitrion, Propiedad

VILLA = "550e8400-e29b-41d4-a716-446655440000"
CANDELARIA = "550e8400-e29b-41d4-a716-446655440023"
MISSING = "550e8400-e29b-41d4-a716-4466554400ff"


def propiedad(id: str, **overrides) -> Propiedad:
    values = dict(id=id, title="Apartamento en Villa Del Mar", city="Cartagena", country="Colombia",
                  host=Anfitrion("7c9e6679-7425-40de-944b-e07fc1f90000", "Charith Chavarro", 2021),
                  capacity=6, price_per_night_cents=50_000_000, currency="COP", amenities=("wifi", "pool"),
                  photos=("https://cdn.example/1.jpg", "https://cdn.example/2.jpg"), rating=4.9,
                  bedrooms=3, bathrooms=2, area_m2=120)
    values.update(overrides)
    return Propiedad(**values)


@pytest.fixture
def listings() -> list[Propiedad]:
    # The second one has only the required fields, like the 24th listing of the seed.
    return [propiedad(VILLA),
            Propiedad(id=CANDELARIA, title="Habitación en La Candelaria", city="Bogotá", country="Colombia",
                      host=Anfitrion("7c9e6679-7425-40de-944b-e07fc1f90023", "Camilo Rojas"),
                      capacity=1, price_per_night_cents=9_000_000, currency="COP")]


@pytest.fixture
def client(listings) -> TestClient:
    repository = InMemoryPropiedadRepository(listings)
    return TestClient(create_app(CatalogService(repository), repository.ping), raise_server_exceptions=False)
