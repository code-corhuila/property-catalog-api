"""The Propiedad of catalog: a read model of a listing (06-data/models.md).

Plain Python only: this module imports no web framework and no database driver
(Annex C, the dependency rule; ADR-011, rule 2).
"""
from dataclasses import dataclass, field


class PropiedadNoEncontrada(Exception):
    """The requested Propiedad does not exist in the catalog."""

    def __init__(self, propiedad_id: str):
        super().__init__(f"the property {propiedad_id} does not exist")
        self.propiedad_id = propiedad_id


@dataclass(frozen=True)
class Anfitrion:
    id: str
    display_name: str
    host_since: int | None = None


@dataclass(frozen=True)
class Propiedad:
    id: str
    title: str
    city: str
    country: str
    host: Anfitrion
    capacity: int
    price_per_night_cents: int
    currency: str
    amenities: tuple[str, ...] = ()
    photos: tuple[str, ...] = ()
    rating: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    area_m2: int | None = None
    # Ranges [start, end) taken by a PENDIENTE or CONFIRMADA Reserva, as ISO dates.
    unavailable_ranges: tuple[tuple[str, str], ...] = field(default=())
