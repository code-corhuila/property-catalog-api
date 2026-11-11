"""A search of E-05 and the page it returns (HU-CAT-001). Plain Python only."""
import math
import unicodedata
from dataclasses import dataclass
from datetime import date

from catalog.domain.model.propiedad import Propiedad


def fold(text: str) -> str:
    """The city compared ignoring case and accents (E-05): "Bogotá" = "BOGOTA"."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class RangoFechas:
    """[inicio, fin): fin is the check-out day, not included."""
    inicio: date
    fin: date

    def __post_init__(self):
        if self.fin <= self.inicio:
            raise ValueError("fechaFin must be after fechaInicio")

    def se_superpone_con(self, inicio: date, fin: date) -> bool:
        """The half-open overlap of INV-001 (DateRange.seSuperponeCon): a stay that ends
        the day another one starts does not overlap it (catalog-endpoint-fiches.md, E-05)."""
        return self.inicio < fin and inicio < self.fin


@dataclass(frozen=True)
class Busqueda:
    page: int = 1
    limit: int = 20
    ciudad: str | None = None
    huespedes: int | None = None
    fechas: RangoFechas | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    def admite(self, p: Propiedad) -> bool:
        """The filters of E-05 on one Propiedad, as the in-memory store applies them."""
        if self.ciudad is not None and fold(p.city) != fold(self.ciudad):
            return False
        if self.huespedes is not None and p.capacity < self.huespedes:
            return False
        return self.fechas is None or not any(
            self.fechas.se_superpone_con(date.fromisoformat(start), date.fromisoformat(end))
            for start, end in p.unavailable_ranges)


@dataclass(frozen=True)
class Pagina:
    items: tuple[Propiedad, ...]
    page: int
    limit: int
    total: int

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.limit)
