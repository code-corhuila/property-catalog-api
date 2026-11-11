"""Composition root of the consumer of catalog.reservas (HU-CAT-004): a separate process of
this repository, from the same image, that receives no requests. Run with
`python -m apps.consumer`. It connects to RabbitMQ as the broker user catalog, which may
only read its queue (domain-events.md, "Broker topology"), and to MongoDB as catalog_app."""
import logging
import os
import signal
import time
from collections.abc import Mapping

import pika
from pika.exceptions import AMQPError

from apps.api.__main__ import mongo_client
from catalog.adapter.inbound.broker.consumer import ReservasConsumer
from catalog.adapter.inbound.http.app import configure_logging
from catalog.adapter.outbound.persistence.mongo_disponibilidad import MongoDisponibilidadStore
from catalog.application.usecase.disponibilidad import DisponibilidadService

log = logging.getLogger("catalog.consumer")


def broker_parameters(env: Mapping[str, str]) -> pika.ConnectionParameters:
    """Without its password the consumer does not start: it is a secret of the environment,
    never versioned (security-policy.md)."""
    if not env.get("BROKER_PASSWORD"):
        raise SystemExit("BROKER_PASSWORD is required: the password of the broker user catalog.")
    return pika.ConnectionParameters(
        host=env.get("BROKER_HOST", "rabbitmq"), port=int(env.get("BROKER_PORT", "5672")),
        credentials=pika.PlainCredentials(env.get("BROKER_USER", "catalog"), env["BROKER_PASSWORD"]),
        client_properties={"connection_name": "catalog-consumer"},
        heartbeat=int(env.get("BROKER_HEARTBEAT_S", "30")),                  # a dead link is noticed
        blocked_connection_timeout=int(env.get("BROKER_BLOCKED_TIMEOUT_S", "60")),
        connection_attempts=1, socket_timeout=int(env.get("BROKER_SOCKET_TIMEOUT_S", "10")))


def build_consumer(env: Mapping[str, str]) -> ReservasConsumer:
    if not env.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required: the database catalog of property-catalog-db.")
    store = MongoDisponibilidadStore(mongo_client(env, appname="catalog-consumer"))
    return ReservasConsumer(DisponibilidadService(store))


def _stop(*_):
    raise SystemExit(0)   # the message in hand is not acknowledged: the broker delivers it again


def main() -> None:
    env = os.environ
    configure_logging(env.get("LOG_LEVEL", "INFO"), service="catalog-consumer")
    logging.getLogger("pika").setLevel(logging.WARNING)    # its connection steps are noise
    parameters = broker_parameters(env)
    consumer = build_consumer(env)
    queue = env.get("BROKER_QUEUE", "catalog.reservas")
    reconnect_s = int(env.get("BROKER_RECONNECT_S", "5"))
    signal.signal(signal.SIGTERM, _stop)
    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            try:
                channel = connection.channel()
                channel.basic_qos(prefetch_count=1)     # one event at a time, in queue order
                channel.basic_consume(queue, consumer.on_message)
                log.info("consuming queue=%s", queue)
                channel.start_consuming()
            finally:
                if connection.is_open:
                    connection.close()
        except AMQPError as e:
            # The broker down or the link lost: what was not acknowledged comes back.
            log.warning("broker unavailable (%s); reconnecting in %ss", type(e).__name__, reconnect_s)
            time.sleep(reconnect_s)


if __name__ == "__main__":
    main()
