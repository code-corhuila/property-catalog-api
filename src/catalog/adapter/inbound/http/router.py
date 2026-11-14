"""The routes of catalog (catalog-endpoint-fiches.md). Every operation is public: a
visitor browses without a session, and Booking reads E-06 without a credential
(ADR-015). The domain is never serialized: it is translated to these responses."""
import re

from fastapi import APIRouter
from pydantic import BaseModel

from catalog.adapter.inbound.http.errors import validation_error
from catalog.application.port.inbound.catalog import CatalogQueries
from catalog.domain.model.propiedad import Propiedad

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class AnfitrionResponse(BaseModel):
    id: str
    nombre: str
    anfitrionDesde: int | None = None


class PropiedadSummary(BaseModel):
    id: str
    titulo: str
    ciudad: str
    pais: str
    precioNocheCents: int
    moneda: str
    calificacion: float | None = None
    fotoPrincipal: str | None = None


class PropiedadDetail(PropiedadSummary):
    # Booking reads precioNocheCents, moneda and capacidad: they never change shape (ADR-015).
    capacidad: int
    habitaciones: int | None = None
    banos: int | None = None
    metrosCuadrados: int | None = None
    amenities: list[str]
    fotos: list[str]
    anfitrion: AnfitrionResponse


def to_summary(p: Propiedad) -> PropiedadSummary:
    return PropiedadSummary(**_summary_fields(p))


def _summary_fields(p: Propiedad) -> dict:
    return {"id": p.id, "titulo": p.title, "ciudad": p.city, "pais": p.country,
            "precioNocheCents": p.price_per_night_cents, "moneda": p.currency,
            "calificacion": p.rating, "fotoPrincipal": p.photos[0] if p.photos else None}


def to_detail(p: Propiedad) -> PropiedadDetail:
    return PropiedadDetail(
        **_summary_fields(p), capacidad=p.capacity, habitaciones=p.bedrooms, banos=p.bathrooms,
        metrosCuadrados=p.area_m2, amenities=list(p.amenities), fotos=list(p.photos),
        anfitrion=AnfitrionResponse(id=p.host.id, nombre=p.host.display_name, anfitrionDesde=p.host.host_since))


def build(queries: CatalogQueries) -> APIRouter:
    router = APIRouter()

    @router.get("/propiedades/{propiedad_id}", response_model=PropiedadDetail, response_model_exclude_none=True)
    def get_propiedad(propiedad_id: str) -> PropiedadDetail:
        """E-06: the detail of a Propiedad."""
        if not UUID.match(propiedad_id):
            raise validation_error([{"field": "id", "message": "must be a UUID"}])
        return to_detail(queries.get_propiedad(propiedad_id.lower()))

    return router
