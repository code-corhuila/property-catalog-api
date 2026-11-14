"""The listings in the database catalog of MongoDB, as catalog_app (ADR-008, Annex J.7).

The collections, their validators and the seed come from property-catalog-db: this
service never creates or changes them. The document fields are the ones of
06-data/models.md; the domain never sees them. Every filter is built from values
the HTTP adapter already validated, never from raw input (security-rules.md).
"""
from pymongo import MongoClient

from catalog.domain.model.busqueda import Busqueda, Pagina
from catalog.domain.model.propiedad import Anfitrion, Propiedad

# The city matches ignoring case and accents (E-05): the collation of
# idx_properties_city_capacity in property-catalog-db, so the query can use that index.
IGNORING_CASE_AND_ACCENTS = {"locale": "es", "strength": 1}
NEWEST_FIRST = [("createdAt", -1), ("_id", -1)]


class MongoPropiedadRepository:
    def __init__(self, client: MongoClient):
        self._database = client.get_default_database()    # the one in DATABASE_URL: catalog
        self._properties = self._database["properties"]

    def find_by_id(self, propiedad_id: str) -> Propiedad | None:
        document = self._properties.find_one({"_id": propiedad_id})
        return None if document is None else to_propiedad(document)

    def search(self, busqueda: Busqueda) -> Pagina:
        query: dict = {}
        if busqueda.ciudad is not None:
            query["city"] = busqueda.ciudad
        if busqueda.huespedes is not None:
            query["capacity"] = {"$gte": busqueda.huespedes}
        total = self._properties.count_documents(query, collation=IGNORING_CASE_AND_ACCENTS)
        cursor = (self._properties.find(query, collation=IGNORING_CASE_AND_ACCENTS)
                  .sort(NEWEST_FIRST).skip(busqueda.offset).limit(busqueda.limit))
        return Pagina(tuple(to_propiedad(d) for d in cursor), busqueda.page, busqueda.limit, total)

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
        unavailable_ranges=tuple((r["startDate"], r["endDate"]) for r in d.get("unavailableRanges", ())),
        created_at=d["createdAt"])
