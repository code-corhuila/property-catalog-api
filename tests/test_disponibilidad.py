"""HU-CAT-004 in the core: what each event does to the ranges, with a fake store."""
from datetime import date

import pytest

from catalog.application.usecase.disponibilidad import DisponibilidadService
from catalog.domain.model.evento_reserva import Cambio, EventoInvalido, EventoReserva, Resultado
from conftest import VILLA

RESERVA = "b7e6c1d0-2222-4c3e-9a2d-000000000002"


def evento(event_type: str, **overrides) -> EventoReserva:
    values = dict(event_id="9f1c2b3a-1111-4c3e-9a2d-000000000001", event_type=event_type,
                  reserva_id=RESERVA, propiedad_id=VILLA)
    if event_type in ("ReservaCreada", "ReservaConfirmada"):
        values.update(fecha_inicio=date(2027, 9, 10), fecha_fin=date(2027, 9, 15))
    values.update(overrides)
    return EventoReserva(**values)


class FakeStore:
    def __init__(self):
        self.calls = []

    def aplicar(self, evento, hoy):
        self.calls.append((evento, hoy))
        return Resultado.APLICADO


@pytest.mark.parametrize("event_type, cambio", [
    ("ReservaCreada", Cambio.TOMAR), ("ReservaConfirmada", Cambio.MANTENER),
    ("ReservaCancelada", Cambio.LIBERAR), ("ReservaExpirada", Cambio.LIBERAR)])
def test_each_event_of_a_reserva_has_its_change_as_models_md_says(event_type, cambio):
    assert evento(event_type).cambio is cambio


def test_the_service_hands_the_event_to_the_store_with_the_date_of_today():
    store = FakeStore()
    service = DisponibilidadService(store, hoy=lambda: date(2027, 9, 1))
    assert service.aplicar(evento("ReservaCreada")) is Resultado.APLICADO
    assert store.calls == [(evento("ReservaCreada"), "2027-09-01")]


@pytest.mark.parametrize("event_type", ["PagoAprobado", "reservaCreada", ""])
def test_an_event_catalog_does_not_consume_is_invalid(event_type):
    with pytest.raises(EventoInvalido):
        EventoReserva(event_id="e", event_type=event_type, reserva_id=RESERVA, propiedad_id=VILLA)


def test_a_reserva_creada_needs_its_dates_and_in_order():
    with pytest.raises(EventoInvalido):
        evento("ReservaCreada", fecha_fin=None)
    with pytest.raises(EventoInvalido):
        evento("ReservaCreada", fecha_inicio=date(2027, 9, 15), fecha_fin=date(2027, 9, 15))


def test_the_events_that_free_need_no_dates():
    assert evento("ReservaExpirada").fecha_inicio is None
