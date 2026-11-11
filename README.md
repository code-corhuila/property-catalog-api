# property-catalog-api

> catalog bounded context: the service that searches and shows the Propiedades

Part of the **PMS Property** distributed system — team `pms-property`, Grupo 2.
Governance and documentation live in [`property-docs`](https://github.com/code-corhuila/property-docs).

`catalog-service` is the only service in **Python 3.12 + FastAPI** (ADR-011). It follows
the same hexagonal layers and the same public contract as the Java services: a consumer
cannot tell which language it is written in (Annex C).

| Operation | Fiche | Who calls it |
|---|---|---|
| `GET /api/v1/propiedades/{id}` | E-06 | The portal, and Booking without a credential when it creates a Reserva (ADR-015) |
| `GET /health` | — | Answers without a token, outside `/api/v1` |

Every operation is public. Read-only in MVP 1: the listings come from the seed of
`property-catalog-db`; this service never migrates.

## Layout (Annex C, ADR-011 rule 2)

```
src/catalog/domain/model/              Propiedad and its typed error: no framework, no driver
src/catalog/application/port/inbound/  what catalog offers (CatalogQueries)
src/catalog/application/port/outbound/ what it needs (PropiedadRepository)
src/catalog/application/usecase/       CatalogService
src/catalog/adapter/inbound/http/      app.py (correlation, JSON logs, /health), errors.py, router.py
src/catalog/adapter/outbound/persistence/  mongo.py (catalog_app, pool and limits), memory.py
deploy/Dockerfile, deploy/compose.yml  the image and this service, included by property-infra-postgres
apps/api/__main__.py                   the composition root: concrete types and limits
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
The CI prepares one: MongoDB 7, `catalog_app` with no role, and the changelog of
`property-catalog-db` from `develop`.

```bash
TEST_DATABASE_URL='mongodb://localhost:27017/catalog?directConnection=true' TEST_DATABASE_PASSWORD=<catalog_app password> python -m pytest
```

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
