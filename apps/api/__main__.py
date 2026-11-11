"""Composition root of catalog-api (Annex C): the only place that knows every concrete
type and declares every limit. Run with `python -m apps.api`."""
import logging
import os
from collections.abc import Mapping

import uvicorn

from catalog.adapter.inbound.http.app import configure_logging, create_app
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
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
    raise SystemExit("PERSISTENCE=mongo is not available in this version: use PERSISTENCE=memory")


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
