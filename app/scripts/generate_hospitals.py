import csv
import random
from pathlib import Path

STATES_AND_UTS = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

DISTRICT_SUFFIXES = ["Central", "North", "South", "East", "West"]
SUBDISTRICTS = ["Block A", "Block B", "Block C"]
FACILITY_TYPES = [
    "District Hospital",
    "Sub District Hospital",
    "Community Health Centre",
    "Primary Health Centre",
    "Medical College Hospital",
]

INDIA_LAT_RANGE = (8.0, 37.5)
INDIA_LON_RANGE = (68.0, 97.0)


def random_pincode():
    return str(random.randint(110000, 855999))


def random_lat():
    return round(random.uniform(*INDIA_LAT_RANGE), 6)


def random_lon():
    return round(random.uniform(*INDIA_LON_RANGE), 6)


def generate_rows():
    counter = 1
    for state in STATES_AND_UTS:
        base = state.split()[0]
        for suffix in DISTRICT_SUFFIXES:
            district = f"{base} {suffix}"
            for idx in range(1, 6):
                facility_type = FACILITY_TYPES[(counter - 1) % len(FACILITY_TYPES)]
                yield {
                    "facility_name": f"Government {district} Hospital {idx}",
                    "address": f"Main Road, {district}, {state}",
                    "state_name": state,
                    "district_name": district,
                    "sub_district_name": random.choice(SUBDISTRICTS),
                    "pincode": random_pincode(),
                    "facility_type": facility_type,
                    "ownership": "Government",
                    "facility_id": f"GEN-{counter:05d}",
                    "latitude": random_lat(),
                    "longitude": random_lon(),
                }
                counter += 1


def main():
    output = Path(__file__).resolve().parents[1] / "data" / "hospitals" / "raw" / "generated_government_hospitals.csv"
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = list(generate_rows())
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} demo hospitals at {output}")


if __name__ == "__main__":
    main()
