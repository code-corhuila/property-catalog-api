"""HU-CAT-004 against the real engine: a single-node replica set with the database catalog
of property-catalog-db applied, as catalog_app (Annex C, level "Integración"). Skipped,
not failed, when TEST_DATABASE_URL is not set.

catalog_app may not delete: every test uses new eventIds and Reservas, and frees the ranges
it took with a ReservaCancelada, the way Booking would.
"""
import os
import uuid
from datetime import date

import pytest
from pymongo import MongoClient

from apps.api.__main__ import mongo_client
from catalog.adapter.outbound.persistence.mongo import MongoPropiedadRepository
from catalog.adapter.outbound.persistence.mongo_disponibilidad import MongoDisponibilidadStore
from catalog.application.usecase.disponibilidad import DisponibilidadService
from catalog.domain.model.busqueda import Busqueda, RangoFechas
from catalog.domain.model.evento_reserva import EventoReserva, Resultado
from conftest import MISSING, VILLA

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                                reason="TEST_DATABASE_URL is not set (Annex C)")
TODAY = date(2027, 3, 1)


@pytest.fixture(scope="module")
def client() -> MongoClient:
    client = mongo_client({"DATABASE_URL": os.environ.get("TEST_DATABASE_URL", ""),
                           "DATABASE_USER": os.environ.get("TEST_DATABASE_USER", "catalog_app"),
                           "DATABASE_PASSWORD": os.environ.get("TEST_DATABASE_PASSWORD", "")})
    yield client
    client.close()


@pytest.fixture
def service(client) -> DisponibilidadService:
    return DisponibilidadService(MongoDisponibilidadStore(client), hoy=lambda: TODAY)


@pytest.fixture
def reserva(service):
    """A new Reserva on VILLA; whatever it took is freed at the end."""
    reserva_id = str(uuid.uuid4())
    yield reserva_id
    service.aplicar(evento("ReservaCancelada", reserva_id))


def evento(event_type: str, reserva_id: str, propiedad: str = VILLA, event_id: str | None = None,
           inicio: date = date(2027, 3, 10), fin: date = date(2027, 3, 15)) -> EventoReserva:
    fechas = dict(fecha_inicio=inicio, fecha_fin=fin) if event_type in ("ReservaCreada", "ReservaConfirmada") else {}
    return EventoReserva(event_id=event_id or str(uuid.uuid4()), event_type=event_type,
                         reserva_id=reserva_id, propiedad_id=propiedad, **fechas)


def rangos(client, propiedad: str = VILLA) -> list[dict]:
    return client.get_default_database()["properties"].find_one({"_id": propiedad})["unavailableRanges"]


def processed(client, event_id: str) -> dict | None:
    return client.get_default_database()["processed_events"].find_one({"_id": event_id})


def test_scenario_1_a_reserva_creada_takes_its_dates(client, service, reserva):
    creada = evento("ReservaCreada", reserva)
    assert service.aplicar(creada) is Resultado.APLICADO
    assert {"reservationId": reserva, "startDate": "2027-03-10", "endDate": "2027-03-15"} in rangos(client)
    assert processed(client, creada.event_id)["eventType"] == "ReservaCreada"


@pytest.mark.parametrize("libera", ["ReservaCancelada", "ReservaExpirada"])
def test_scenario_2_a_cancelled_or_expired_reserva_frees_its_dates(client, service, reserva, libera):
    service.aplicar(evento("ReservaCreada", reserva))
    assert service.aplicar(evento(libera, reserva)) is Resultado.APLICADO
    assert reserva not in {r["reservationId"] for r in rangos(client)}


def test_scenario_3_the_same_event_twice_changes_nothing_the_second_time(client, service, reserva):
    creada = evento("ReservaCreada", reserva)
    service.aplicar(creada)
    service.aplicar(evento("ReservaCancelada", reserva))
    # Delivered again after the cancellation: it must not take the dates back.
    assert service.aplicar(creada) is Resultado.DUPLICADO
    assert reserva not in {r["reservationId"] for r in rangos(client)}


def test_a_reserva_confirmada_keeps_the_range_and_is_recorded(client, service, reserva):
    service.aplicar(evento("ReservaCreada", reserva))
    confirmada = evento("ReservaConfirmada", reserva)
    assert service.aplicar(confirmada) is Resultado.APLICADO
    assert [r["reservationId"] for r in rangos(client)].count(reserva) == 1
    assert processed(client, confirmada.event_id)["eventType"] == "ReservaConfirmada"


def test_an_unknown_property_writes_nothing_not_even_the_event_id(client, service):
    creada = evento("ReservaCreada", str(uuid.uuid4()), propiedad=MISSING)
    assert service.aplicar(creada) is Resultado.PROPIEDAD_DESCONOCIDA
    assert processed(client, creada.event_id) is None


def test_the_ranges_that_ended_are_dropped_so_the_array_stays_bounded(client, service, reserva):
    """models.md, rule 4. The range of the past is loaded by hand, as an old projection."""
    ended = {"reservationId": str(uuid.uuid4()), "startDate": "2027-02-20", "endDate": "2027-03-01"}
    client.get_default_database()["properties"].update_one({"_id": VILLA}, {"$push": {"unavailableRanges": ended}})
    service.aplicar(evento("ReservaCreada", reserva))
    assert ended["reservationId"] not in {r["reservationId"] for r in rangos(client)}


def test_hu_cat_003_scenario_2_the_search_leaves_out_the_property_after_the_event(client, service, reserva):
    search = MongoPropiedadRepository(client)

    def ids():
        page = search.search(Busqueda(ciudad="Cartagena", fechas=RangoFechas(date(2027, 3, 14), date(2027, 3, 16))))
        return {p.id for p in page.items}
    assert VILLA in ids()
    service.aplicar(evento("ReservaCreada", reserva))
    assert VILLA not in ids()
    service.aplicar(evento("ReservaExpirada", reserva))
    assert VILLA in ids()
