"""E-06 GET /propiedades/{id} over HTTP, with the in-memory repository (HU-CAT-002)."""
from conftest import CANDELARIA, MISSING, VILLA


def test_detail_has_the_fields_of_the_fiche_in_camel_case(client):
    """HU-CAT-002, scenario 1: photos, location, amenities, price per night and capacity."""
    response = client.get(f"/api/v1/propiedades/{VILLA}")
    assert response.status_code == 200
    assert response.json() == {
        "id": VILLA, "titulo": "Apartamento en Villa Del Mar", "ciudad": "Cartagena", "pais": "Colombia",
        "precioNocheCents": 50_000_000, "moneda": "COP", "calificacion": 4.9,
        "fotoPrincipal": "https://cdn.example/1.jpg", "capacidad": 6, "habitaciones": 3, "banos": 2,
        "metrosCuadrados": 120, "amenities": ["wifi", "pool"],
        "fotos": ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"],
        "anfitrion": {"id": "7c9e6679-7425-40de-944b-e07fc1f90000", "nombre": "Charith Chavarro",
                      "anfitrionDesde": 2021}}


def test_a_listing_with_only_the_required_fields_leaves_out_the_rest(client):
    body = client.get(f"/api/v1/propiedades/{CANDELARIA.upper()}").json()
    assert body["capacidad"] == 1 and body["amenities"] == [] and body["fotos"] == []
    assert not {"calificacion", "fotoPrincipal", "habitaciones", "banos", "metrosCuadrados"} & body.keys()
    assert body["anfitrion"] == {"id": "7c9e6679-7425-40de-944b-e07fc1f90023", "nombre": "Camilo Rojas"}


def test_an_unknown_propiedad_is_404_with_the_envelope(client):
    """HU-CAT-002, scenario 2."""
    response = client.get(f"/api/v1/propiedades/{MISSING}", headers={"X-Correlation-Id": "e2e-cat-404"})
    assert response.status_code == 404
    assert response.json() == {"error": "NOT_FOUND", "message": "the property does not exist", "traceId": "e2e-cat-404"}


def test_an_id_that_is_not_a_uuid_is_400_naming_the_field(client):
    response = client.get("/api/v1/propiedades/not-a-uuid")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR" and body["details"] == [{"field": "id", "message": "must be a UUID"}]
    assert body["traceId"] == response.headers["X-Correlation-Id"]
