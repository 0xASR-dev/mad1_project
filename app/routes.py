from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from . import db
from .models import User, DoctorProfile, PatientProfile, DoctorAvailability, Appointment, Treatment
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta, date
from sqlalchemy import or_

main = Blueprint("main", __name__)



# ---------- Auth ----------
@main.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("main.admin_dashboard"))
        if current_user.role == "doctor":
            return redirect(url_for("main.doctor_dashboard"))
        if current_user.role == "patient":
            return redirect(url_for("main.patient_dashboard"))
    return render_template("index.html")

@main.route("/register", methods=["GET", "POST"])
def register():
    """Patient-only registration. Doctors are added by Admin."""
    if request.method=="POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(email=email).first():
            flash("User already registered! Please Login", "warning")
            return redirect(url_for("main.register"))
        user = User(name=name, email=email, password_hash=generate_password_hash(password), role="patient")
        db.session.add(user)
        db.session.commit()
        pp = PatientProfile(user_id=user.id)
        db.session.add(pp)
        db.session.commit()
        flash(f"{user.name} Thank you for Registering. Please login.", "success")
        return redirect(url_for("main.login"))
    return render_template("auth/register.html")

@main.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("main.login"))
        if not user.is_active:
            flash("Your account is inactive. Please contact Admin support.", "warning")
            return redirect(url_for("main.login"))
        login_user(user)
        flash(f"Welcome back {user.name}! Logged in successfully.", "success")
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")

@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("main.login"))

@main.route("/blacklisted")
@login_required
def blacklisted():
    return render_template("blacklisted.html")

# ---------- Admin ----------
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role!="admin":
            abort(403)
        return func(*args, **kwargs)
    return wrapper

@main.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    total_doctors = DoctorProfile.query.count()
    total_patients = PatientProfile.query.count()
    total_appointments = Appointment.query.count()
    doctors = DoctorProfile.query.all()
    upcoming = (
        Appointment.query.filter(Appointment.date >= date.today())
        .order_by(Appointment.date, Appointment.time_slot)
        .limit(5)
        .all()
    )
    
    # Chart data: Appointment status breakdown
    booked_count = Appointment.query.filter_by(status="Booked").count()
    completed_count = Appointment.query.filter_by(status="Completed").count()
    cancelled_count = Appointment.query.filter_by(status="Cancelled").count()
    
    # Chart data: Appointments/day for last 7 days
    today = date.today()
    daily_labels = []
    daily_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_labels.append(day.strftime("%d %b"))
        count = Appointment.query.filter_by(date=day).count()
        daily_data.append(count)
    
    # Chart data: Doctors by specialization
    specializations = db.session.query(
        DoctorProfile.specialization, db.func.count(DoctorProfile.id)
    ).group_by(DoctorProfile.specialization).all()
    spec_labels = [s[0] or "Unassigned" for s in specializations]
    spec_data = [s[1] for s in specializations]

    # Recent Patients
    recent_patients = PatientProfile.query.join(User).order_by(User.created_at.desc()).limit(5).all()

    # Blacklist Stats
    blacklisted_doctors = DoctorProfile.query.filter_by(is_blacklisted=True).count()
    blacklisted_patients = PatientProfile.query.filter_by(is_blacklisted=True).count()
    
    return render_template(
        "admin/dashboard.html",
        doctors=doctors,
        upcoming=upcoming,
        recent_patients=recent_patients,
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,
        booked_count=booked_count,
        completed_count=completed_count,
        cancelled_count=cancelled_count,
        daily_labels=daily_labels,
        daily_data=daily_data,
        spec_labels=spec_labels,
        spec_data=spec_data,
        blacklisted_doctors=blacklisted_doctors,
        blacklisted_patients=blacklisted_patients,
    )

@main.route("/admin/doctors")
@login_required
@admin_required
def admin_doctors():
    q = request.args.get("q", "").strip()
    base_query = DoctorProfile.query.join(User)
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            or_(
                User.name.ilike(like),
                User.email.ilike(like),
                DoctorProfile.specialization.ilike(like),
            )
        )
    doctors = base_query.all()
    return render_template("admin/doctors_list.html", doctors=doctors, q=q)

@main.route("/admin/doctor/add", methods=["GET","POST"])
@login_required
@admin_required
def admin_add_doctor():
    if request.method=="POST":
        name = request.form.get("name")
        email = request.form.get("email")
        specialization = request.form.get("specialization")
        password = request.form.get("password") or "doc123"
        if User.query.filter_by(email=email).first():
            flash("Email exists", "warning")
            return redirect(url_for("main.admin_add_doctor"))
        user = User(name=name, email=email, password_hash=generate_password_hash(password), role="doctor")
        db.session.add(user)
        db.session.commit()
        profile = DoctorProfile(user_id=user.id, specialization=specialization)
        db.session.add(profile)
        db.session.commit()
        flash("Doctor added successfully!", "success")
        return redirect(url_for("main.admin_doctors"))
    return render_template("admin/doctor_form.html")

@main.route("/admin/doctor/<int:d_id>/edit", methods=["GET","POST"])
@login_required
@admin_required
def admin_edit_doctor(d_id):
    doctor = DoctorProfile.query.get_or_404(d_id)
    if request.method=="POST":
        doctor.user.name = request.form.get("name")
        doctor.specialization = request.form.get("specialization")
        db.session.commit()
        flash("Updated successfully!", "success")
        return redirect(url_for("main.admin_doctors"))
    return render_template("admin/doctor_form.html", doctor=doctor)

@main.route("/admin/doctor/<int:d_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_doctor(d_id):
    doctor = DoctorProfile.query.get_or_404(d_id)
    db.session.delete(doctor.user)  #removes profile
    db.session.commit()
    flash("Doctor removed successfully!", "success")
    return redirect(url_for("main.admin_doctors"))

@main.route("/admin/doctor/<int:d_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_doctor(d_id):
    doctor = DoctorProfile.query.get_or_404(d_id)
    doctor.is_blacklisted = not doctor.is_blacklisted
    doctor.user.is_active = True # make sure user can login to see the blacklist message
    db.session.commit()
    state = "re-activated" if not doctor.is_blacklisted else "blacklisted"
    flash(f"Doctor {state}", "info")
    return redirect(request.referrer or url_for("main.admin_doctors"))

@main.route("/admin/search")
@login_required
@admin_required
def admin_search():
    q = request.args.get("q","").strip()
    doctors = []
    patients = []
    if q:
        like = f"%{q}%"
        doctors = (
            DoctorProfile.query.join(User)
            .filter(
                or_(
                    User.name.ilike(like),
                    User.email.ilike(like),
                    DoctorProfile.specialization.ilike(like),
                )
            )
            .all()
        )
        patients = (
            PatientProfile.query.join(User)
            .filter(
                or_(
                    User.name.ilike(like),
                    User.email.ilike(like),
                    PatientProfile.contact.ilike(like),
                )
            )
            .all()
        )
    return render_template("admin/search.html", doctors=doctors, patients=patients, q=q)

@main.route("/admin/appointments")
@login_required
@admin_required
def admin_appointments():
    today = date.today()
    # Upcoming: Only Booked appointments with future/today date
    upcoming = Appointment.query.filter(
        Appointment.date >= today, 
        Appointment.status == "Booked"
    ).order_by(Appointment.date, Appointment.time_slot).all()
    # Past/History: Completed appointments OR past date appointments (not cancelled)
    past = Appointment.query.filter(
        db.or_(
            Appointment.status == "Completed",
            db.and_(Appointment.date < today, Appointment.status != "Cancelled")
        )
    ).order_by(Appointment.date.desc()).all()
    # Cancelled: All cancelled appointments
    cancelled = Appointment.query.filter_by(status="Cancelled").order_by(Appointment.date.desc()).all()
    return render_template(
        "admin/appointments.html",
        upcoming=upcoming,
        past=past,
        cancelled=cancelled,
        today=today,
    )

@main.route("/admin/appointment/<int:aid>")
@login_required
@admin_required
def admin_view_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    return render_template("admin/appointment_detail.html", appt=appt)

@main.route("/admin/appointment/<int:aid>/status", methods=["POST"])
@login_required
@admin_required
def admin_update_appointment_status(aid):
    appt = Appointment.query.get_or_404(aid)
    new_status = request.form.get("status")
    allowed_statuses = {"Booked", "Completed", "Cancelled"}
    if new_status not in allowed_statuses:
        flash("Invalid status", "warning")
        return redirect(request.referrer or url_for("main.admin_appointments"))
    if appt.status != new_status:
        appt.status = new_status
        db.session.commit()
        flash("Appointment status updated", "success")
    else:
        flash("Appointment already in that status", "info")
    return redirect(request.referrer or url_for("main.admin_appointments"))

@main.route("/admin/patients")
@login_required
@admin_required
def admin_patients():
    q = request.args.get("q", "").strip()
    base_query = PatientProfile.query.join(User)
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            or_(User.name.ilike(like), User.email.ilike(like), PatientProfile.contact.ilike(like))
        )
    patients = base_query.order_by(User.name).all()
    return render_template("admin/patients_list.html", patients=patients, q=q)

@main.route("/admin/patient/<int:pid>")
@login_required
@admin_required
def admin_view_patient(pid):
    patient = PatientProfile.query.get_or_404(pid)
    appointments = (
        Appointment.query.filter_by(patient_id=patient.id)
        .order_by(Appointment.date.desc(), Appointment.time_slot.desc())
        .all()
    )
    return render_template("admin/patient_detail.html", patient=patient, appointments=appointments)

@main.route("/admin/patient/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_patient(pid):
    patient = PatientProfile.query.get_or_404(pid)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        age = request.form.get("age")
        contact = request.form.get("contact", "").strip()

        if not name or not email:
            flash("Name and email are required", "warning")
            return redirect(request.url)

        existing = User.query.filter(User.email == email, User.id != patient.user_id).first()
        if existing:
            flash("Email already in use", "warning")
            return redirect(request.url)

        patient.user.name = name
        patient.user.email = email
        patient.contact = contact or None
        patient.age = int(age) if age else None
        db.session.commit()
        flash("Patient profile updated", "success")
        return redirect(url_for("main.admin_view_patient", pid=patient.id))

    return render_template("admin/patient_form.html", patient=patient)

@main.route("/admin/patient/<int:pid>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_patient(pid):
    patient = PatientProfile.query.get_or_404(pid)
    patient.is_blacklisted = not patient.is_blacklisted
    patient.user.is_active = True # Ensure they can login to see the blacklist message
    db.session.commit()
    state = "re-activated" if not patient.is_blacklisted else "blacklisted"
    flash(f"Patient account {state}", "info")
    return redirect(request.referrer or url_for("main.admin_patients"))

@main.route("/admin/patient/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_patient(pid):
    patient = PatientProfile.query.get_or_404(pid)
    db.session.delete(patient.user)  # cascade removes profile and appointments
    db.session.commit()
    flash("Patient account deleted", "success")
    return redirect(url_for("main.admin_patients"))

# ---------- Patient ----------
def patient_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role!="patient":
            abort(403)
        if current_user.patient_profile and current_user.patient_profile.is_blacklisted:
            return redirect(url_for("main.blacklisted"))
        return func(*args, **kwargs)
    return wrapper

@main.route("/patient/dashboard")
@login_required
@patient_required
def patient_dashboard():
    q = request.args.get("q", "").strip()
    query = DoctorProfile.query.join(User).filter(DoctorProfile.is_blacklisted == False)
    
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.name.ilike(like),
                User.email.ilike(like),
                DoctorProfile.specialization.ilike(like)
            )
        )
        
    doctors = query.all()
    # get appointments for this patient
    patient_profile = current_user.patient_profile
    appointments = patient_profile.appointments if patient_profile else []
    return render_template("patient/dashboard.html", doctors=doctors, appointments=appointments, q=q)

@main.route("/patient/doctor/<int:doctor_id>")
@login_required
@patient_required
def patient_view_doctor_profile(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    return render_template("patient/doctor_profile.html", doctor=doctor)

@main.route("/patient/book/<int:doctor_id>", methods=["GET","POST"])
@login_required
@patient_required
def book_appointment(doctor_id):
    doctor = DoctorProfile.query.get_or_404(doctor_id)
    today = date.today()
    max_date = today + timedelta(days=7)
    
    # Get all availability for next 7 days
    avail = DoctorAvailability.query.filter_by(doctor_id=doctor.id).filter(DoctorAvailability.date >= today).order_by(DoctorAvailability.date, DoctorAvailability.timeslot).all()
    
    # Get all booked appointments for next 7 days to mark them
    booked_appts = Appointment.query.filter_by(doctor_id=doctor.id).filter(Appointment.date >= today, Appointment.status != "Cancelled").all()
    booked_slots = {(a.date.isoformat(), a.time_slot) for a in booked_appts}
    
    if request.method=="POST":
        slot_id = request.form.get("slot")
        if not slot_id:
            flash("Please select a time slot", "warning")
            return redirect(request.url)
            
        slot = DoctorAvailability.query.get_or_404(slot_id)
        if slot.doctor_id != doctor.id:
            abort(403)
        date_obj = slot.date
        time_slot = slot.timeslot
        
        # check slot free
        existing = Appointment.query.filter_by(doctor_id=doctor.id, date=date_obj, time_slot=time_slot).filter(Appointment.status!="Cancelled").first()
        if existing:
            flash("Slot already booked, choose another", "danger")
            return redirect(url_for("main.book_appointment", doctor_id=doctor_id))
            
        appt = Appointment(patient_id=current_user.patient_profile.id, doctor_id=doctor.id, date=date_obj, time_slot=time_slot, status="Booked")
        db.session.add(appt)
        db.session.commit()
        flash("Appointment booked", "success")
        return redirect(url_for("main.patient_dashboard"))
        
    # Group availability by date
    avail_by_date = {}
    for a in avail:
        d_str = a.date.strftime('%Y-%m-%d')
        if d_str not in avail_by_date:
            avail_by_date[d_str] = []
        avail_by_date[d_str].append(a)
        
    # Sort dates
    sorted_dates = sorted(avail_by_date.keys())
        
    return render_template("patient/book_appointment.html", doctor=doctor, avail_by_date=avail_by_date, sorted_dates=sorted_dates, booked_slots=booked_slots)

@main.route("/patient/profile", methods=["GET", "POST"])
@login_required
@patient_required
def patient_profile():
    profile = current_user.patient_profile
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        age = request.form.get("age")
        contact = request.form.get("contact", "").strip()

        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(request.url)

        existing = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing:
            flash("Email already in use.", "warning")
            return redirect(request.url)

        current_user.name = name
        current_user.email = email
        profile.age = int(age) if age else None
        profile.contact = contact or None

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.patient_dashboard"))

    return render_template("patient/profile.html", profile=profile)

@main.route("/patient/appointments")
@login_required
@patient_required
def patient_appointments():
    today = date.today()
    all_appts = current_user.patient_profile.appointments
    # Upcoming: Only Booked appointments with future/today date
    upcoming = [a for a in all_appts if a.status == "Booked" and a.date >= today]
    # Past: Completed appointments OR past date appointments (not cancelled)
    past = [a for a in all_appts if a.status == "Completed" or (a.date < today and a.status != "Cancelled")]
    # Cancelled: All cancelled appointments
    cancelled = [a for a in all_appts if a.status == "Cancelled"]
    # Sort for display
    upcoming.sort(key=lambda x: (x.date, x.time_slot))
    past.sort(key=lambda x: x.date, reverse=True)
    return render_template("patient/appointments.html", upcoming=upcoming, past=past, cancelled=cancelled, today=today)

@main.route("/patient/appointment/<int:aid>")
@login_required
@patient_required
def patient_view_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    if appt.patient.user_id != current_user.id:
        abort(403)
    return render_template("patient/appointment_detail.html", appt=appt)

@main.route("/patient/appointment/<int:aid>/cancel", methods=["POST"])
@login_required
@patient_required
def patient_cancel_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    if appt.patient.user_id != current_user.id:
        abort(403)
    if appt.status == "Completed":
        flash("Cannot cancel a completed appointment", "warning")
    else:
        appt.status = "Cancelled"
        db.session.commit()
        flash("Appointment cancelled", "info")
    return redirect(url_for("main.patient_appointments"))

@main.route("/patient/appointment/<int:aid>/reschedule", methods=["GET", "POST"])
@login_required
@patient_required
def patient_reschedule_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    if appt.patient.user_id != current_user.id:
        abort(403)
    if appt.status != "Booked":
        flash("Only booked appointments can be rescheduled", "warning")
        return redirect(url_for("main.patient_appointments"))
    
    doctor = appt.doctor
    today = date.today()
    avail = DoctorAvailability.query.filter_by(doctor_id=doctor.id).filter(DoctorAvailability.date >= today).order_by(DoctorAvailability.date).all()
    
    if request.method == "POST":
        slot_id = request.form.get("slot")
        slot = DoctorAvailability.query.get_or_404(slot_id)
        if slot.doctor_id != doctor.id:
            abort(403)
        
        # Check if new slot is already booked
        existing = Appointment.query.filter_by(
            doctor_id=doctor.id, date=slot.date, time_slot=slot.timeslot
        ).filter(Appointment.status != "Cancelled", Appointment.id != appt.id).first()
        
        if existing:
            flash("Slot already booked, choose another", "danger")
            return redirect(url_for("main.patient_reschedule_appointment", aid=aid))
        
        appt.date = slot.date
        appt.time_slot = slot.timeslot
        db.session.commit()
        flash("Appointment rescheduled successfully", "success")
        return redirect(url_for("main.patient_appointments"))
    
    return render_template("patient/reschedule.html", appt=appt, doctor=doctor, avail=avail)

# ---------- Doctor ----------
def doctor_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role!="doctor":
            abort(403)
        if current_user.doctor_profile and current_user.doctor_profile.is_blacklisted:
            return redirect(url_for("main.blacklisted"))
        return func(*args, **kwargs)
    return wrapper

@main.route("/doctor/dashboard")
@login_required
@doctor_required
def doctor_dashboard():
    doc_profile = current_user.doctor_profile
    today = date.today()
    
    # Upcoming: Only Booked appointments with today or future date
    upcoming = (
        Appointment.query.filter_by(doctor_id=doc_profile.id, status="Booked")
        .filter(Appointment.date >= today)
        .order_by(Appointment.date, Appointment.time_slot)
        .all()
    )
    
    # Completed appointments
    completed = (
        Appointment.query.filter_by(doctor_id=doc_profile.id, status="Completed")
        .order_by(Appointment.date.desc(), Appointment.time_slot.desc())
        .limit(10)
        .all()
    )
    
    # Cancelled appointments
    cancelled = (
        Appointment.query.filter_by(doctor_id=doc_profile.id, status="Cancelled")
        .order_by(Appointment.date.desc(), Appointment.time_slot.desc())
        .limit(10)
        .all()
    )
    
    patient_map = {}
    for appt in doc_profile.appointments:
        if appt.patient is not None:
            patient_map[appt.patient.id] = appt.patient
    assigned_patients = list(patient_map.values())
    
    return render_template(
        "doctor/dashboard.html",
        upcoming=upcoming,
        completed=completed,
        cancelled=cancelled,
        patients=assigned_patients,
    )

@main.route("/doctor/availability", methods=["GET","POST"])
@login_required
@doctor_required
def doctor_availability():
    dp = current_user.doctor_profile
    today = date.today()
    max_date = today + timedelta(days=7)
    
    # Predefined time slots
    time_slots = [
        "09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00",
        "11:00-11:30", "11:30-12:00", "12:00-12:30", "12:30-13:00",
        "14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00",
        "16:00-16:30", "16:30-17:00", "17:00-17:30", "17:30-18:00",
    ]
    
    # Get existing availability 
    existing_avail = DoctorAvailability.query.filter_by(doctor_id=dp.id).filter(
        DoctorAvailability.date >= today
    ).all()
    existing_set = {(a.date.isoformat(), a.timeslot) for a in existing_avail}
    
    if request.method=="POST":
        date_str = request.form.get("date")
        timeslots = request.form.getlist("timeslots")  # checking Multiple slots
        
        if not date_str:
            flash("Please select a date", "warning")
            return redirect(url_for("main.doctor_availability"))
        
        if not timeslots:
            flash("Please select at least one time slot", "warning")
            return redirect(url_for("main.doctor_availability"))
            
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # make sure dates are under next 7 days
        if date_obj < today or date_obj > max_date:
            flash("Availability must be within next 7 days", "warning")
            return redirect(url_for("main.doctor_availability"))
        
        added_count = 0
        for timeslot in timeslots:
            existing = DoctorAvailability.query.filter_by(
                doctor_id=dp.id, date=date_obj, timeslot=timeslot
            ).first()
            if not existing:
                db.session.add(DoctorAvailability(doctor_id=dp.id, date=date_obj, timeslot=timeslot))
                added_count += 1
        
        db.session.commit()
        if added_count > 0:
            flash(f"{added_count} slot(s) added successfully", "success")
        else:
            flash("All selected slots already exist", "info")
        return redirect(url_for("main.doctor_availability"))
    
    avail = (
        DoctorAvailability.query.filter_by(doctor_id=dp.id)
        .filter(DoctorAvailability.date >= today)
        .order_by(DoctorAvailability.date, DoctorAvailability.timeslot)
        .all()
    )
    
    # Group availability by date 
    avail_by_date = {}
    for a in avail:
        date_key = a.date.strftime('%d %b %Y')
        if date_key not in avail_by_date:
            avail_by_date[date_key] = []
        avail_by_date[date_key].append(a)
    
    return render_template(
        "doctor/availability.html", 
        avail=avail, 
        avail_by_date=avail_by_date,
        today=today, 
        max_date=max_date,
        time_slots=time_slots,
        existing_set=existing_set
    )

@main.route("/doctor/availability/<int:availability_id>/delete", methods=["POST"])
@login_required
@doctor_required
def doctor_remove_availability(availability_id):
    slot = DoctorAvailability.query.get_or_404(availability_id)
    if slot.doctor.user_id != current_user.id:
        abort(403)
    existing_booking = (
        Appointment.query.filter_by(doctor_id=slot.doctor_id, date=slot.date, time_slot=slot.timeslot)
        .filter(Appointment.status != "Cancelled")
        .first()
    )
    if existing_booking:
        flash("Cannot remove slot with a booked appointment", "warning")
        return redirect(url_for("main.doctor_availability"))
    db.session.delete(slot)
    db.session.commit()
    flash("Availability removed", "info")
    return redirect(url_for("main.doctor_availability"))

@main.route("/doctor/appointment/<int:aid>/complete", methods=["GET","POST"])
@login_required
@doctor_required
def doctor_complete_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    if appt.doctor.user_id != current_user.id:
        abort(403)
    if appt.status == "Cancelled":
        flash("Cannot complete a cancelled appointment", "warning")
        return redirect(url_for("main.doctor_dashboard"))
    if request.method=="POST":
        diagnosis = request.form.get("diagnosis")
        prescription = request.form.get("prescription")
        notes = request.form.get("notes")
        appt.status = "Completed"
        treatment = appt.treatment or Treatment(appointment_id=appt.id)
        treatment.diagnosis = diagnosis
        treatment.prescription = prescription
        treatment.notes = notes
        db.session.add(treatment)
        db.session.commit()
        flash("Marked complete and treatment saved", "success")
        return redirect(url_for("main.doctor_dashboard"))
    return render_template("doctor/complete_appointment.html", appt=appt)

@main.route("/doctor/appointment/<int:aid>/cancel", methods=["POST"])
@login_required
@doctor_required
def doctor_cancel_appointment(aid):
    appt = Appointment.query.get_or_404(aid)
    if appt.doctor.user_id != current_user.id:
        abort(403)
    if appt.status == "Completed":
        flash("Cannot cancel a completed appointment", "warning")
    else:
        appt.status = "Cancelled"
        db.session.commit()
        flash("Appointment cancelled", "info")
    return redirect(url_for("main.doctor_dashboard"))

@main.route("/doctor/patient/<int:patient_id>/history")
@login_required
@doctor_required
def doctor_view_patient_history(patient_id):
    patient = PatientProfile.query.get_or_404(patient_id)
    doc_profile = current_user.doctor_profile
    
    # Only show appointments with the current doctor
    upcoming = Appointment.query.filter_by(
        patient_id=patient.id, 
        doctor_id=doc_profile.id,
        status="Booked"
    ).order_by(Appointment.date, Appointment.time_slot).all()
    
    completed = Appointment.query.filter_by(
        patient_id=patient.id,
        doctor_id=doc_profile.id,
        status="Completed"
    ).order_by(Appointment.date.desc()).all()
    
    return render_template(
        "doctor/patient_history.html", 
        patient=patient,
        upcoming=upcoming,
        completed=completed
    )

@main.route("/doctor/profile", methods=["GET", "POST"])
@login_required
@doctor_required
def doctor_profile():
    profile = current_user.doctor_profile
    if profile is None:
        profile = DoctorProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        specialization = request.form.get("specialization", "").strip()
        bio = request.form.get("bio", "").strip()
        contact = request.form.get("contact", "").strip()

        if not name or not email:
            flash("Name and email are required.", "warning")
            return redirect(request.url)

        existing = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing:
            flash("Email already in use.", "warning")
            return redirect(request.url)

        current_user.name = name
        current_user.email = email
        current_user.contact = contact or None
        profile.specialization = specialization or None
        profile.bio = bio or None

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.doctor_dashboard"))

    return render_template("doctor/profile.html", profile=profile)


# Prevent caching of pages to avoid back button access after logout
@main.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response