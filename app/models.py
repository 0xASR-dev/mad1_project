from . import db
from datetime import datetime
from flask_login import UserMixin
from . import login_manager

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin / doctor / patient
    is_active = db.Column(db.Boolean, default=True)
    contact = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor_profile = db.relationship("DoctorProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    patient_profile = db.relationship("PatientProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class DoctorProfile(db.Model):
    __tablename__ = "doctor_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    specialization = db.Column(db.String(120))
    bio = db.Column(db.Text)
    is_blacklisted = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="doctor_profile")
    availabilities = db.relationship("DoctorAvailability", back_populates="doctor", cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")

class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    age = db.Column(db.Integer)
    contact = db.Column(db.String(50))
    is_blacklisted = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="patient_profile")
    appointments = db.relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")

class DoctorAvailability(db.Model):
    __tablename__ = "doctor_availabilities"
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"))
    date = db.Column(db.Date)  # date of availability
    timeslot = db.Column(db.String(50))  # e.g., "10:00-10:30"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship("DoctorProfile", back_populates="availabilities")

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profiles.id"))
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"))
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)  # match availability timeslot
    status = db.Column(db.String(20), default="Booked")  # Booked/Completed/Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("PatientProfile", back_populates="appointments")
    doctor = db.relationship("DoctorProfile", back_populates="appointments")
    treatment = db.relationship("Treatment", back_populates="appointment", uselist=False, cascade="all, delete-orphan")

class Treatment(db.Model):
    __tablename__ = "treatments"
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"))
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointment = db.relationship("Appointment", back_populates="treatment")
