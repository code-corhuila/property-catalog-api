"""The routes of catalog (catalog-endpoint-fiches.md). Every operation is public: a
visitor browses without a session, and Booking reads E-06 without a credential
(ADR-015). The domain is never serialized: it is translated to these responses."""
import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from catalog.adapter.inbound.http.errors import validation_error
from catalog.application.port.inbound.catalog import CatalogQueries
from catalog.domain.model.busqueda import Busqueda, RangoFechas
from catalog.domain.model.propiedad import Propiedad

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class SearchParams(BaseModel):
    """The query of E-05, validated with Pydantic (security-rules.md). A value out of
    range is 400 naming the field (D-C3). An unknown parameter is ignored, as the fiche
    lists only these."""
    page: int = Field(1, ge=1, le=100_000)       # the upper bound keeps the skip bounded
    limit: int = Field(20, ge=1, le=100)
    ciudad: str | None = Field(None, min_length=1, max_length=100)
    fechaInicio: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    fechaFin: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    huespedes: int | None = Field(None, ge=1, le=20)


class Meta(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int


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


class PropiedadPage(BaseModel):
    data: list[PropiedadSummary]
    meta: Meta


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


def _dates(params: SearchParams) -> RangoFechas | None:
    """Both dates or neither; real days; the check-out after the check-in."""
    if (params.fechaInicio is None) != (params.fechaFin is None):
        missing = "fechaInicio" if params.fechaInicio is None else "fechaFin"
        raise validation_error([{"field": missing, "message": "fechaInicio and fechaFin go together"}])
    if params.fechaInicio is None:
        return None
    parsed, details = {}, []
    for name in ("fechaInicio", "fechaFin"):
        try:
            parsed[name] = date.fromisoformat(getattr(params, name))
        except ValueError:
            details.append({"field": name, "message": "must be a date yyyy-mm-dd"})
    if details:
        raise validation_error(details)
    if parsed["fechaFin"] <= parsed["fechaInicio"]:
        raise validation_error([{"field": "fechaFin", "message": "must be after fechaInicio"}])
    return RangoFechas(parsed["fechaInicio"], parsed["fechaFin"])


def build(queries: CatalogQueries) -> APIRouter:
    router = APIRouter()

    @router.get("/propiedades", response_model=PropiedadPage, response_model_exclude_none=True)
    def buscar(params: Annotated[SearchParams, Query()]) -> PropiedadPage:
        """E-05: one page of the Propiedades that match, newest first (HU-CAT-001)."""
        if params.ciudad is not None and not params.ciudad.strip():
            raise validation_error([{"field": "ciudad", "message": "must not be blank"}])
        busqueda = Busqueda(page=params.page, limit=params.limit,
                            ciudad=params.ciudad.strip() if params.ciudad else None,
                            huespedes=params.huespedes, fechas=_dates(params))
        pagina = queries.buscar(busqueda)
        return PropiedadPage(data=[to_summary(p) for p in pagina.items],
                             meta=Meta(page=pagina.page, limit=pagina.limit, total=pagina.total,
                                       totalPages=pagina.total_pages))

    @router.get("/propiedades/{propiedad_id}", response_model=PropiedadDetail, response_model_exclude_none=True)
    def get_propiedad(propiedad_id: str) -> PropiedadDetail:
        """E-06: the detail of a Propiedad."""
        if not UUID.match(propiedad_id):
            raise validation_error([{"field": "id", "message": "must be a UUID"}])
        return to_detail(queries.get_propiedad(propiedad_id.lower()))

    return router
