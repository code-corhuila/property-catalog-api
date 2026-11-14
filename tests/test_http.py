"""The contract checks of Annex C that apply to a public service, over HTTP (level "HTTP")."""
import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from apps.api.__main__ import build_repository
from catalog.adapter.inbound.http.app import JsonFormatter, create_app
from catalog.adapter.inbound.http.errors import CORRELATION_ID
from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@pytest.fixture
def app():
    app = create_app(object(), lambda: True)

    # Two routes for the tests only: a typed parameter, and a failure nobody expected.
    @app.get("/api/v1/probe")
    def probe(limit: int):
        return {"limit": limit}

    @app.get("/api/v1/boom")
    def boom():
        raise RuntimeError("connection refused by db-host-17")

    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_health_answers_without_a_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" and response.json()["dependencies"] == {"database": "ok"}


def test_health_reports_a_database_that_is_down_inside_the_200():
    def down() -> bool:
        raise ConnectionError("no server")
    body = TestClient(create_app(object(), down)).get("/health").json()
    assert body["status"] == "degraded" and body["dependencies"]["database"] == "down"


def test_an_unknown_route_is_404_with_the_envelope(client):
    response = client.get("/api/v1/nothing-here", headers={"X-Correlation-Id": "route-1"})
    assert response.status_code == 404
    assert response.json() == {"error": "NOT_FOUND", "message": "the route does not exist", "traceId": "route-1"}


def test_a_method_the_route_does_not_have_answers_with_the_envelope(client):
    response = client.post("/health")
    assert response.status_code == 405 and response.json()["error"] == "NOT_FOUND"


def test_an_invalid_parameter_is_400_naming_the_field(client):
    response = client.get("/api/v1/probe?limit=many", headers={"X-Correlation-Id": "val-1"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "VALIDATION_ERROR" and body["traceId"] == "val-1"
    assert [d["field"] for d in body["details"]] == ["limit"]


@pytest.mark.parametrize("sent", ["abc-123", "x" * 128])
def test_the_correlation_id_received_is_returned_and_is_the_trace_id(client, sent):
    response = client.get("/api/v1/nothing-here", headers={"X-Correlation-Id": sent})
    assert response.headers["X-Correlation-Id"] == sent
    assert response.json()["traceId"] == sent


@pytest.mark.parametrize("headers", [{}, {"X-Correlation-Id": "   "}, {"X-Correlation-Id": "x" * 129}])
def test_without_a_usable_correlation_id_the_service_generates_one(client, headers):
    response = client.get("/api/v1/nothing-here", headers=headers)
    generated = response.headers["X-Correlation-Id"]
    assert UUID.match(generated) and response.json()["traceId"] == generated


def test_an_unexpected_error_is_a_neutral_500_and_the_detail_goes_only_to_the_log(client, caplog):
    with caplog.at_level(logging.ERROR, logger="catalog.http"):
        response = client.get("/api/v1/boom", headers={"X-Correlation-Id": "boom-1"})
    assert response.status_code == 500
    assert response.json() == {"error": "INTERNAL_ERROR", "message": "internal server error", "traceId": "boom-1"}
    assert response.headers["X-Correlation-Id"] == "boom-1"
    assert "db-host-17" in caplog.text


def test_each_log_line_is_json_with_the_correlation_id():
    token = CORRELATION_ID.set("log-1")
    try:
        record = logging.LogRecord("catalog.http", logging.INFO, __file__, 1, "request status=%s", (200,), None)
        line = json.loads(JsonFormatter().format(record))
    finally:
        CORRELATION_ID.reset(token)
    assert line["correlationId"] == "log-1" and line["message"] == "request status=200"
    assert line["log.level"] == "INFO" and line["service.name"] == "catalog-api" and "@timestamp" in line


def test_without_database_url_the_service_does_not_start():
    with pytest.raises(SystemExit, match="DATABASE_URL is required"):
        build_repository({})


def test_mongo_is_the_default_and_connects_lazily():
    from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
    repository = build_repository({"DATABASE_URL": "mongodb://nowhere.invalid:27017/catalog"})
    assert isinstance(repository, MongoPropiedadRepository)


def test_memory_only_when_asked_for_explicitly():
    assert isinstance(build_repository({"PERSISTENCE": "memory"}), InMemoryPropiedadRepository)
    with pytest.raises(SystemExit, match="PERSISTENCE must be"):
        build_repository({"PERSISTENCE": "postgres"})
