"""What catalog needs: where the listings and their taken ranges are stored."""
from typing import Protocol

from catalog.domain.model.busqueda import Busqueda, Pagina
from catalog.domain.model.evento_reserva import EventoReserva, Resultado
from catalog.domain.model.propiedad import Propiedad


class PropiedadRepository(Protocol):
    def find_by_id(self, propiedad_id: str) -> Propiedad | None:
        ...

    def search(self, busqueda: Busqueda) -> Pagina:
        ...

    def ping(self) -> bool:
        """True when the store answers; reported by /health."""
        ...


class DisponibilidadStore(Protocol):
    """Where the taken ranges are kept, with the eventIds already applied (06-data/models.md)."""

    def aplicar(self, evento: EventoReserva, hoy: str) -> Resultado:
        """Records evento.event_id in processed_events and makes evento.cambio on the ranges of
        the property, in one transaction; the ranges that ended by hoy are dropped too. A known
        eventId is DUPLICADO and an unknown property PROPIEDAD_DESCONOCIDA: nothing is written."""
        ...
