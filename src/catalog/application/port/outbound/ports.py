"""What catalog needs: where the listings are stored."""
from typing import Protocol

from catalog.domain.model.busqueda import Busqueda, Pagina
from catalog.domain.model.propiedad import Propiedad


class PropiedadRepository(Protocol):
    def find_by_id(self, propiedad_id: str) -> Propiedad | None:
        ...

    def search(self, busqueda: Busqueda) -> Pagina:
        ...

    def ping(self) -> bool:
        """True when the store answers; reported by /health."""
        ...
