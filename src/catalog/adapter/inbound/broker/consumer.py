"""The consumer of the queue catalog.reservas (HU-CAT-004; ADR-013; domain-events.md,
"Broker topology"; services/03-catalog/events.md).

Each message is the envelope of a Booking event. It is acknowledged only after its change
and its eventId are saved. A message that cannot be read is rejected at once: no retry can
fix it. A failure to save is retried 3 times, after 1 s, 2 s and 4 s; then the message is
rejected and the broker moves it to catalog.reservas.dlq. A message there is a stale
availability: someone must look at it.
"""
import json
import logging
import uuid
from collections.abc import Callable, Sequence
from datetime import date

from catalog.adapter.inbound.http.errors import CORRELATION_ID
from catalog.application.port.inbound.disponibilidad import ActualizarDisponibilidad
from catalog.domain.model.evento_reserva import EventoInvalido, EventoReserva, Resultado

log = logging.getLogger("catalog.consumer")
RETRY_DELAYS_S = (1, 2, 4)


def leer(body: bytes) -> EventoReserva:
    """The envelope of domain-events.md, checked field by field: the ids must be UUIDs and
    the dates yyyy-mm-dd. Anything else is EventoInvalido."""
    try:
        envelope = json.loads(body)
        payload = envelope["payload"]
        correlation_id = (envelope.get("metadata") or {}).get("correlationId")
        fechas = {}
        if "fechaInicio" in payload or "fechaFin" in payload:
            fechas = dict(fecha_inicio=date.fromisoformat(payload["fechaInicio"]),
                          fecha_fin=date.fromisoformat(payload["fechaFin"]))
        return EventoReserva(
            event_id=str(uuid.UUID(envelope["eventId"])), event_type=envelope["eventType"],
            reserva_id=str(uuid.UUID(payload["reservaId"])), propiedad_id=str(uuid.UUID(payload["propiedadId"])),
            correlation_id=correlation_id if isinstance(correlation_id, str) and 0 < len(correlation_id) <= 128 else None,
            **fechas)
    except EventoInvalido:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise EventoInvalido(f"not an event of a Reserva: {type(e).__name__}") from None


class ReservasConsumer:
    def __init__(self, service: ActualizarDisponibilidad, delays: Sequence[float] = RETRY_DELAYS_S):
        self._service = service
        self._delays = tuple(delays)

    def on_message(self, channel, method, properties, body: bytes) -> None:
        """The callback of pika. It waits between retries with connection.sleep, which keeps
        the heartbeats of the connection going."""
        if self.handle(body, properties.correlation_id, channel.connection.sleep):
            channel.basic_ack(method.delivery_tag)
        else:
            channel.basic_nack(method.delivery_tag, requeue=False)    # to catalog.reservas.dlq

    def handle(self, body: bytes, correlation_id: str | None, sleep: Callable[[float], None]) -> bool:
        """True to acknowledge, False to reject. Every log line carries the correlationId of
        the event (metadata.correlationId, or the property of the message); never the body."""
        token = CORRELATION_ID.set(correlation_id or "")
        try:
            try:
                evento = leer(body)
            except EventoInvalido as e:
                log.error("rejected to the dead-letter queue: %s", e)
                return False
            CORRELATION_ID.set(evento.correlation_id or correlation_id or "")
            return self._apply(evento, sleep)
        finally:
            CORRELATION_ID.reset(token)

    def _apply(self, evento: EventoReserva, sleep: Callable[[float], None]) -> bool:
        for retry, delay in enumerate((*self._delays, None)):
            try:
                resultado = self._service.aplicar(evento)
            except Exception as e:
                if delay is None:
                    log.error("rejected to the dead-letter queue after %d retries eventType=%s eventId=%s: %s",
                              retry, evento.event_type, evento.event_id, type(e).__name__)
                    return False
                log.warning("not applied eventType=%s eventId=%s: %s; retry %d in %ss",
                            evento.event_type, evento.event_id, type(e).__name__, retry + 1, delay)
                sleep(delay)
                continue
            if resultado is Resultado.PROPIEDAD_DESCONOCIDA:
                log.error("rejected to the dead-letter queue: unknown property eventType=%s eventId=%s propiedadId=%s",
                          evento.event_type, evento.event_id, evento.propiedad_id)
                return False
            log.info("event %s eventType=%s eventId=%s propiedadId=%s", resultado.value,
                     evento.event_type, evento.event_id, evento.propiedad_id)
            return True
        return False
