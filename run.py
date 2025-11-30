from app import create_app, db
from app.models import User, DoctorProfile, PatientProfile
from werkzeug.security import generate_password_hash

app = create_app()

def create_admin_if_missing():
    # Admin email and password 
    admin_email = "admin@gmail.com"
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(
            name="Admin",
            email=admin_email,
            role="admin",
            password_hash=generate_password_hash("admin123")
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created:", admin_email, "password: admin123")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin_if_missing()
    app.run(debug=True)
