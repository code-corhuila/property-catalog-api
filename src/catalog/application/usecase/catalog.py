"""The queries of catalog. Read-only in MVP 1: no use case writes a Propiedad."""
from catalog.application.port.outbound.ports import PropiedadRepository
from catalog.domain.model.busqueda import Busqueda, Pagina
from catalog.domain.model.propiedad import Propiedad, PropiedadNoEncontrada


class CatalogService:
    def __init__(self, repository: PropiedadRepository):
        self._repository = repository

    def get_propiedad(self, propiedad_id: str) -> Propiedad:
        found = self._repository.find_by_id(propiedad_id)
        if found is None:
            raise PropiedadNoEncontrada(propiedad_id)
        return found

    def buscar(self, busqueda: Busqueda) -> Pagina:
        return self._repository.search(busqueda)
