"""A Booking event as catalog uses it: which Reserva, which property, which dates
(02-domain/domain-events.md; HU-CAT-004). Plain Python only (Annex C, the dependency rule).
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Cambio(Enum):
    TOMAR = "take"        # the range of the Reserva becomes taken
    MANTENER = "keep"     # nothing changes in the ranges
    LIBERAR = "free"      # the range of the Reserva, if any, is freed


# The four events of a Reserva that the queue catalog.reservas receives (domain-events.md,
# "Broker topology"), and what each one does to the taken ranges (06-data/models.md, rule 5).
CAMBIOS ={"ReservaCreada": Cambio.TOMAR, "ReservaConfirmada": Cambio.MANTENER,
           "ReservaCancelada": Cambio.LIBERAR, "ReservaExpirada": Cambio.LIBERAR}


class EventoInvalido(Exception):
    """The message is not one of the four events, or misses a field: no retry can fix it."""


@dataclass(frozen=True)
class EventoReserva:
    event_id: str
    event_type: str
    reserva_id: str
    propiedad_id: str
    correlation_id: str | None = None
    # Only ReservaCreada and ReservaConfirmada carry the dates; the others free by reservaId.
    fecha_inicio: date | None = None
    fecha_fin: date | None = None

    def __post_init__(self):
        if self.event_type not in CAMBIOS:
            raise EventoInvalido(f"catalog does not consume {self.event_type!r}")
        if self.cambio is Cambio.TOMAR:
            if self.fecha_inicio is None or self.fecha_fin is None:
                raise EventoInvalido("ReservaCreada without fechaInicio and fechaFin")
            if self.fecha_fin <= self.fecha_inicio:
                raise EventoInvalido("fechaFin must be after fechaInicio")

    @property
    def cambio(self) -> Cambio:
        return CAMBIOS[self.event_type]


class Resultado(Enum):
    APLICADO = "applied"                  # the change and its eventId, together
    DUPLICADO = "duplicate"               # the eventId was already in processed_events: nothing changes
    PROPIEDAD_DESCONOCIDA = "unknown-property"   # no such property: nothing changes, someone must look
