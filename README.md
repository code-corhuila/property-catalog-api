# property-catalog-api

> catalog bounded context: the service that searches and shows the Propiedades

Part of the **PMS Property** distributed system — team `pms-property`, Grupo 2.
Governance and documentation live in [`property-docs`](https://github.com/code-corhuila/property-docs).

`catalog-service` is the only service in **Python 3.12 + FastAPI** (ADR-011). It follows
the same hexagonal layers and the same public contract as the Java services: a consumer
cannot tell which language it is written in (Annex C).

| Operation | Fiche | Who calls it |
|---|---|---|
| `GET /api/v1/propiedades` | E-05 | The search of the portal: `ciudad` (ignoring case and accents), `huespedes` (minimum capacity), `fechaInicio`/`fechaFin`, `page`, `limit`; newest first |
| `GET /api/v1/propiedades/{id}` | E-06 | The portal, and Booking without a credential when it creates a Reserva (ADR-015) |
| `GET /health` | — | Answers without a token, outside `/api/v1` |

Every operation is public. The listings come from the seed of `property-catalog-db`;
this service never migrates.

## The consumer of Booking's events (HU-CAT-004)

A second process of the same image, `python -m apps.consumer` (service `catalog-consumer`
in `deploy/compose.yml`), reads the queue `catalog.reservas` as the broker user `catalog`
and keeps the taken ranges of each property, which the search by dates uses:

| Event | What changes in `unavailableRanges` |
|---|---|
| `ReservaCreada` | The range of the Reserva is added |
| `ReservaConfirmada` | Nothing: the range stays |
| `ReservaCancelada`, `ReservaExpirada` | The range of the Reserva is removed |

- **Once per event.** The `eventId` goes into `processed_events` in the same transaction as
  the change (MongoDB runs as a replica set for that); a redelivery changes nothing.
- **Acknowledged only after saving.** A failure to save is retried 3 times (1 s, 2 s, 4 s);
  then the message is rejected and goes to `catalog.reservas.dlq`, where it stays 7 days.
  A message that cannot be read goes there at once, and so does an event about a property
  that does not exist in the catalog: no retry would make it appear. The `.dlq` keeps both
  7 days for someone to review.
- **Logs.** One line per event with its `correlationId`, `eventType` and `eventId`; never the body.
- Catalog never calls Booking: the ranges are a projection, and Booking decides (ADR-015).
- **Eventually consistent (AP), by design.** Booking guarantees INV-001 with its exclusion
  constraint; catalog only reflects it. The broker does not promise order, but with a single
  outbox relay and `prefetch 1` here the events arrive in order in practice. If a late
  `ReservaCreada` came after its cancellation, it would only hide the property from the
  search for those dates: it can never allow a double booking. Freed Reservas are not recorded.

## Layout (Annex C, ADR-011 rule 2)

```
src/catalog/domain/model/              Propiedad and its typed error: no framework, no driver
src/catalog/application/port/inbound/  what catalog offers (CatalogQueries)
src/catalog/application/port/outbound/ what it needs (PropiedadRepository)
src/catalog/application/usecase/       CatalogService
src/catalog/adapter/inbound/http/      app.py (correlation, JSON logs, /health), errors.py, router.py
src/catalog/adapter/inbound/broker/    consumer.py: the messages of catalog.reservas, retries, dead-letter
src/catalog/adapter/outbound/persistence/  mongo.py (catalog_app, pool and limits), memory.py,
                                       mongo_disponibilidad.py (the ranges and processed_events)
deploy/Dockerfile, deploy/compose.yml  the image, the API and the consumer, included by property-infra-postgres
apps/api/__main__.py                   the composition root of the API: concrete types and limits
apps/consumer/__main__.py              the composition root of the consumer
tests/                                 pytest: core, HTTP contract, E-06, composition, MongoDB
```

The dependency rule is checked by a test that reads the imports of `domain/` and
`application/`: neither may import FastAPI, Pydantic, a driver or an adapter.

## Run it

```bash
pip install '.[test]'
python -m pytest
PERSISTENCE=memory python -m apps.api      # an empty catalog, on http://localhost:3002
```

Without `DATABASE_URL` the service does not start; `PERSISTENCE=memory` is for tests and
local development only, never an environment (norm 5.5.2). The variables are listed in
`.env.example`. In the platform it runs from `property-infra-postgres`, which includes
`deploy/compose.yml`, against `mongo:27017` as `catalog_app`.

The integration tests run only when `TEST_DATABASE_URL` points at a MongoDB with the
database `catalog` of `property-catalog-db` applied (Annex C); otherwise they are skipped.
The CI prepares one: MongoDB 7 as a single-node replica set (the consumer of Booking's
events writes in transactions), `catalog_app` with no role, and the changelog of
`property-catalog-db` from `develop`.

```bash
TEST_DATABASE_URL='mongodb://localhost:27017/catalog?directConnection=true' TEST_DATABASE_PASSWORD=<catalog_app password> python -m pytest
```

The tests of the consumer against a real broker also need `TEST_BROKER_URL`, a user that may
declare queues (`amqp://<user>:<password>@localhost:5672/%2F`): they declare their own queue
and its dead-letter queue, and delete them at the end. The CI starts RabbitMQ 3.13 for them.

## The common contract

- **Errors:** every error, including an unknown route, answers with the single envelope
  `{error, message, details?, traceId}`; the translation happens only in `errors.py`.
- **Correlation:** the `X-Correlation-Id` received (1 to 128 characters) is reused, or one is
  generated; it is returned, it is the `traceId`, and it is in every log line.
- **Logs:** one JSON object per line, with the field names of the Java services
  (`@timestamp`, `log.level`, `message`, `correlationId`). A 500 carries a neutral message;
  the detail goes only to the log.

## Branching

Three permanent branches. **None of them accepts a direct commit** — you enter through a child
branch and leave through a Pull Request.

```
develop  <--PR--  feat/... fix/... chore/...
qa       <--PR--  qa/...
main     <--PR--  release/...  hotfix/...
```

Promotion happens **by re-application** (`git cherry-pick -x`), never by merging one permanent
branch into another: `merge develop -> qa` and `merge qa -> main` do not exist in this model.

`main` requires **1 approval from `ariel5253`**. On `develop` and `qa` the team sets its own review
rule.

Full policy: `00-governance/branching-policy.md` in `property-docs`.
