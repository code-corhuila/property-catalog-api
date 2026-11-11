"""HU-CAT-004 end to end inside catalog: a real RabbitMQ and the real MongoDB (Annex C,
level "Integración"). Skipped when TEST_BROKER_URL or TEST_DATABASE_URL is not set.

The test declares its own queue, with the arguments of catalog.reservas in
property-infra-rabbitmq (dead-letter to <queue>.dlq through the default exchange), and
deletes both at the end. Each message is taken with basic_get and handed to the callback
of pika, which acknowledges or rejects it on the real channel.
"""
import json
import os
import uuid
from datetime import date

import pika
import pytest

from apps.api.__main__ import mongo_client
from catalog.adapter.inbound.broker.consumer import ReservasConsumer
from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
from catalog.adapter.outbound.persistence.mongo_disponibilidad import MongoDisponibilidadStore
from catalog.application.usecase.disponibilidad import DisponibilidadService
from catalog.domain.model.busqueda import Busqueda, RangoFechas
from conftest import VILLA

pytestmark = pytest.mark.skipif(not (os.environ.get("TEST_BROKER_URL") and os.environ.get("TEST_DATABASE_URL")),
                                reason="TEST_BROKER_URL and TEST_DATABASE_URL are needed (Annex C)")


@pytest.fixture(scope="module")
def mongo():
    client = mongo_client({"DATABASE_URL": os.environ.get("TEST_DATABASE_URL", ""),
                           "DATABASE_USER": os.environ.get("TEST_DATABASE_USER", "catalog_app"),
                           "DATABASE_PASSWORD": os.environ.get("TEST_DATABASE_PASSWORD", "")})
    yield client
    client.close()


@pytest.fixture
def broker():
    connection = pika.BlockingConnection(pika.URLParameters(os.environ.get("TEST_BROKER_URL", "")))
    channel = connection.channel()
    queue = f"test.catalog.reservas.{uuid.uuid4().hex[:8]}"
    channel.queue_declare(f"{queue}.dlq", durable=True)
    channel.queue_declare(queue, durable=True, arguments={
        "x-dead-letter-exchange": "", "x-dead-letter-routing-key": f"{queue}.dlq"})
    yield channel, queue
    channel.queue_delete(queue)
    channel.queue_delete(f"{queue}.dlq")
    connection.close()


@pytest.fixture
def consume(broker, mongo):
    """Publishes the bodies to the queue and lets the consumer take every message there."""
    channel, queue = broker
    consumer = ReservasConsumer(DisponibilidadService(MongoDisponibilidadStore(mongo), hoy=lambda: date(2027, 3, 1)),
                                delays=(0.01, 0.02, 0.04))

    def run(*bodies: bytes):
        for body in bodies:
            channel.basic_publish("", queue, body, pika.BasicProperties(content_type="application/json", delivery_mode=2))
        while True:
            method, properties, body = channel.basic_get(queue)
            if method is None:
                return
            consumer.on_message(channel, method, properties, body)
    return run


def message(event_type: str, reserva: str, event_id: str | None = None) -> bytes:
    payload = {"reservaId": reserva, "propiedadId": VILLA}
    if event_type in ("ReservaCreada", "ReservaConfirmada"):
        payload.update(fechaInicio="2027-03-10", fechaFin="2027-03-15")
    return json.dumps({"eventId": event_id or str(uuid.uuid4()), "eventType": event_type, "schemaVersion": 1,
                       "payload": payload, "metadata": {"correlationId": "test-hu-cat-004"}}).encode()


def taken(mongo) -> set[str]:
    villa = mongo.get_default_database()["properties"].find_one({"_id": VILLA})
    return {r["reservationId"] for r in villa["unavailableRanges"]}


def counts(broker) -> tuple[int, int]:
    channel, queue = broker
    return (channel.queue_declare(queue, passive=True).method.message_count,
            channel.queue_declare(f"{queue}.dlq", passive=True).method.message_count)


def test_scenarios_1_and_2_created_takes_the_dates_confirmed_keeps_them_cancelled_frees_them(broker, consume, mongo):
    reserva = str(uuid.uuid4())
    consume(message("ReservaCreada", reserva), message("ReservaConfirmada", reserva))
    assert reserva in taken(mongo)
    consume(message("ReservaCancelada", reserva))
    assert reserva not in taken(mongo) and counts(broker) == (0, 0)


def test_scenario_2_an_expired_reserva_frees_its_dates(broker, consume, mongo):
    reserva = str(uuid.uuid4())
    consume(message("ReservaCreada", reserva), message("ReservaExpirada", reserva))
    assert reserva not in taken(mongo) and counts(broker) == (0, 0)


def test_scenario_3_a_duplicate_is_acknowledged_and_changes_nothing(broker, consume, mongo):
    reserva, creada = str(uuid.uuid4()), str(uuid.uuid4())
    consume(message("ReservaCreada", reserva, creada), message("ReservaCancelada", reserva),
            message("ReservaCreada", reserva, creada))      # the first one again, after the cancellation
    assert reserva not in taken(mongo) and counts(broker) == (0, 0)


def test_hu_cat_003_scenario_2_after_the_event_the_search_by_dates_leaves_the_property_out(consume, mongo):
    def ids():
        page = MongoPropiedadRepository(mongo).search(
            Busqueda(ciudad="Cartagena", fechas=RangoFechas(date(2027, 3, 14), date(2027, 3, 16))))
        return {p.id for p in page.items}
    reserva = str(uuid.uuid4())
    consume(message("ReservaCreada", reserva))
    try:
        assert VILLA not in ids()
    finally:
        consume(message("ReservaCancelada", reserva))
    assert VILLA in ids()


def test_a_malformed_message_ends_in_the_dead_letter_queue_with_its_x_death(broker, consume):
    consume(b'{"eventType": "ReservaCreada", "payload": {}}')
    assert counts(broker) == (0, 1)
    channel, queue = broker
    method, properties, body = channel.basic_get(f"{queue}.dlq", auto_ack=True)
    assert body == b'{"eventType": "ReservaCreada", "payload": {}}'
    assert properties.headers["x-death"][0]["queue"] == queue
    assert properties.headers["x-death"][0]["reason"] == "rejected"
