"""Keeps the taken ranges of each property from the events of Booking (HU-CAT-004).

ReservaCreada takes the range of the Reserva; ReservaConfirmada keeps it (nothing changes
but the record of its eventId); ReservaCancelada and ReservaExpirada free it by reservaId
(06-data/models.md, rule 5; services/03-catalog/events.md). Catalog never calls Booking:
the ranges are a projection, and Booking decides (ADR-015, rule 6).
"""
from collections.abc import Callable
from datetime import date, datetime, timezone

from catalog.application.port.outbound.ports import DisponibilidadStore
from catalog.domain.model.evento_reserva import EventoReserva, Resultado


def _hoy() -> date:
    return datetime.now(timezone.utc).date()


class DisponibilidadService:
    def __init__(self, store: DisponibilidadStore, hoy: Callable[[], date] = _hoy):
        self._store = store
        self._hoy = hoy

    def aplicar(self, evento: EventoReserva) -> Resultado:
        # The array stays bounded (models.md, rule 4): a stay that ended frees nothing anymore.
        return self._store.aplicar(evento, self._hoy().isoformat())
