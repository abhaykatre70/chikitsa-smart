import argparse
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app import app, db, Hospital


def normalize_column(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def first_value(row, keys):
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none"}:
            return text
    return None


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_record(row, source):
    name = first_value(
        row,
        [
            "facility_name",
            "health_facility_name",
            "hospital_name",
            "name",
            "facility",
            "hospital",
        ],
    )
    if not name:
        return None

    address = first_value(
        row,
        [
            "address",
            "facility_address",
            "hospital_address",
            "location",
        ],
    )
    state = first_value(row, ["state_name", "state", "state_ut", "state_uts"])
    district = first_value(row, ["district_name", "district", "districts"])
    subdistrict = first_value(row, ["sub_district_name", "subdistrict", "taluk", "block"])
    pincode = first_value(row, ["pincode", "pin_code", "pin", "postal_code", "zipcode"])
    facility_type = first_value(row, ["facility_type", "facility_category", "type", "hospital_type"])
    ownership = first_value(row, ["ownership", "owner", "ownership_type", "ownership_category"])
    source_id = first_value(
        row,
        ["facility_id", "health_facility_id", "hfr_id", "hospital_id", "nhrr_id"],
    )

    latitude = parse_float(first_value(row, ["latitude", "lat", "geo_lat", "y"]))
    longitude = parse_float(first_value(row, ["longitude", "lon", "long", "geo_long", "x"]))

    ownership_value = (ownership or "").lower()
    is_government = False
    if source in {"ogd", "generated"}:
        is_government = True
    elif any(term in ownership_value for term in ["government", "govt", "public", "state"]):
        is_government = True

    return {
        "name": name,
        "address": address,
        "facility_type": facility_type,
        "ownership": ownership,
        "state": state,
        "district": district,
        "subdistrict": subdistrict,
        "pincode": pincode,
        "latitude": latitude,
        "longitude": longitude,
        "source": source,
        "source_id": source_id,
        "is_government": is_government,
    }


def read_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [normalize_column(col) for col in df.columns]
    return df


def import_files(files, source, replace):
    with app.app_context():
        db.create_all()
        if replace:
            Hospital.query.filter_by(source=source).delete()
            db.session.commit()

        seen = set()
        buffer = []
        total = 0

        for file_path in files:
            df = read_dataframe(file_path)
            for _, row in df.iterrows():
                record = build_record(row, source)
                if not record:
                    continue

                key = (
                    (record["name"] or "").lower(),
                    (record["state"] or "").lower(),
                    (record["district"] or "").lower(),
                    (record["facility_type"] or "").lower(),
                )
                if key in seen:
                    continue
                seen.add(key)

                buffer.append(Hospital(**record))
                if len(buffer) >= 1000:
                    db.session.add_all(buffer)
                    db.session.commit()
                    total += len(buffer)
                    buffer.clear()

        if buffer:
            db.session.add_all(buffer)
            db.session.commit()
            total += len(buffer)

        print(f"Imported {total} records for source '{source}'.")


def main():
    parser = argparse.ArgumentParser(description="Import hospital datasets")
    parser.add_argument("--source", required=True, choices=["ogd", "cghs", "hfr", "generated"], help="Data source name")
    parser.add_argument("--replace", action="store_true", help="Replace existing records for source")
    parser.add_argument("files", nargs="+", help="CSV/XLSX files to import")
    args = parser.parse_args()

    files = [Path(path) for path in args.files]
    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(file_path)

    import_files(files, args.source, args.replace)


if __name__ == "__main__":
    main()
