"""The listings in the database catalog of MongoDB, as catalog_app (ADR-008, Annex J.7).

The collections, their validators and the seed come from property-catalog-db: this
service never creates or changes them. The document fields are the ones of
06-data/models.md; the domain never sees them. Every filter is built from values
the HTTP adapter already validated, never from raw input (security-rules.md).
"""
from pymongo import MongoClient

from catalog.domain.model.propiedad import Anfitrion, Propiedad


class MongoPropiedadRepository:
    def __init__(self, client: MongoClient):
        self._database = client.get_default_database()    # the one in DATABASE_URL: catalog
        self._properties = self._database["properties"]

    def find_by_id(self, propiedad_id: str) -> Propiedad | None:
        document = self._properties.find_one({"_id": propiedad_id})
        return None if document is None else to_propiedad(document)

    def ping(self) -> bool:
        self._database.command("ping")
        return True


def to_propiedad(d: dict) -> Propiedad:
    host = d["host"]
    return Propiedad(
        id=d["_id"], title=d["title"], city=d["city"], country=d["country"],
        host=Anfitrion(host["id"], host["displayName"], host.get("hostSince")),
        capacity=d["capacity"], price_per_night_cents=int(d["pricePerNightCents"]), currency=d["currency"],
        amenities=tuple(d.get("amenities", ())), photos=tuple(d.get("photos", ())),
        rating=float(d["rating"]) if "rating" in d else None,
        bedrooms=d.get("bedrooms"), bathrooms=d.get("bathrooms"), area_m2=d.get("areaM2"),
        unavailable_ranges=tuple((r["startDate"], r["endDate"]) for r in d.get("unavailableRanges", ())))
