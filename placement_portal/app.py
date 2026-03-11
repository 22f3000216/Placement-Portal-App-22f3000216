from flask import Flask, render_template, request, redirect, url_for, session, flash
from main import db, User, Company, Student, Drive, Application
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'placement123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(name='Admin', email='admin@placementportaldashboard.com', role='admin')
        admin.set_password('123456')
        db.session.add(admin)
        db.session.commit()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Email not found', 'danger')
            return redirect(url_for('login'))

        if not user.check_password(password):
            flash('Wrong password', 'danger')
            return redirect(url_for('login'))

        if user.role == 'company':
            company = Company.query.filter_by(user_id=user.id).first()
            if company.status == 'pending':
                flash('Your account is pending admin approval', 'warning')
                return redirect(url_for('login'))
            if company.status == 'rejected':
                flash('Your account was rejected by admin', 'danger')
                return redirect(url_for('login'))
            if company.status == 'blacklisted':
                flash('Your company has been blacklisted', 'danger')
                return redirect(url_for('login'))

        if user.role == 'student':
            student = Student.query.filter_by(user_id=user.id).first()
            if student.is_blacklisted:
                flash('Your account is blacklisted. Contact admin.', 'danger')
                return redirect(url_for('login'))

        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_role'] = user.role

        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'company':
            return redirect(url_for('company_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/register/student', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        roll_no = request.form['roll_no']
        department = request.form['department']
        cgpa = request.form['cgpa']
        skills = request.form['skills']

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('student_register'))

        if Student.query.filter_by(roll_no=roll_no).first():
            flash('Roll number already exists', 'danger')
            return redirect(url_for('student_register'))

        user = User(name=name, email=email, role='student', phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            roll_no=roll_no,
            department=department,
            cgpa=float(cgpa) if cgpa else None,
            skills=skills
        )
        db.session.add(student)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('student_register.html')


@app.route('/register/company', methods=['GET', 'POST'])
def company_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        company_name = request.form['company_name']
        hr_contact = request.form['hr_contact']
        website = request.form['website']
        description = request.form['description']

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('company_register'))

        if Company.query.filter_by(company_name=company_name).first():
            flash('Company name already registered', 'danger')
            return redirect(url_for('company_register'))

        user = User(name=name, email=email, role='company')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        company = Company(
            user_id=user.id,
            company_name=company_name,
            hr_contact=hr_contact,
            website=website,
            description=description
        )
        db.session.add(company)
        db.session.commit()

        flash('Company registered! Wait for admin approval.', 'success')
        return redirect(url_for('login'))

    return render_template('company_register.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('user_role') != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('login'))

    all_students = Student.query.all()
    all_companies = Company.query.all()
    all_drives = Drive.query.all()
    all_applications = Application.query.all()

    pending_drives = Drive.query.filter_by(status='pending').all()
    approved_drives = Drive.query.filter_by(status='approved').all()
    ongoing_drives = Drive.query.filter_by(status='ongoing').all()

    recent_applications = Application.query.order_by(Application.applied_on.desc()).limit(10).all()

    return render_template('admin_dashboard.html',
        all_students=all_students,
        all_companies=all_companies,
        all_drives=all_drives,
        all_applications=all_applications,
        pending_drives=pending_drives,
        approved_drives=approved_drives,
        ongoing_drives=ongoing_drives,
        recent_applications=recent_applications
    )


@app.route('/admin/search')
def admin_search():
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    q = request.args.get('q', '')
    students = []
    companies = []

    if q:
        matched_users = User.query.filter(
            User.role == 'student',
            db.or_(User.name.ilike(f'%{q}%'), User.email.ilike(f'%{q}%'))
        ).all()

        for u in matched_users:
            if u.student:
                students.append(u.student)

        by_roll = Student.query.filter(Student.roll_no.ilike(f'%{q}%')).all()
        for s in by_roll:
            if s not in students:
                students.append(s)

        companies = Company.query.filter(Company.company_name.ilike(f'%{q}%')).all()

    return render_template('admin_search.html', students=students, companies=companies, q=q)


@app.route('/admin/company/approve/<int:id>')
def approve_company(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    company = db.session.get(Company, id)
    company.status = 'approved'
    db.session.commit()
    flash('Company approved!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/company/reject/<int:id>')
def reject_company(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    company = db.session.get(Company, id)
    company.status = 'rejected'
    db.session.commit()
    flash('Company rejected', 'warning')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/company/blacklist/<int:id>')
def blacklist_company(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    company = db.session.get(Company, id)
    company.status = 'blacklisted'
    for drive in company.drives:
        drive.status = 'closed'
    db.session.commit()
    flash('Company blacklisted and all drives closed', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/company/delete/<int:id>')
def delete_company(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    company = db.session.get(Company, id)
    user = company.user
    db.session.delete(user)
    db.session.commit()
    flash('Company deleted', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/student/blacklist/<int:id>', methods=['POST'])
def blacklist_student(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    student = db.session.get(Student, id)
    student.is_blacklisted = not student.is_blacklisted
    db.session.commit()
    msg = 'Student blacklisted' if student.is_blacklisted else 'Student removed from blacklist'
    flash(msg, 'info')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/student/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    student = db.session.get(Student, id)
    if request.method == 'POST':
        student.user.name = request.form['name']
        student.user.phone = request.form['phone']
        student.department = request.form['department']
        student.cgpa = request.form['cgpa']
        student.skills = request.form['skills']
        db.session.commit()
        flash('Student updated', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_student.html', student=student)


@app.route('/admin/student/delete/<int:id>')
def delete_student(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    student = db.session.get(Student, id)
    user = student.user
    db.session.delete(user)
    db.session.commit()
    flash('Student deleted', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/drive/approve/<int:id>')
def approve_drive(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    drive.status = 'approved'
    db.session.commit()
    flash('Drive approved!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/drive/reject/<int:id>')
def reject_drive(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    drive.status = 'rejected'
    db.session.commit()
    flash('Drive rejected', 'warning')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/drive/close/<int:id>')
def close_drive_admin(id):
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    drive.status = 'closed'
    db.session.commit()
    flash('Drive marked as complete', 'info')
    return redirect(url_for('admin_dashboard'))


@app.route('/company/dashboard')
def company_dashboard():
    if session.get('user_role') != 'company':
        flash('Login as company first', 'danger')
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    company = Company.query.filter_by(user_id=user.id).first()

    all_drives = Drive.query.filter_by(company_id=company.id).all()
    pending_drives = [d for d in all_drives if d.status == 'pending']
    approved_drives = [d for d in all_drives if d.status == 'approved']
    ongoing_drives = [d for d in all_drives if d.status == 'ongoing']
    closed_drives = [d for d in all_drives if d.status == 'closed']

    total_applications = Application.query.join(Drive).filter(Drive.company_id == company.id).count()

    return render_template('company_dashboard.html',
        company=company,
        pending_drives=pending_drives,
        approved_drives=approved_drives,
        ongoing_drives=ongoing_drives,
        closed_drives=closed_drives,
        total_drives=len(all_drives),
        total_applications=total_applications
    )


@app.route('/company/drive/create', methods=['GET', 'POST'])
def create_drive():
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    company = Company.query.filter_by(user_id=user.id).first()

    if request.method == 'POST':
        job_title = request.form['job_title']
        description = request.form['description']
        eligibility = request.form['eligibility']
        deadline = request.form['deadline']
        salary = request.form['salary']
        location = request.form['location']

        drive = Drive(
            company_id=company.id,
            job_title=job_title,
            description=description,
            eligibility=eligibility,
            deadline=datetime.strptime(deadline, '%Y-%m-%dT%H:%M'),
            salary=salary,
            location=location,
            status='pending'
        )
        db.session.add(drive)
        db.session.commit()
        flash('Drive created! Waiting for admin approval.', 'success')
        return redirect(url_for('company_dashboard'))

    return render_template('create_drive.html', company=company)


@app.route('/company/drive/edit/<int:id>', methods=['GET', 'POST'])
def edit_drive(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    if request.method == 'POST':
        drive.job_title = request.form['job_title']
        drive.description = request.form['description']
        drive.eligibility = request.form['eligibility']
        drive.salary = request.form['salary']
        drive.location = request.form['location']
        drive.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('Drive updated!', 'success')
        return redirect(url_for('company_dashboard'))
    return render_template('edit_drive.html', drive=drive)


@app.route('/company/drive/delete/<int:id>')
def delete_drive(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    db.session.delete(drive)
    db.session.commit()
    flash('Drive deleted', 'danger')
    return redirect(url_for('company_dashboard'))


@app.route('/company/drive/start/<int:id>')
def start_drive(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    drive.status = 'ongoing'
    db.session.commit()
    flash('Drive is now ongoing', 'success')
    return redirect(url_for('company_dashboard'))


@app.route('/company/drive/close/<int:id>')
def close_drive(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    drive.status = 'closed'
    db.session.commit()
    flash('Drive closed', 'info')
    return redirect(url_for('company_dashboard'))


@app.route('/company/drive/<int:id>/applications')
def view_applications(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    drive = db.session.get(Drive, id)
    applications = Application.query.filter_by(drive_id=id).all()
    return render_template('view_applications.html', drive=drive, applications=applications)


@app.route('/company/application/update/<int:id>', methods=['POST'])
def update_application(id):
    if session.get('user_role') != 'company':
        return redirect(url_for('login'))
    application = db.session.get(Application, id)
    application.status = request.form['status']
    db.session.commit()
    flash('Application status updated', 'success')
    return redirect(url_for('view_applications', id=application.drive_id))


@app.route('/student/dashboard')
def student_dashboard():
    if session.get('user_role') != 'student':
        flash('Login as student first', 'danger')
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    student = Student.query.filter_by(user_id=user.id).first()

    available_drives = Drive.query.filter(Drive.status.in_(['approved', 'ongoing'])).all()
    my_applications = Application.query.filter_by(student_id=student.id).all()
    applied_drive_ids = [a.drive_id for a in my_applications]
    all_companies = Company.query.filter_by(status='approved').all()

    return render_template('student_dashboard.html',
        student=student,
        user=user,
        available_drives=available_drives,
        my_applications=my_applications,
        applied_drive_ids=applied_drive_ids,
        all_companies=all_companies
    )


@app.route('/student/apply/<int:id>', methods=['POST'])
def apply_drive(id):
    if session.get('user_role') != 'student':
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    student = Student.query.filter_by(user_id=user.id).first()

    if Application.query.filter_by(student_id=student.id, drive_id=id).first():
        flash('You already applied to this drive!', 'warning')
        return redirect(url_for('student_dashboard'))

    drive = db.session.get(Drive, id)
    if drive.status not in ['approved', 'ongoing']:
        flash('This drive is not accepting applications', 'warning')
        return redirect(url_for('student_dashboard'))

    application = Application(student_id=student.id, drive_id=id)
    db.session.add(application)
    db.session.commit()
    flash('Applied successfully!', 'success')
    return redirect(url_for('student_dashboard'))


@app.route('/student/history')
def student_history():
    if session.get('user_role') != 'student':
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    student = Student.query.filter_by(user_id=user.id).first()
    my_applications = Application.query.filter_by(student_id=student.id).all()
    return render_template('student_history.html', student=student, my_applications=my_applications)


@app.route('/student/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if session.get('user_role') != 'student':
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    student = Student.query.filter_by(user_id=user.id).first()
    if request.method == 'POST':
        user.name = request.form['name']
        user.phone = request.form['phone']
        student.department = request.form['department']
        student.skills = request.form['skills']
        if request.form['cgpa']:
            student.cgpa = float(request.form['cgpa'])
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('edit_profile.html', student=student, user=user)


@app.route('/student/search')
def student_search():
    if session.get('user_role') != 'student':
        return redirect(url_for('login'))
    q = request.args.get('q', '')
    results = []
    user = db.session.get(User, session['user_id'])
    student = Student.query.filter_by(user_id=user.id).first()
    applied_drive_ids = [a.drive_id for a in student.applications]
    if q:
        results = Drive.query.filter(
            Drive.status.in_(['approved', 'ongoing']),
            db.or_(Drive.job_title.ilike(f'%{q}%'), Drive.location.ilike(f'%{q}%'))
        ).all()
    return render_template('student_search.html', results=results, q=q, applied_drive_ids=applied_drive_ids)


if __name__ == '__main__':
    app.run(debug=True)
