"""In-memory listings: for tests and local development only (PERSISTENCE=memory).

Nothing persists and it is never an environment (norm 5.5.2).
"""
from collections.abc import Iterable

from catalog.domain.model.propiedad import Propiedad


class InMemoryPropiedadRepository:
    def __init__(self, propiedades: Iterable[Propiedad] = ()):
        self._by_id = {p.id: p for p in propiedades}

    def find_by_id(self, propiedad_id: str) -> Propiedad | None:
        return self._by_id.get(propiedad_id)

    def ping(self) -> bool:
        return True
