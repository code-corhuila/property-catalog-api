"""What catalog does with the events of Booking (HU-CAT-004)."""
from typing import Protocol

from catalog.domain.model.evento_reserva import EventoReserva, Resultado


class ActualizarDisponibilidad(Protocol):
    def aplicar(self, evento: EventoReserva) -> Resultado:
        """Applies the event once: a redelivery of the same eventId changes nothing."""
        ...
