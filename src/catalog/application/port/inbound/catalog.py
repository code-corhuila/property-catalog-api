"""What catalog offers: the queries of E-05 and E-06 (catalog-endpoint-fiches.md)."""
from typing import Protocol

from catalog.domain.model.busqueda import Busqueda, Pagina
from catalog.domain.model.propiedad import Propiedad


class CatalogQueries(Protocol):
    def get_propiedad(self, propiedad_id: str) -> Propiedad:
        """The Propiedad with that id, or PropiedadNoEncontrada."""
        ...

    def buscar(self, busqueda: Busqueda) -> Pagina:
        """One page of the Propiedades that match, newest first."""
        ...
