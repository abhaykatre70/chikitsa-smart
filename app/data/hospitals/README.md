# Hospital Dataset Imports

Place raw datasets inside `backend/data/hospitals/raw/` and import with the script:

```bash
python3 backend/scripts/import_hospitals.py --source ogd --replace backend/data/hospitals/raw/ogd_health_centres.csv
python3 backend/scripts/import_hospitals.py --source cghs --replace backend/data/hospitals/raw/cghs_empanelled.csv
python3 backend/scripts/import_hospitals.py --source hfr --replace backend/data/hospitals/raw/hfr_export.csv
```

## Suggested Sources
- All India Health Centres Directory (MoHFW / OGD)
- CGHS empanelled hospitals list
- HFR (Health Facility Registry / NHRR) export

## Notes
- OGD facilities are treated as government by default.
- CGHS entries are imported as empanelled (not all are government-owned).
- HFR ownership fields are used to infer government facilities.
- Use `/api/hospitals?q=...` for search (gov-only by default).
