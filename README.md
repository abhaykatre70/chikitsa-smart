# Chikitsa Smart

<img src="app/static/images/doctors-animate.svg" align="right" height="300px">

> **Team Abhiyanta - Code League 1.0 Hackathon Top 10 Finalist**
> 
> **🔴 Live Demo:** [https://chikitsa-smart.vercel.app/](https://chikitsa-smart.vercel.app/)

Chikitsa Smart (formerly MediCare) is a web application developed using Flask that aims to assist patients in obtaining necessary medical care. The system allows users to register, book appointments, and uses AI to predict diseases based on symptoms.

## 🏆 Hackathon Achievement

On **3rd February 2026**, we participated in the **Code League 1.0 Hackathon** at GHRCE Nagpur as **Team Abhiyanta**.
We are proud to share that we qualified for the **Final Round** and secured a **Top 10 position** 🎉.

Although we didn’t win the final prize, the judges appreciated our **UI design** and our idea – **“Chikitsa Smart”**. This hackathon was a great learning experience where we enjoyed building the project, solving real-world problems, and collaborating as a team.

**Team Members:**
- **Tanmay Rathi**
- **Vinay Ninave**
- **Abhay Katre**
- **Piyush Lomte**

## ✨ Features

1. **Admin & Hospital Hospital Dashboard**: Live KPIs, doctor availability, and queue health.
2. **Smart Patient Registration**: Captures demographics and hospital selection.
3. **Appointment Scheduling**: Auto-assigns best available doctors with smart slots.
4. **Dynamic Queue Management**: Priority-based ordering with real-time updates.
5. **Real-Time Availability**: Tracking for doctors and admin visibility.
6. **Emergency Handling**: Priority surfacing for emergency cases.
7. **Token Generation**: Unique tokens and wait-time estimates.
8. **Notifications**: In-app, Email, and SMS (Twilio) alerts.
9. **AI Helpdesk**: Multilingual virtual assistant.
10. **Crowd Monitor**: Live crowd levels based on queue load.

## 🛠️ Project Structure

- `app/app.py`: Main Flask application routes and logic.
- `app/instance/database.db`: SQLite database for users and appointments.
- `app/templates`: HTML templates.
- `app/static`: CSS, JS, images, and assets.

## 🚀 Getting Started

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python run.py
   ```

3. **Access the App**:
   Visit `http://localhost:5000` in your browser.

## ☁️ Deployment & Configuration (Vercel)

The application is deployed on Vercel. To avoid server errors and enable full functionality, configure the following:

### 1. Database Persistence
**Important:** On Vercel (free tier), the SQLite database is **temporary**. It is recreated every time the app restarts. Data will not persist permanently unless you connect an external database (like PostgreSQL or MongoDB).

### 2. Environment Variables
Authentication and core features work with defaults, but for Email/SMS/AI features, add these in your Vercel Project Settings:

| Variable | Description |
| :--- | :--- |
| `SECRET_KEY` | Security key (e.g., random string) |
| `ADMIN_DEFAULT_PASSWORD` | Password for default `admin` user |
| `MAIL_SERVER` | SMTP Server (e.g., `smtp.gmail.com`) |
| `MAIL_USERNAME` | Email address for sending notifications |
| `MAIL_PASSWORD` | App Password for the email |
| `TWILIO_ACCOUNT_SID` | Twilio SID for SMS |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `AI_API_KEY` | API Key for AI features |

### 🔐 Demo Login Credentials

Since the database resets on every Vercel deployment, we have pre-loaded these accounts for you to test:

| Role | Username | Password |
| :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` |
| **Doctor** | `doctor1` | `doctor123` |
| **Patient** | `patient1` | `patient123` |

> *Note: You can also register new users, but they will be deleted when the server restarts.*

## 📦 Dependencies

- Flask-SQLAlchemy
- Plotly
- NumPy
- TensorFlow
- Scikit-learn
- Pandas

## 📊 Data Analysis

We have included a dataset of OGD Health Centres (`ogd_health_centres.csv`) and a script to analyze it.
To run the analysis:
```bash
python analyze_health_centres.py
```
This script provides insights into the distribution of health facilities across different states and types.

##  License

This project is licensed under the [MIT License](LICENSE).

---
*#Hackathon #CodeLeague #Top10 #Learning #UIUX #ChikitsaSmart #Growth #TeamAbhiyanta*
