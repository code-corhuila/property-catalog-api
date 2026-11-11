"""The taken ranges of each property in MongoDB, fed by Booking's events (HU-CAT-004).

The eventId goes into processed_events and the change into properties.unavailableRanges in
the same transaction (06-data/modeling-conventions.md; services/03-catalog/events.md): a
redelivery fails on the _id of processed_events and nothing changes. That is why MongoDB
runs as a single-node replica set, also in develop (Annex B, rule 6). catalog_app has
find, insert and update on both collections (catalog_writer): this adapter never deletes.
"""
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from catalog.domain.model.evento_reserva import Cambio, EventoReserva, Resultado


class _PropiedadDesconocida(Exception):
    """Aborts the transaction: the eventId is not recorded either."""


class MongoDisponibilidadStore:
    def __init__(self, client: MongoClient):
        self._client = client
        database = client.get_default_database()    # the one in DATABASE_URL: catalog
        self._properties = database["properties"]
        self._processed = database["processed_events"]

    def aplicar(self, evento: EventoReserva, hoy: str) -> Resultado:
        with self._client.start_session() as session:
            try:
                with session.start_transaction():
                    self._processed.insert_one({"_id": evento.event_id, "eventType": evento.event_type,
                                                "processedAt": datetime.now(timezone.utc)}, session=session)
                    changed = self._properties.update_one({"_id": evento.propiedad_id},
                                                          [{"$set": nuevos_rangos(evento, hoy)}], session=session)
                    if changed.matched_count == 0:
                        raise _PropiedadDesconocida()
            except DuplicateKeyError:
                return Resultado.DUPLICADO
            except _PropiedadDesconocida:
                return Resultado.PROPIEDAD_DESCONOCIDA
        return Resultado.APLICADO


def nuevos_rangos(evento: EventoReserva, hoy: str) -> dict:
    """One update of the document, as an aggregation pipeline: keep the ranges that have not
    ended (endDate after hoy: the ranges are half-open), without the one of this Reserva when
    it takes or frees, and add its range when it takes. Taking twice leaves one range. Every
    value goes in as $literal: an id or a date is never read as a field path."""
    keep = [{"$gt": ["$$this.endDate", {"$literal": hoy}]}]
    if evento.cambio is not Cambio.MANTENER:
        keep.append({"$ne": ["$$this.reservationId", {"$literal": evento.reserva_id}]})
    ranges: dict = {"$filter": {"input": "$unavailableRanges", "cond": {"$and": keep}}}
    if evento.cambio is Cambio.TOMAR:
        taken = {"reservationId": evento.reserva_id, "startDate": evento.fecha_inicio.isoformat(),
                 "endDate": evento.fecha_fin.isoformat()}
        ranges = {"$concatArrays": [ranges, {"$literal": [taken]}]}
    return {"unavailableRanges": ranges, "updatedAt": "$$NOW"}
