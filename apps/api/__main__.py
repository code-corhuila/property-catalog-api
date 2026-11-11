"""Composition root of catalog-api (Annex C): the only place that knows every concrete
type and declares every limit. Run with `python -m apps.api`."""
import logging
import os
from collections.abc import Mapping

import uvicorn
from pymongo import MongoClient

from catalog.adapter.inbound.http.app import configure_logging, create_app
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
from catalog.application.usecase.catalog import CatalogService

log = logging.getLogger("catalog.app")


def build_repository(env: Mapping[str, str]):
    """mongo (default) or memory. memory is for tests and local development only, never
    an environment (norm 5.5.2). mongo without DATABASE_URL does not start."""
    persistence = env.get("PERSISTENCE", "mongo")
    if persistence == "memory":
        log.warning("PERSISTENCE=memory: nothing persists; for tests and local development only")
        return InMemoryPropiedadRepository()
    if persistence != "mongo":
        raise SystemExit(f"PERSISTENCE must be mongo or memory, not {persistence!r}")
    if not env.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required: the database catalog of property-catalog-db. "
                         "PERSISTENCE=memory is for tests and local development only.")
    return MongoPropiedadRepository(mongo_client(env))


def mongo_client(env: Mapping[str, str], appname: str = "catalog-api") -> MongoClient:
    """One pool per process with its limits (Annex C, numeral 5.3.10). The client connects
    lazily: with the database down the service starts and /health reports it."""
    return MongoClient(
        env["DATABASE_URL"], username=env.get("DATABASE_USER") or None, password=env.get("DATABASE_PASSWORD") or None,
        appname=appname, tz_aware=True,
        maxPoolSize=int(env.get("DB_POOL_MAX", "10")),                 # size of the pool
        waitQueueTimeoutMS=int(env.get("DB_POOL_WAIT_MS", "5000")),    # waiting for a connection
        timeoutMS=int(env.get("DB_TIMEOUT_MS", "5000")))               # each operation, as a whole


def main() -> None:
    env = os.environ
    configure_logging(env.get("LOG_LEVEL", "INFO"))
    repository = build_repository(env)
    app = create_app(CatalogService(repository), repository.ping)
    # Limits (Annex C, numeral 5.3.10). Reading the headers has no setting in uvicorn: the
    # gateway imposes it (client_header_timeout of NGINX).
    uvicorn.run(app, host="0.0.0.0", port=int(env.get("PORT", "3002")),
                timeout_keep_alive=int(env.get("HTTP_KEEP_ALIVE_S", "60")),
                timeout_graceful_shutdown=int(env.get("SHUTDOWN_TIMEOUT_S", "20")),
                log_config=None, access_log=False)


if __name__ == "__main__":
    main()
