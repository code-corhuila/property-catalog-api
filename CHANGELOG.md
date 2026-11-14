# Changelog of `property-catalog-api`

Every release of this repository, newest first. One release per course cut, tagged on `main`
(`git-conventions.md`, "Tags and versioning"; SemVer). Each entry lists the user stories it
brought, with the pull requests of `develop` that built them.

## [3.0.0] - 2026-11-15

### Added

- **HU-CAT-002 (code-corhuila/property-docs#138) — Property detail**
  - chore(catalog): start the service in Python with the common contract (#1)
  - feat(catalog): show the detail of a propiedad (#2)
  - feat(catalog): read the listings from MongoDB (#3)
- **HU-CAT-001 (code-corhuila/property-docs#136) — Search properties**
  - feat(catalog): search propiedades by city, guests and dates (#4)
- **HU-CAT-003 (code-corhuila/property-docs#197) — Filter by availability**
  - feat(catalog): leave out propiedades already booked on the dates (#5)
- **HU-CAT-004 (code-corhuila/property-docs#202) — Keep availability up to date from Booking events**
  - feat(catalog): apply Booking's events to the taken ranges (#6)
  - feat(catalog): consume catalog.reservas in a process of its own (#7)
