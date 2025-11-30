from .models import Appointment, DoctorAvailability
from . import db
from datetime import date

def is_slot_free(doctor_id, date_obj, time_slot):
    # prevent double booking for same doctor/date/time (only Booked appointments considered)
    existing = Appointment.query.filter_by(doctor_id=doctor_id, date=date_obj, time_slot=time_slot).filter(Appointment.status!="Cancelled").first()
    return existing is None
