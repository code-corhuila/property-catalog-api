"""The consumer of catalog.reservas without a broker: reading the envelope, the retries and
what is acknowledged or rejected (HU-CAT-004; services/03-catalog/events.md)."""
import json
import logging

import pytest

from apps.consumer.__main__ import broker_parameters, build_consumer
from catalog.adapter.inbound.broker.consumer import ReservasConsumer, leer
from catalog.adapter.inbound.http.errors import CORRELATION_ID
from catalog.domain.model.evento_reserva import EventoInvalido, Resultado
from conftest import VILLA

EVENT_ID = "9f1c2b3a-1111-4c3e-9a2d-000000000001"
RESERVA = "b7e6c1d0-2222-4c3e-9a2d-000000000002"


def envelope(event_type="ReservaCreada", **payload) -> dict:
    """As booking-api writes it in its outbox (domain-events.md)."""
    body = {"reservaId": RESERVA, "propiedadId": VILLA}
    if event_type in ("ReservaCreada", "ReservaConfirmada"):
        body.update(fechaInicio="2027-09-10", fechaFin="2027-09-15")
    body.update(payload)
    return {"eventId": EVENT_ID, "eventType": event_type, "schemaVersion": 1, "aggregateId": RESERVA,
            "aggregateType": "Reserva", "occurredAt": "2027-08-17T14:30:00Z", "version": 1, "payload": body,
            "metadata": {"correlationId": "saga-123", "causationId": None, "userId": "c8f2a1b0-4444-4c3e-9a2d-000000000004"}}


def raw(value) -> bytes:
    return json.dumps(value).encode()


class Service:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def aplicar(self, evento):
        self.calls.append(CORRELATION_ID.get())
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_reads_the_envelope_of_booking():
    evento = leer(raw(envelope()))
    assert (evento.event_id, evento.event_type, evento.reserva_id, evento.propiedad_id) == \
        (EVENT_ID, "ReservaCreada", RESERVA, VILLA)
    assert evento.fecha_inicio.isoformat() == "2027-09-10" and evento.correlation_id == "saga-123"
    assert leer(raw(envelope("ReservaExpirada", motivo="TIMEOUT_PAGO_EXCEDIDO"))).fecha_inicio is None


@pytest.mark.parametrize("body", [
    b"not json", b"\xff", raw([]), raw({"eventId": EVENT_ID}),
    raw(envelope(reservaId="r-1")), raw(envelope(propiedadId="'; drop")), raw(envelope(fechaInicio="10/09/2027")),
    raw(envelope("ReservaCreada", fechaFin="2027-09-01")), raw(envelope("PagoAprobado")),
    raw({**envelope(), "eventId": None})])
def test_anything_else_is_not_an_event(body):
    with pytest.raises(EventoInvalido):
        leer(body)


def test_a_failure_to_save_is_retried_after_1_2_and_4_seconds_then_rejected():
    service, waits = Service(*[ConnectionError()] * 4), []
    assert ReservasConsumer(service).handle(raw(envelope()), None, waits.append) is False
    assert waits == [1, 2, 4] and len(service.calls) == 4


def test_it_is_acknowledged_when_a_retry_saves_it():
    service, waits = Service(ConnectionError(), Resultado.APLICADO), []
    assert ReservasConsumer(service).handle(raw(envelope()), None, waits.append) is True
    assert waits == [1]


@pytest.mark.parametrize("resultado, ack", [(Resultado.APLICADO, True), (Resultado.DUPLICADO, True),
                                            (Resultado.PROPIEDAD_DESCONOCIDA, False)])
def test_applied_and_duplicate_are_acknowledged_an_unknown_property_is_rejected_at_once(resultado, ack):
    service, waits = Service(resultado), []
    assert ReservasConsumer(service).handle(raw(envelope()), None, waits.append) is ack
    assert waits == []


def test_a_malformed_message_is_rejected_without_retries_and_without_its_body_in_the_log(caplog):
    service = Service()
    with caplog.at_level(logging.INFO):
        assert ReservasConsumer(service).handle(b'{"secret": "x"}', "amqp-cid", lambda s: None) is False
    assert service.calls == [] and "secret" not in caplog.text


def test_the_correlation_id_of_the_event_is_set_while_it_is_applied_and_cleared_after():
    service = Service(Resultado.APLICADO)
    ReservasConsumer(service).handle(raw(envelope()), "amqp-cid", lambda s: None)
    assert service.calls == ["saga-123"] and CORRELATION_ID.get() == ""


def test_without_its_secrets_the_consumer_does_not_start():
    with pytest.raises(SystemExit, match="BROKER_PASSWORD is required"):
        broker_parameters({})
    with pytest.raises(SystemExit, match="DATABASE_URL is required"):
        build_consumer({})
    assert broker_parameters({"BROKER_PASSWORD": "p"}).credentials.username == "catalog"
