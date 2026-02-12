import base64
import csv
import json
import os
from datetime import datetime, date, time, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"

app = Flask(
    __name__,
    instance_relative_config=True,
)
app.secret_key = os.getenv("SECRET_KEY", "MYSECRETKEY")

# Vercel filesystem is read-only, use /tmp for SQLite (Transient/Ephemeral only)
if os.environ.get('VERCEL'):
    import tempfile
    db_path = Path(tempfile.gettempdir()) / "database.db"
else:
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = Path(app.instance_path) / "database.db"

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT") or 465)
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)
db = SQLAlchemy(app)

PRIORITY_SCORES = {
    "Emergency": 3,
    "High": 2,
    "Normal": 1,
    "Low": 0,
}

AVAILABILITY_STATUSES = ["Available", "On Break", "Off Duty"]


class Hospital(db.Model):
    __table_args__ = (
        db.Index("ix_hospital_name", "name"),
        db.Index("ix_hospital_state_district", "state", "district"),
        db.UniqueConstraint("source", "source_id", name="uq_hospital_source_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(255))
    facility_type = db.Column(db.String(80))
    ownership = db.Column(db.String(80))
    state = db.Column(db.String(80))
    district = db.Column(db.String(80))
    subdistrict = db.Column(db.String(80))
    pincode = db.Column(db.String(10))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    source = db.Column(db.String(50))
    source_id = db.Column(db.String(80))
    is_government = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="patient")

    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    language = db.Column(db.String(10), default="en")

    hospital_id = db.Column(db.Integer, db.ForeignKey("hospital.id"))
    hospital = db.relationship("Hospital", backref=db.backref("users", lazy=True))

    type_of_doctor = db.Column(db.String(50))
    slot_minutes = db.Column(db.Integer, default=10)
    daily_start_time = db.Column(db.String(5), default="09:00")
    daily_end_time = db.Column(db.String(5), default="17:00")

    availability_status = db.Column(db.String(20), default="Available")
    availability_note = db.Column(db.String(120))
    availability_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    patient = db.relationship("User", foreign_keys=[patient_id])
    doctor = db.relationship("User", foreign_keys=[doctor_id])

    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="Waiting")
    priority_level = db.Column(db.String(20), default="Normal")
    priority_score = db.Column(db.Integer, default=1)
    symptoms = db.Column(db.Text)

    token_number = db.Column(db.Integer, nullable=False)
    token_date = db.Column(db.Date, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(20), default="in_app")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- Utilities ----------

def create_tables():
    with app.app_context():
        db.create_all()


def seed_data():
    with app.app_context():
        if not Hospital.query.first():
            default_hospital = Hospital(
                name="City General Hospital",
                address="Main Road",
                state="",
                district="",
                source="seed",
                is_government=True,
            )
            db.session.add(default_hospital)
            db.session.commit()
        if not User.query.filter_by(role="admin").first():
            admin_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")
            admin_user = User(
                username="admin",
                email="admin@hospital.local",
                password_hash=generate_password_hash(admin_password, method="pbkdf2:sha256"),
                role="admin",
                full_name="Hospital Admin",
                hospital_id=Hospital.query.first().id,
            )
            db.session.add(admin_user)
            db.session.commit()


def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or user.role not in roles:
                flash("Access denied.", "error")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def parse_time(value, fallback=time(9, 0)):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (ValueError, TypeError):
        return fallback


def generate_token(doctor_id, token_date):
    max_token = (
        db.session.query(func.max(Appointment.token_number))
        .filter_by(doctor_id=doctor_id, token_date=token_date)
        .scalar()
    )
    return (max_token or 0) + 1


def get_queue(doctor_id, token_date=None):
    token_date = token_date or date.today()
    return (
        Appointment.query.filter_by(doctor_id=doctor_id, token_date=token_date)
        .filter(Appointment.status.in_(["Waiting", "In Progress"]))
        .order_by(Appointment.priority_score.desc(), Appointment.token_number.asc())
        .all()
    )


def get_queue_position(appointment):
    queue = get_queue(appointment.doctor_id, appointment.token_date)
    for index, entry in enumerate(queue, start=1):
        if entry.id == appointment.id:
            return index
    return None


def estimate_wait_minutes(doctor, position):
    slot_minutes = max(5, doctor.slot_minutes or 10)
    if not position:
        return slot_minutes
    return slot_minutes * max(position - 1, 0)


def compute_scheduled_time(doctor, position):
    now = datetime.now().replace(second=0, microsecond=0)
    start_time = parse_time(doctor.daily_start_time, fallback=time(9, 0))
    end_time = parse_time(doctor.daily_end_time, fallback=time(17, 0))

    base_time = datetime.combine(now.date(), start_time)
    if now > base_time:
        base_time = now

    slot_minutes = max(5, doctor.slot_minutes or 10)
    scheduled = base_time + timedelta(minutes=slot_minutes * max(position - 1, 0))

    if scheduled.time() > end_time:
        next_day = now.date() + timedelta(days=1)
        scheduled = datetime.combine(next_day, start_time) + timedelta(
            minutes=slot_minutes * max(position - 1, 0)
        )

    return scheduled


def choose_doctor(specialization=None, hospital_id=None):
    query = User.query.filter_by(role="doctor", is_active=True)
    if specialization:
        query = query.filter_by(type_of_doctor=specialization)
    if hospital_id:
        query = query.filter_by(hospital_id=hospital_id)

    doctors = query.all()
    if not doctors:
        return None

    scored = []
    for doctor in doctors:
        queue_len = len(get_queue(doctor.id))
        availability_bonus = 0 if doctor.availability_status == "Available" else 5
        scored.append((queue_len + availability_bonus, doctor))

    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def send_email(subject, recipient, body):
    if not app.config.get("MAIL_SERVER"):
        return False
    try:
        msg = Message(subject, recipients=[recipient])
        msg.body = body
        mail.send(msg)
        return True
    except Exception:
        return False


def send_sms(to_number, body):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not (sid and token and from_number and to_number):
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = urlencode({"To": to_number, "From": from_number, "Body": body}).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = Request(url, data=payload, headers={"Authorization": f"Basic {auth}"})

    try:
        with urlopen(req, timeout=10) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def notify_user(user, title, message, send_email_flag=False, send_sms_flag=False):
    notification = Notification(user_id=user.id, title=title, message=message)
    db.session.add(notification)
    db.session.commit()

    if send_email_flag:
        send_email(title, user.email, message)
    if send_sms_flag and user.phone:
        send_sms(user.phone, message)


def rules_based_reply(message, language, context=None):
    normalized = message.lower()
    context = context or {}
    response_key = "default"
    response_en = "I can help with appointments, queue status, and doctor availability."

    if any(word in normalized for word in ["appointment", "book", "schedule"]):
        response_key = "appointment"
        response_en = "You can book an appointment from the patient dashboard. I can also suggest the best available doctor."
    elif any(word in normalized for word in ["wait", "token", "queue", "status"]):
        token = context.get("token")
        position = context.get("position")
        wait_minutes = context.get("wait_minutes")
        doctor = context.get("doctor_name")
        if token:
            response_key = "queue_dynamic"
            response_en = (
                f"Your token is #{token} with {doctor or 'the doctor'}. "
                f"You are number {position} in queue. Estimated wait: {wait_minutes} minutes."
            )
        else:
            response_key = "queue"
            response_en = "Check your dashboard to see your token number and estimated wait time."
    elif any(word in normalized for word in ["available", "doctor", "availability"]):
        availability = context.get("doctor_availability")
        if availability:
            response_key = "availability_dynamic"
            response_en = f"Doctor availability is currently {availability}."
        else:
            response_key = "availability"
            response_en = "Doctor availability is updated in real time on the dashboard."
    elif any(word in normalized for word in ["emergency", "urgent"]):
        response_key = "emergency"
        response_en = "If this is an emergency, please select Emergency priority while booking so you are moved to the top of the queue."
    elif any(word in normalized for word in ["crowd", "rush", "busy"]):
        crowd = context.get("crowd_level")
        if crowd:
            response_key = "crowd_dynamic"
            response_en = f"Current hospital crowd level is {crowd}. I recommend visiting during Low or Medium hours."
        else:
            response_key = "crowd"
            response_en = "Crowd level is monitored live on the admin dashboard."

    translations = {
        "hi": {
            "default": "मैं अपॉइंटमेंट, क्यू स्टेटस और डॉक्टर उपलब्धता में मदद कर सकता हूँ।",
            "appointment": "आप मरीज डैशबोर्ड से अपॉइंटमेंट बुक कर सकते हैं। मैं सबसे उपलब्ध डॉक्टर भी सुझा सकता हूँ।",
            "queue": "अपने टोकन नंबर और अनुमानित प्रतीक्षा समय के लिए डैशबोर्ड देखें।",
            "queue_dynamic": "आपका टोकन #{token} है, डॉक्टर {doctor} के साथ। आपकी कतार स्थिति {position} है। अनुमानित प्रतीक्षा: {wait_minutes} मिनट।",
            "availability": "डैशबोर्ड पर डॉक्टर की उपलब्धता रियल‑टाइम में अपडेट होती है।",
            "availability_dynamic": "डॉक्टर की उपलब्धता अभी {availability} है।",
            "emergency": "यदि यह आपात स्थिति है, तो बुकिंग करते समय Emergency प्राथमिकता चुनें।",
            "crowd": "भीड़ स्तर का अपडेट एडमिन डैशबोर्ड पर मिलता है।",
            "crowd_dynamic": "अभी अस्पताल की भीड़ {crowd} है। कम भीड़ के समय आने की सलाह है।",
        },
        "mr": {
            "default": "मी अपॉइंटमेंट, क्यू स्थिती आणि डॉक्टर उपलब्धता यामध्ये मदत करू शकतो.",
            "appointment": "तुम्ही रुग्ण डॅशबोर्डवरून अपॉइंटमेंट बुक करू शकता. मी सर्वोत्तम उपलब्ध डॉक्टर सुचवू शकतो.",
            "queue": "तुमचा टोकन नंबर आणि अंदाजे प्रतीक्षा वेळ डॅशबोर्डवर पाहा.",
            "queue_dynamic": "तुमचा टोकन #{token} आहे, डॉक्टर {doctor} सोबत. तुमची क्यू स्थिती {position}. अंदाजे प्रतीक्षा: {wait_minutes} मिनिटे.",
            "availability": "डॅशबोर्डवर डॉक्टरची उपलब्धता रिअल‑टाइममध्ये अपडेट होते.",
            "availability_dynamic": "डॉक्टरची उपलब्धता सध्या {availability} आहे.",
            "emergency": "आपत्कालीन परिस्थितीत बुकिंग करताना Emergency प्राधान्य निवडा.",
            "crowd": "गर्दीची माहिती एडमिन डॅशबोर्डवर दिसते.",
            "crowd_dynamic": "सध्या रुग्ण गर्दी {crowd} आहे. कमी गर्दीच्या वेळी येण्याची शिफारस.",
        },
        "ta": {
            "default": "நியமனம், வரிசை நிலை மற்றும் மருத்துவர் கிடைப்பை நான் உதவ முடியும்.",
            "appointment": "நீங்கள் நோயாளர் டாஷ்போர்டில் இருந்து நேரம் பதிவு செய்யலாம். சிறந்த கிடைக்கும் மருத்துவரையும் பரிந்துரைக்க முடியும்.",
            "queue": "டோக்கன் எண் மற்றும் காத்திருக்கும் நேரத்தை டாஷ்போர்டில் பார்க்கவும்.",
            "queue_dynamic": "உங்கள் டோக்கன் #{token}, மருத்துவர் {doctor} உடன். வரிசை நிலை {position}. காத்திருக்கும் நேரம்: {wait_minutes} நிமிடங்கள்.",
            "availability": "மருத்துவர் கிடைப்புத் தகவல் டாஷ்போர்டில் நேரடியாக புதுப்பிக்கப்படுகிறது.",
            "availability_dynamic": "மருத்துவர் கிடைப்புத் நிலை தற்போது {availability}.",
            "emergency": "அவசர நிலைக்கு, பதிவு செய்யும்போது Emergency முன்னுரிமை தேர்வு செய்யவும்.",
            "crowd": "கூட்ட நெரிசல் விவரம் நிர்வாக டாஷ்போர்டில் உள்ளது.",
            "crowd_dynamic": "இப்போது மருத்துவமனை நெரிசல் {crowd}. குறைந்த நெரிசல் நேரத்தை தேர்வு செய்யவும்.",
        },
        "te": {
            "default": "అపాయింట్‌మెంట్‌లు, క్యూస్థితి మరియు డాక్టర్ అందుబాటులో సహాయం చేయగలను.",
            "appointment": "పేషెంట్ డ్యాష్‌బోర్డ్లో అపాయింట్‌మెంట్ బుక్ చేయవచ్చు. ఉత్తమ అందుబాటు డాక్టర్‌ను సూచించగలను.",
            "queue": "టోకెన్ నంబర్ మరియు అంచనా వేచి ఉండే సమయాన్ని డ్యాష్‌బోర్డ్లో చూడండి.",
            "queue_dynamic": "మీ టోకెన్ #{token}, డాక్టర్ {doctor}తో. క్యూలో మీ స్థానం {position}. అంచనా వేచి ఉండే సమయం: {wait_minutes} నిమిషాలు.",
            "availability": "డాక్టర్ అందుబాటు డ్యాష్‌బోర్డ్లో రియల్‑టైమ్‌లో అప్డేట్ అవుతుంది.",
            "availability_dynamic": "డాక్టర్ అందుబాటు ప్రస్తుతం {availability} గా ఉంది.",
            "emergency": "ఎమర్జెన్సీ అయితే బుకింగ్ సమయంలో Emergency ప్రాధాన్యం ఎంచుకోండి.",
            "crowd": "గుంపు సమాచారం అడ్మిన్ డ్యాష్‌బోర్డ్లో ఉంటుంది.",
            "crowd_dynamic": "ప్రస్తుతం ఆసుపత్రి గుంపు స్థాయి {crowd}. తక్కువ గుంపు సమయంలో రావడం మంచిది.",
        },
        "bn": {
            "default": "আমি অ্যাপয়েন্টমেন্ট, কিউ স্ট্যাটাস এবং ডাক্তার উপলভ্যতা নিয়ে সাহায্য করতে পারি।",
            "appointment": "রোগী ড্যাশবোর্ড থেকে অ্যাপয়েন্টমেন্ট বুক করতে পারেন। আমি সেরা উপলভ্য ডাক্তারও সাজেস্ট করতে পারি।",
            "queue": "টোকেন নম্বর এবং আনুমানিক অপেক্ষার সময় ড্যাশবোর্ডে দেখুন।",
            "queue_dynamic": "আপনার টোকেন #{token}, ডাক্তার {doctor} এর সাথে। কিউ পজিশন {position}. আনুমানিক অপেক্ষা: {wait_minutes} মিনিট।",
            "availability": "ডাক্তার উপলভ্যতা ড্যাশবোর্ডে রিয়েল‑টাইমে আপডেট হয়।",
            "availability_dynamic": "ডাক্তার উপলভ্যতা বর্তমানে {availability}।",
            "emergency": "জরুরি হলে বুকিংয়ের সময় Emergency প্রায়োরিটি নির্বাচন করুন।",
            "crowd": "ভিড়ের তথ্য অ্যাডমিন ড্যাশবোর্ডে দেখা যায়।",
            "crowd_dynamic": "এখন হাসপাতালের ভিড় {crowd}। কম ভিড়ের সময় আসার পরামর্শ।",
        },
        "gu": {
            "default": "હું એપોઇન્ટમેન્ટ, ક્યુ સ્થિતિ અને ડોક્ટર ઉપલબ્ધતા વિશે મદદ કરી શકું છું.",
            "appointment": "તમે પેશન્ટ ડૅશબોર્ડ પરથી એપોઇન્ટમેન્ટ બુક કરી શકો છો. હું શ્રેષ્ઠ ઉપલબ્ધ ડોક્ટર સૂચવી શકું છું.",
            "queue": "તમારો ટોકન નંબર અને અંદાજિત રાહ સમય માટે ડૅશબોર્ડ જુઓ.",
            "queue_dynamic": "તમારો ટોકન #{token} છે, ડોક્ટર {doctor} સાથે. ક્યુ સ્થિતિ {position}. અંદાજિત રાહ: {wait_minutes} મિનિટ.",
            "availability": "ડોક્ટરની ઉપલબ્ધતા ડૅશબોર્ડ પર રિયલ‑ટાઈમ અપડેટ થાય છે.",
            "availability_dynamic": "ડોક્ટરની ઉપલબ્ધતા હાલમાં {availability} છે.",
            "emergency": "ઇમરજન્સી হলে બુકિંગ દરમિયાન Emergency પ્રાથમિકતા પસંદ કરો.",
            "crowd": "ભીડની માહિતી એડમિન ડૅશબોર્ડ પર મળે છે.",
            "crowd_dynamic": "હાલમાં હોસ્પિટલની ભીડ {crowd} છે. ઓછા ભીડવાળા સમયે આવવાનું સૂચન છે.",
        },
        "kn": {
            "default": "ನಾನು ಅಪಾಯಿಂಟ್ಮೆಂಟ್, ಕ್ಯೂ ಸ್ಥಿತಿ ಮತ್ತು ವೈದ್ಯರ ಲಭ್ಯತೆಯಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಹುದು.",
            "appointment": "ನೀವು ರೋಗಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಿಂದ ಅಪಾಯಿಂಟ್ಮೆಂಟ್ ಬುಕ್ ಮಾಡಬಹುದು. ಉತ್ತಮ ಲಭ್ಯ ವೈದ್ಯರನ್ನು ಸೂಚಿಸಬಹುದು.",
            "queue": "ನಿಮ್ಮ ಟೋಕನ್ ಸಂಖ್ಯೆ ಮತ್ತು ಅಂದಾಜು ಕಾಯುವ ಸಮಯಕ್ಕೆ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ ನೋಡಿ.",
            "queue_dynamic": "ನಿಮ್ಮ ಟೋಕನ್ #{token}, ವೈದ್ಯ {doctor} ಜೊತೆ. ಕ್ಯೂ ಸ್ಥಾನ {position}. ಅಂದಾಜು ಕಾಯುವ ಸಮಯ: {wait_minutes} ನಿಮಿಷಗಳು.",
            "availability": "ವೈದ್ಯರ ಲಭ್ಯತೆ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ ತಕ್ಷಣ ಅಪ್‌ಡೇಟ್ ಆಗುತ್ತದೆ.",
            "availability_dynamic": "ವೈದ್ಯರ ಲಭ್ಯತೆ ಈಗ {availability} ಆಗಿದೆ.",
            "emergency": "ಇದು ತುರ್ತುಸ್ಥಿತಿ হলে ಬುಕಿಂಗ್ ಸಮಯದಲ್ಲಿ Emergency ಪ್ರಾಥಮ್ಯ ಆಯ್ಕೆ ಮಾಡಿ.",
            "crowd": "ಗುಂಪಿನ ಮಾಹಿತಿ ಆಡ್ಮಿನ್ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ನಲ್ಲಿ ಲಭ್ಯ.",
            "crowd_dynamic": "ಪ್ರಸ್ತುತ ಆಸ್ಪತ್ರೆಯ ಗುಂಪಿನ ಮಟ್ಟ {crowd}. ಕಡಿಮೆ ಗುಂಪಿನ ಸಮಯದಲ್ಲಿ ಬನ್ನಿ.",
        },
        "ml": {
            "default": "അപ്പോയിന്റ്മെന്റ്, ക്യൂ നില, ഡോക്ടർ ലഭ്യത എന്നിവയിൽ ഞാൻ സഹായിക്കാം.",
            "appointment": "പേഷ്യന്റ് ഡാഷ്‌ബോർഡിൽ നിന്ന് അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യാം. മികച്ച ലഭ്യമായ ഡോക്ടറെ നിർദേശിക്കാം.",
            "queue": "നിങ്ങളുടെ ടോക്കൺ നമ്പറും കാത്തിരിപ്പ് സമയവും ഡാഷ്‌ബോർഡിൽ കാണുക.",
            "queue_dynamic": "നിങ്ങളുടെ ടോക്കൺ #{token}, ഡോക്ടർ {doctor} കൂടെ. ക്യൂ സ്ഥാനമാണ് {position}. കാത്തിരിപ്പ്: {wait_minutes} മിനിറ്റ്.",
            "availability": "ഡോക്ടറുടെ ലഭ്യത ഡാഷ്‌ബോർഡിൽ റിയൽ‑ടൈമിൽ അപ്‌ഡേറ്റ് ചെയ്യും.",
            "availability_dynamic": "ഡോക്ടറുടെ ലഭ്യത ഇപ്പോൾ {availability} ആണ്.",
            "emergency": "ഇത് അടിയന്തരമാണെങ്കിൽ ബുക്കിംഗ് സമയത്ത് Emergency മുൻഗണന തിരഞ്ഞെടുക്കുക.",
            "crowd": "ജനക്കൂട്ട വിവരങ്ങൾ അഡ്മിൻ ഡാഷ്‌ബോർഡിൽ ലഭ്യമാണ്.",
            "crowd_dynamic": "ഇപ്പോൾ ആശുപത്രിയിലെ തിരക്ക് {crowd}. തിരക്കുകുറഞ്ഞ സമയത്ത് വരിക.",
        },
    }

    if language in translations:
        template = translations[language].get(response_key)
        if template:
            return template.format(
                token=context.get("token"),
                doctor=context.get("doctor_name") or "डॉक्टर",
                position=context.get("position"),
                wait_minutes=context.get("wait_minutes"),
                availability=context.get("doctor_availability"),
                crowd=context.get("crowd_level"),
            )

    return response_en


def api_based_reply(message, language, context=None):
    api_url = os.getenv("AI_API_URL")
    api_key = os.getenv("AI_API_KEY")
    if not (api_url and api_key):
        return None

    payload = {
        "message": message,
        "language": language,
        "context": context or "hospital_helpdesk",
    }
    body = json.dumps(payload).encode()
    req = Request(
        api_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        if isinstance(data, dict):
            if "reply" in data:
                return data["reply"]
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    message_data = choice.get("message", {})
                    return message_data.get("content") or choice.get("text")
    except Exception:
        return None

    return None


def ai_reply(message, language, context=None):
    api_reply = api_based_reply(message, language, context=context)
    if api_reply:
        return api_reply
    return rules_based_reply(message, language, context=context)


def compute_crowd_status():
    today = date.today()
    queue_len = (
        Appointment.query.filter_by(token_date=today)
        .filter(Appointment.status.in_(["Waiting", "In Progress"]))
        .count()
    )
    available_doctors = User.query.filter_by(role="doctor", availability_status="Available").count()

    slot_minutes = (
        db.session.query(func.avg(User.slot_minutes))
        .filter_by(role="doctor", availability_status="Available")
        .scalar()
        or 10
    )

    capacity_per_hour = max(1, int(available_doctors * (60 / max(5, slot_minutes))))
    load_factor = queue_len / max(1, capacity_per_hour)

    if load_factor < 0.5:
        level = "Low"
    elif load_factor < 1:
        level = "Medium"
    elif load_factor < 1.5:
        level = "High"
    else:
        level = "Critical"

    return {
        "queue_len": queue_len,
        "available_doctors": available_doctors,
        "capacity_per_hour": capacity_per_hour,
        "level": level,
    }


def build_helpdesk_context(user):
    context = {"role": user.role}

    if user.role == "patient":
        appointment = (
            Appointment.query.filter_by(patient_id=user.id)
            .order_by(Appointment.created_at.desc())
            .first()
        )
        if appointment:
            position = get_queue_position(appointment)
            context.update(
                {
                    "token": appointment.token_number,
                    "position": position,
                    "wait_minutes": estimate_wait_minutes(appointment.doctor, position),
                    "doctor_name": appointment.doctor.full_name or appointment.doctor.username,
                }
            )

    if user.role == "doctor":
        context.update(
            {
                "doctor_availability": user.availability_status,
                "queue_len": len(get_queue(user.id)),
            }
        )

    if user.role == "admin":
        crowd = compute_crowd_status()
        context.update(
            {
                "crowd_level": crowd.get("level"),
                "crowd_queue": crowd.get("queue_len"),
            }
        )

    return context


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("home.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))


@app.route("/register/patient", methods=["GET", "POST"])
@app.route("/patient-register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        age = request.form.get("age")
        gender = request.form.get("gender")
        language = request.form.get("language")
        hospital_id = request.form.get("hospital_id")

        if not hospital_id:
            flash("Please select a hospital from the list.", "error")
            return render_template("patient-register.html")

        if not phone or len(phone.strip()) < 8:
            flash("Please enter a valid mobile number for SMS alerts.", "error")
            return render_template("patient-register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "error")
            return render_template("patient-register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            role="patient",
            full_name=full_name,
            phone=phone,
            age=int(age) if age else None,
            gender=gender,
            language=language or "en",
            hospital_id=int(hospital_id) if hospital_id else None,
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))

    return render_template("patient-register.html")


@app.route("/register/doctor", methods=["GET", "POST"])
@app.route("/doctor-register", methods=["GET", "POST"])
def doctor_register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        specialization = request.form.get("type_of_doctor")
        hospital_id = request.form.get("hospital_id")
        slot_minutes = request.form.get("slot_minutes")
        daily_start_time = request.form.get("daily_start_time")
        daily_end_time = request.form.get("daily_end_time")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "error")
            return render_template("doctor-register.html")

        if not hospital_id:
            flash("Please select a hospital from the list.", "error")
            return render_template("doctor-register.html")

        if not phone or len(phone.strip()) < 8:
            flash("Please enter a valid mobile number for SMS alerts.", "error")
            return render_template("doctor-register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            role="doctor",
            full_name=full_name,
            phone=phone,
            type_of_doctor=specialization,
            hospital_id=int(hospital_id) if hospital_id else None,
            slot_minutes=int(slot_minutes) if slot_minutes else 10,
            daily_start_time=daily_start_time or "09:00",
            daily_end_time=daily_end_time or "17:00",
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))

    return render_template("doctor-register.html")


@app.route("/register/admin", methods=["GET", "POST"])
def admin_register():
    setup_token = os.getenv("ADMIN_SETUP_TOKEN")

    if request.method == "POST":
        token = request.form.get("setup_token")
        if setup_token and token != setup_token:
            flash("Invalid setup token.", "error")
            return render_template("admin-register.html")

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        hospital_id = request.form.get("hospital_id")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "error")
            return render_template("admin-register.html")

        if not hospital_id:
            flash("Please select a hospital from the list.", "error")
            return render_template("admin-register.html")

        if not phone or len(phone.strip()) < 8:
            flash("Please enter a valid mobile number for SMS alerts.", "error")
            return render_template("admin-register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            role="admin",
            full_name=full_name,
            phone=phone,
            hospital_id=int(hospital_id) if hospital_id else None,
        )
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))

    return render_template("admin-register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "admin":
        today = date.today()
        total_patients = User.query.filter_by(role="patient").count()
        total_doctors = User.query.filter_by(role="doctor").count()
        today_appointments = Appointment.query.filter_by(token_date=today).count()
        emergency_count = Appointment.query.filter_by(
            token_date=today, priority_level="Emergency"
        ).count()
        emergency_cases = (
            Appointment.query.filter_by(token_date=today, priority_level="Emergency")
            .order_by(Appointment.created_at.desc())
            .all()
        )
        waiting = Appointment.query.filter_by(token_date=today).filter(
            Appointment.status.in_(["Waiting", "In Progress"])
        ).count()
        doctors = User.query.filter_by(role="doctor").all()
        crowd_status = compute_crowd_status()

        return render_template(
            "dashboard-admin.html",
            user=user,
            total_patients=total_patients,
            total_doctors=total_doctors,
            today_appointments=today_appointments,
            emergency_count=emergency_count,
            emergency_cases=emergency_cases,
            waiting=waiting,
            doctors=doctors,
            crowd_status=crowd_status,
        )

    if user.role == "doctor":
        queue = get_queue(user.id)
        return render_template(
            "dashboard-doctor.html",
            user=user,
            queue=queue,
            availability_status=user.availability_status,
            availability_note=user.availability_note,
        )

    upcoming = (
        Appointment.query.filter_by(patient_id=user.id)
        .order_by(Appointment.created_at.desc())
        .first()
    )
    position = get_queue_position(upcoming) if upcoming else None
    wait_minutes = estimate_wait_minutes(upcoming.doctor, position) if upcoming else None
    crowd_status = compute_crowd_status()

    return render_template(
        "dashboard-patient.html",
        user=user,
        appointment=upcoming,
        queue_position=position,
        wait_minutes=wait_minutes,
        crowd_status=crowd_status,
    )


@app.route("/book-appointment", methods=["GET", "POST"])
@login_required
@role_required("patient")
def book_appointment():
    user = current_user()
    doctors = User.query.filter_by(role="doctor").all()
    specializations = sorted({doc.type_of_doctor for doc in doctors if doc.type_of_doctor})

    if request.method == "POST":
        specialization = request.form.get("specialization")
        priority = request.form.get("priority", "Normal")
        symptoms = request.form.get("symptoms")

        doctor = choose_doctor(specialization=specialization, hospital_id=user.hospital_id)
        if not doctor:
            flash("No doctor available for the selected specialization.", "error")
            return render_template(
                "appointment-book.html", user=user, specializations=specializations
            )

        token_date = date.today()
        token_number = generate_token(doctor.id, token_date)
        queue_position = len(get_queue(doctor.id, token_date)) + 1
        scheduled_time = compute_scheduled_time(doctor, queue_position)

        appointment = Appointment(
            patient_id=user.id,
            doctor_id=doctor.id,
            scheduled_time=scheduled_time,
            status="Waiting",
            priority_level=priority,
            priority_score=PRIORITY_SCORES.get(priority, 1),
            symptoms=symptoms,
            token_number=token_number,
            token_date=token_date,
        )
        db.session.add(appointment)
        db.session.commit()

        notify_user(
            user,
            "Appointment Confirmed",
            f"Token #{token_number} assigned with Dr. {doctor.full_name or doctor.username}. Estimated wait: {estimate_wait_minutes(doctor, queue_position)} minutes.",
            send_email_flag=True,
            send_sms_flag=True,
        )
        notify_user(
            doctor,
            "New Patient Assigned",
            f"New patient {user.full_name or user.username} assigned. Token #{token_number} ({priority}).",
            send_email_flag=True,
            send_sms_flag=True,
        )

        if priority == "Emergency":
            admins = User.query.filter_by(role="admin").all()
            for admin in admins:
                notify_user(
                    admin,
                    "Emergency Case Alert",
                    f"Emergency case booked for Dr. {doctor.full_name or doctor.username}. Token #{token_number}.",
                    send_email_flag=True,
                    send_sms_flag=True,
                )

        return redirect(url_for("dashboard"))

    return render_template(
        "appointment-book.html", user=user, specializations=specializations
    )


@app.route("/doctor/availability", methods=["POST"])
@login_required
@role_required("doctor")
def update_availability():
    user = current_user()
    status = request.form.get("status")
    note = request.form.get("note")

    if status not in AVAILABILITY_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("dashboard"))

    user.availability_status = status
    user.availability_note = note
    user.availability_updated_at = datetime.utcnow()
    db.session.commit()

    flash("Availability updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/doctor/<int:doctor_id>/availability", methods=["POST"])
@login_required
@role_required("admin")
def admin_update_availability(doctor_id):
    status = request.form.get("status")
    note = request.form.get("note")
    doctor = User.query.get_or_404(doctor_id)

    if status not in AVAILABILITY_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("dashboard"))

    doctor.availability_status = status
    doctor.availability_note = note
    doctor.availability_updated_at = datetime.utcnow()
    db.session.commit()

    notify_user(
        doctor,
        "Availability Updated by Admin",
        f"Your availability is now set to {status}.",
        send_email_flag=True,
        send_sms_flag=True,
    )

    flash("Doctor availability updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/doctor/appointments/<int:appointment_id>/status", methods=["POST"])
@login_required
@role_required("doctor")
def update_appointment_status(appointment_id):
    user = current_user()
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != user.id:
        flash("Unauthorized.", "error")
        return redirect(url_for("dashboard"))

    new_status = request.form.get("status")
    if new_status not in ["Waiting", "In Progress", "Completed", "No Show"]:
        flash("Invalid status.", "error")
        return redirect(url_for("dashboard"))

    appointment.status = new_status
    db.session.commit()

    notify_user(
        appointment.patient,
        "Appointment Update",
        f"Your appointment status is now {new_status}.",
        send_email_flag=True,
        send_sms_flag=True,
    )

    if new_status in ["Completed", "No Show"]:
        queue = get_queue(user.id, appointment.token_date)
        if queue:
            next_patient = queue[0].patient
            notify_user(
                next_patient,
                "You're Next",
                f"You are next in queue for Dr. {user.full_name or user.username}. Please proceed to the consultation desk.",
                send_email_flag=True,
                send_sms_flag=True,
            )

    flash("Appointment updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/notifications")
@login_required
def notifications():
    user = current_user()
    notifications_list = (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "notifications.html", user=user, notifications=notifications_list
    )


@app.route("/helpdesk", methods=["GET", "POST"])
@login_required
def helpdesk():
    user = current_user()
    response_text = None
    if request.method == "POST":
        message = request.form.get("message")
        language = request.form.get("language", user.language or "en")
        context = build_helpdesk_context(user)
        response_text = ai_reply(message, language, context=context)
    return render_template(
        "helpdesk.html", user=user, response_text=response_text
    )


@app.route("/api/helpdesk-public", methods=["POST"])
def api_helpdesk_public():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    language = data.get("language") or "en"

    if not message:
        return jsonify({"reply": "Please enter a message."}), 400

    crowd = compute_crowd_status()
    context = {"crowd_level": crowd.get("level")}
    reply = ai_reply(message, language, context=context)
    return jsonify({"reply": reply})


@app.route("/api/hospitals")
def api_hospitals():
    q = (request.args.get("q") or "").strip()
    state = (request.args.get("state") or "").strip()
    district = (request.args.get("district") or "").strip()
    gov_only = request.args.get("gov_only", "1")
    limit = min(request.args.get("limit", 20, type=int) or 20, 50)

    query = Hospital.query
    if gov_only != "0":
        query = query.filter(Hospital.is_government.is_(True))
    if state:
        query = query.filter(func.lower(Hospital.state) == state.lower())
    if district:
        query = query.filter(func.lower(Hospital.district) == district.lower())
    if q:
        query = query.filter(func.lower(Hospital.name).like(f"{q.lower()}%"))
    else:
        query = query.order_by(Hospital.name.asc())

    results = query.limit(limit).all()
    data = [
        {
            "id": hospital.id,
            "name": hospital.name,
            "state": hospital.state,
            "district": hospital.district,
            "facility_type": hospital.facility_type,
            "ownership": hospital.ownership,
        }
        for hospital in results
    ]
    return jsonify(data)


@app.route("/api/hospital-states")
def api_hospital_states():
    gov_only = request.args.get("gov_only", "1")
    query = Hospital.query
    if gov_only != "0":
        query = query.filter(Hospital.is_government.is_(True))

    states = (
        query.with_entities(Hospital.state)
        .filter(Hospital.state.isnot(None))
        .filter(func.trim(Hospital.state) != "")
        .distinct()
        .order_by(Hospital.state.asc())
        .all()
    )
    return jsonify([state[0] for state in states])


@app.route("/api/hospital-districts")
def api_hospital_districts():
    state = (request.args.get("state") or "").strip()
    gov_only = request.args.get("gov_only", "1")

    query = Hospital.query
    if gov_only != "0":
        query = query.filter(Hospital.is_government.is_(True))
    if state:
        query = query.filter(func.lower(Hospital.state) == state.lower())

    districts = (
        query.with_entities(Hospital.district)
        .filter(Hospital.district.isnot(None))
        .filter(func.trim(Hospital.district) != "")
        .distinct()
        .order_by(Hospital.district.asc())
        .all()
    )
    return jsonify([district[0] for district in districts])


@app.route("/api/hospital-list")
def api_hospital_list():
    state = (request.args.get("state") or "").strip()
    district = (request.args.get("district") or "").strip()
    gov_only = request.args.get("gov_only", "1")
    limit = min(request.args.get("limit", 200, type=int) or 200, 2000)

    query = Hospital.query
    if gov_only != "0":
        query = query.filter(Hospital.is_government.is_(True))
    if state:
        query = query.filter(func.lower(Hospital.state) == state.lower())
    if district:
        query = query.filter(func.lower(Hospital.district) == district.lower())

    hospitals = (
        query.order_by(Hospital.name.asc())
        .limit(limit)
        .all()
    )

    data = [
        {
            "id": hospital.id,
            "name": hospital.name,
            "state": hospital.state,
            "district": hospital.district,
            "facility_type": hospital.facility_type,
            "ownership": hospital.ownership,
        }
        for hospital in hospitals
    ]
    return jsonify(data)


@app.route("/api/crowd-status")
@login_required
def api_crowd_status():
    return jsonify(compute_crowd_status())


@app.route("/api/queue")
@login_required
def api_queue():
    user = current_user()
    if user.role == "doctor":
        queue = get_queue(user.id)
    elif user.role == "admin":
        doctor_id = request.args.get("doctor_id", type=int)
        queue = get_queue(doctor_id) if doctor_id else []
    else:
        queue = []

    data = [
        {
            "id": entry.id,
            "token": entry.token_number,
            "patient": entry.patient.full_name or entry.patient.username,
            "priority": entry.priority_level,
            "status": entry.status,
        }
        for entry in queue
    ]
    return jsonify(data)


@app.route("/api/patient-status")
@login_required
@role_required("patient")
def api_patient_status():
    user = current_user()
    appointment = (
        Appointment.query.filter_by(patient_id=user.id)
        .order_by(Appointment.created_at.desc())
        .first()
    )
    if not appointment:
        return jsonify({"status": "no_appointment"})

    position = get_queue_position(appointment)
    wait_minutes = estimate_wait_minutes(appointment.doctor, position)

    return jsonify(
        {
            "token": appointment.token_number,
            "position": position,
            "wait_minutes": wait_minutes,
            "doctor": appointment.doctor.full_name or appointment.doctor.username,
            "status": appointment.status,
        }
    )


@app.route("/api/notifications")
@login_required
def api_notifications():
    user = current_user()
    notifications_list = (
        Notification.query.filter_by(user_id=user.id, is_read=False)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    data = [
        {
            "title": note.title,
            "message": note.message,
            "created_at": note.created_at.isoformat(),
        }
        for note in notifications_list
    ]
    return jsonify(data)


if __name__ == "__main__":
    create_tables()
    seed_data()
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
