"""The core, with no server and no database (Annex C, level "Núcleo")."""
import ast
import pathlib

import pytest

from catalog.adapter.outbound.persistence.memory import InMemoryPropiedadRepository
from catalog.application.usecase.catalog import CatalogService
from catalog.domain.model.propiedad import PropiedadNoEncontrada
from conftest import MISSING, VILLA, propiedad

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "catalog"


def test_returns_the_propiedad_with_that_id():
    service = CatalogService(InMemoryPropiedadRepository([propiedad(VILLA)]))
    assert service.get_propiedad(VILLA).title == "Apartamento en Villa Del Mar"


def test_an_unknown_id_is_a_typed_error():
    service = CatalogService(InMemoryPropiedadRepository())
    with pytest.raises(PropiedadNoEncontrada):
        service.get_propiedad(MISSING)


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_the_core_imports_no_framework_and_no_driver(layer):
    """The dependency rule, checked by reviewing the imports (Annex C; numeral 5.3.3)."""
    forbidden = ("fastapi", "starlette", "pydantic", "pymongo", "bson", "uvicorn", "jwt", "catalog.adapter")
    for file in (SRC / layer).rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                assert not name.startswith(forbidden), f"{file.name} imports {name}"
