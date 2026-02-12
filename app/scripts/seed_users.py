import argparse
import random
from itertools import cycle

from werkzeug.security import generate_password_hash

from app import app, db, Hospital, User

SPECIALIZATIONS = [
    "General Medicine",
    "Cardiology",
    "Orthopedics",
    "Pediatrics",
    "Gynecology",
    "Dermatology",
    "ENT",
    "Neurology",
]

LANGUAGES = ["en", "hi", "mr", "ta", "te", "bn", "gu", "kn", "ml"]
GENDERS = ["Male", "Female", "Other"]


def seed_users(admins_per_hospital, doctors_per_hospital, patients_per_hospital, replace):
    with app.app_context():
        db.create_all()

        if replace:
            User.query.filter(User.username.like("seed_%")).delete(synchronize_session=False)
            db.session.commit()

        hospitals = Hospital.query.order_by(Hospital.id.asc()).all()
        if not hospitals:
            print("No hospitals found. Import or generate hospitals first.")
            return

        specialization_cycle = cycle(SPECIALIZATIONS)
        total_created = 0
        buffer = []
        chunk_size = 1000

        for hospital in hospitals:
            for idx in range(admins_per_hospital):
                username = f"seed_admin_{hospital.id}_{idx}"
                user = User(
                    username=username,
                    email=f"{username}@demo.local",
                    password_hash=generate_password_hash("Admin123", method="pbkdf2:sha256"),
                    role="admin",
                    full_name=f"Admin {hospital.name}",
                    phone=f"9{hospital.id:03d}{idx:02d}00000".ljust(10, "0")[:10],
                    hospital_id=hospital.id,
                )
                buffer.append(user)

            for idx in range(doctors_per_hospital):
                username = f"seed_doctor_{hospital.id}_{idx}"
                user = User(
                    username=username,
                    email=f"{username}@demo.local",
                    password_hash=generate_password_hash("Doctor123", method="pbkdf2:sha256"),
                    role="doctor",
                    full_name=f"Dr. {hospital.name} {idx + 1}",
                    phone=f"8{hospital.id:03d}{idx:02d}00000".ljust(10, "0")[:10],
                    hospital_id=hospital.id,
                    type_of_doctor=next(specialization_cycle),
                    slot_minutes=random.choice([10, 12, 15]),
                    daily_start_time="09:00",
                    daily_end_time="17:00",
                )
                buffer.append(user)

            for idx in range(patients_per_hospital):
                username = f"seed_patient_{hospital.id}_{idx}"
                user = User(
                    username=username,
                    email=f"{username}@demo.local",
                    password_hash=generate_password_hash("Patient123", method="pbkdf2:sha256"),
                    role="patient",
                    full_name=f"Patient {hospital.name} {idx + 1}",
                    phone=f"7{hospital.id:03d}{idx:03d}000".ljust(10, "0")[:10],
                    age=random.randint(18, 70),
                    gender=random.choice(GENDERS),
                    language=random.choice(LANGUAGES),
                    hospital_id=hospital.id,
                )
                buffer.append(user)

            if len(buffer) >= chunk_size:
                db.session.bulk_save_objects(buffer)
                db.session.commit()
                total_created += len(buffer)
                buffer.clear()

        if buffer:
            db.session.bulk_save_objects(buffer)
            db.session.commit()
            total_created += len(buffer)

        print(f"Seeded {total_created} users across {len(hospitals)} hospitals.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo users per hospital")
    parser.add_argument("--admins-per-hospital", type=int, default=1)
    parser.add_argument("--doctors-per-hospital", type=int, default=5)
    parser.add_argument("--patients-per-hospital", type=int, default=50)
    parser.add_argument("--replace", action="store_true", help="Remove existing seed_* users first")
    args = parser.parse_args()

    seed_users(
        admins_per_hospital=args.admins_per_hospital,
        doctors_per_hospital=args.doctors_per_hospital,
        patients_per_hospital=args.patients_per_hospital,
        replace=args.replace,
    )
