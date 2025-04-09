from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from pymongo import MongoClient # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from functools import wraps
from bson.objectid import ObjectId # type: ignore
from datetime import datetime
from compatibility import extract_text_from_pdf, get_compatibility_score
from flask_mail import Mail, Message
from dotenv import load_dotenv  # Import python-dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Load SECRET_KEY from .env
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Or your preferred SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')  # Load from .env
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD')  # Load from .env
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

mail = Mail(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MongoDB Atlas connection
MONGO_URI = os.getenv('MONGO_URI')  # Load MONGO_URI from .env
client = MongoClient(MONGO_URI)
db = client['Hirecrest']
users_collection = db['Users']
jobs_collection = db['Jobs']
interviews_collection = db['Interviews']  # New collection for interviews

# Create unique indexes
users_collection.create_index('username', unique=True)
users_collection.create_index('email', unique=True)

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        gender = request.form['gender']
        role = request.form['role']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if users_collection.find_one({'username': username}):
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        new_user = {
            'name': name,
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'gender': gender,
            'role': role
        }
        
        try:
            users_collection.insert_one(new_user)
            flash('Registration successful! Please login', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/home', methods=['GET'])
@login_required
def home():
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    search_query = request.args.get('search', '').strip().lower()

    if user['role'] == 'student':
        # Filter jobs based on search query
        query = {}
        if search_query:
            query = {
                '$or': [
                    {'job_title': {'$regex': search_query, '$options': 'i'}},
                    {'company': {'$regex': search_query, '$options': 'i'}},
                    {'skills': {'$regex': search_query, '$options': 'i'}},
                    {'location': {'$regex': search_query, '$options': 'i'}}
                ]
            }
        jobs = list(jobs_collection.find(query))
        return render_template('jobs-client.html', jobs=jobs)
    elif user['role'] == 'recruiter':
        # Filter jobs posted by the recruiter
        query = {'recruiter_id': user_id}
        if search_query:
            query['$or'] = [
                {'job_title': {'$regex': search_query, '$options': 'i'}},
                {'company': {'$regex': search_query, '$options': 'i'}},
                {'skills': {'$regex': search_query, '$options': 'i'}},
                {'location': {'$regex': search_query, '$options': 'i'}}
            ]
        jobs = list(jobs_collection.find(query))
        return render_template('jobs-admin.html', jobs=jobs)
    else:
        flash('Invalid role detected', 'danger')
        return redirect(url_for('logout'))

@app.route('/post-job', methods=['POST'])
@login_required
def post_job():
    if session.get('role') != 'recruiter':
        flash('Only recruiters can post jobs', 'danger')
        return redirect(url_for('home'))
    
    try:
        job_title = request.form.get('job_title')
        company = request.form.get('company')
        salary = request.form.get('salary')
        experience = request.form.get('experience')
        job_type = request.form.get('job_type')
        location = request.form.get('location')
        skills = request.form.get('skills')
        description = request.form.get('description')
        
        new_job = {
            'job_title': job_title,
            'company': company,
            'salary': salary,
            'experience': experience,
            'job_type': job_type,
            'location': location,
            'skills': skills.split(','),
            'description': description,
            'posted_date': datetime.now(),
            'recruiter_id': session.get('user_id'),
            'applied': []
        }
        
        jobs_collection.insert_one(new_job)
        flash('Job posted successfully!', 'success')
    except Exception as e:
        flash(f'Error posting job: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

@app.route('/apply-job/<job_id>', methods=['POST'])
@login_required
def apply_job(job_id):
    if session.get('role') != 'student':
        flash('Only students can apply for jobs', 'danger')
        return redirect(url_for('home'))
    
    job = jobs_collection.find_one({'_id': ObjectId(job_id)})
    if not job:
        flash('Job not found', 'danger')
        return redirect(url_for('home'))
    
    user_id = session.get('user_id')
    
    # Check if the student has already applied
    for applicant in job.get('applied', []):
        if applicant['user_id'] == user_id:
            flash('You have already applied to this job!', 'warning')
            return redirect(url_for('home'))
    
    try:
        resume_file = request.files.get('resume')
        
        if not resume_file or resume_file.filename == '':
            flash('No resume file selected', 'danger')
            return redirect(url_for('home'))
        
        if not allowed_file(resume_file.filename):
            flash('Invalid file type. Please upload PDF, DOC, or DOCX', 'danger')
            return redirect(url_for('home'))
        
        filename = secure_filename(f"{user_id}_{job_id}_{resume_file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resume_file.save(file_path)
        
        # Extract resume text and calculate compatibility score
        resume_text = extract_text_from_pdf(file_path)
        compatibility, explanation = get_compatibility_score(resume_text, job)
        
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$push': {'applied': {
                'user_id': user_id,
                'resume': filename,
                'compatibility': compatibility,
                'applied_date': datetime.now()
            }}}
        )
        print(explanation)  # Fixed typo 'explaination' to 'explanation'
        flash('Application submitted successfully!', 'success')
    except Exception as e:
        flash(f'Error applying for job: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

@app.route('/delete-job/<job_id>')
@login_required
def delete_job(job_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can delete jobs', 'danger')
        return redirect(url_for('home'))
    
    try:
        job = jobs_collection.find_one({
            '_id': ObjectId(job_id),
            'recruiter_id': session.get('user_id')
        })
        
        if not job:
            flash('Job not found or you do not have permission to delete it', 'danger')
            return redirect(url_for('home'))
        
        jobs_collection.delete_one({'_id': ObjectId(job_id)})
        flash('Job deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting job: {str(e)}', 'danger')
    
    return redirect(url_for('home'))

@app.route('/list-applicants/<job_id>', methods=['GET'])
@login_required
def list_applicants(job_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can view applicants', 'danger')
        return redirect(url_for('home'))

    job = jobs_collection.find_one({
        '_id': ObjectId(job_id),
        'recruiter_id': session.get('user_id')
    })
    if not job:
        flash('Job not found or you do not have permission to view it', 'danger')
        return redirect(url_for('home'))

    search_query = request.args.get('search', '').strip().lower()
    applicants = []
    for applicant in job.get('applied', []):
        user = users_collection.find_one({'_id': ObjectId(applicant['user_id'])})
        if user:
            applicant_data = {
                'name': user['name'],
                'username': user['username'],
                'email': user['email'],
                'resume': applicant['resume'],
                'compatibility': applicant['compatibility'],
                'applied_date': applicant['applied_date'],
                'user_id': applicant['user_id']
            }
            # Filter applicants based on search query
            if not search_query or (
                search_query in user['name'].lower() or
                search_query in user['email'].lower() or
                search_query in user['username'].lower()
            ):
                applicants.append(applicant_data)

    return render_template('list-admin.html', job=job, applicants=applicants)

@app.route('/download-resume/<filename>')
@login_required
def download_resume(filename):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can download resumes', 'danger')
        return redirect(url_for('home'))
    
    try:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except Exception as e:
        flash(f'Error downloading resume: {str(e)}', 'danger')
        return redirect(url_for('home'))

@app.route('/reject-applicant/<job_id>/<user_id>', methods=['POST'])
@login_required
def reject_applicant(job_id, user_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can reject applicants', 'danger')
        return redirect(url_for('home'))
    
    job = jobs_collection.find_one({
        '_id': ObjectId(job_id),
        'recruiter_id': session.get('user_id')
    })
    
    if not job:
        flash('Job not found or you do not have permission to modify it', 'danger')
        return redirect(url_for('home'))
    
    try:
        # Remove the student's application from the applied array
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$pull': {'applied': {'user_id': user_id}}}
        )
        
        # Also remove any scheduled interviews for this candidate and job
        interviews_collection.delete_many({
            'job_id': job_id,
            'user_id': user_id
        })
        
        flash('Applicant rejected successfully!', 'success')
    except Exception as e:
        flash(f'Error rejecting applicant: {str(e)}', 'danger')
    
    return redirect(url_for('list_applicants', job_id=job_id))

@app.route('/my-applications', methods=['GET'])
@login_required
def my_applications():
    if session.get('role') != 'student':
        flash('Only students can view their applications', 'danger')
        return redirect(url_for('home'))

    user_id = session.get('user_id')
    search_query = request.args.get('search', '').strip().lower()
    applied_jobs = list(jobs_collection.find({'applied.user_id': user_id}))
    applications = []

    for job in applied_jobs:
        for applicant in job['applied']:
            if applicant['user_id'] == user_id:
                application_data = {
                    'job_title': job['job_title'],
                    'company': job['company'],
                    'resume': applicant['resume'],
                    'applied_date': applicant['applied_date'],
                    'job_id': str(job['_id'])
                }
                # Filter applications based on search query
                if not search_query or (
                    search_query in job['job_title'].lower() or
                    search_query in job['company'].lower() or
                    search_query in job['location'].lower()
                ):
                    applications.append(application_data)

    return render_template('list-client.html', applications=applications)

@app.route('/withdraw-application/<job_id>', methods=['POST'])
@login_required
def withdraw_application(job_id):
    if session.get('role') != 'student':
        flash('Only students can withdraw applications', 'danger')
        return redirect(url_for('home'))
    
    user_id = session.get('user_id')
    job = jobs_collection.find_one({'_id': ObjectId(job_id)})
    
    if not job:
        flash('Job not found', 'danger')
        return redirect(url_for('my_applications'))
    
    # Check if the student has applied
    applied = False
    for applicant in job.get('applied', []):
        if applicant['user_id'] == user_id:
            applied = True
            break
    
    if not applied:
        flash('You have not applied to this job!', 'warning')
        return redirect(url_for('my_applications'))
    
    try:
        # Remove the student's application from the applied array
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$pull': {'applied': {'user_id': user_id}}}
        )
        
        # Also remove any scheduled interviews for this candidate and job
        interviews_collection.delete_many({
            'job_id': job_id,
            'user_id': user_id
        })
        
        flash('Application withdrawn successfully!', 'success')
    except Exception as e:
        flash(f'Error withdrawing application: {str(e)}', 'danger')
    
    return redirect(url_for('my_applications'))

@app.route('/schedule-interview/<job_id>/<user_id>', methods=['POST'])
@login_required
def schedule_interview(job_id, user_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can schedule interviews', 'danger')
        return redirect(url_for('home'))

    job = jobs_collection.find_one({
        '_id': ObjectId(job_id),
        'recruiter_id': session.get('user_id')
    })
    if not job:
        flash('Job not found or you do not have permission to modify it', 'danger')
        return redirect(url_for('list_applicants', job_id=job_id))

    user = users_collection.find_one({'_id': ObjectId(user_id)})
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('list_applicants', job_id=job_id))

    # Check if an interview already exists for this job and user
    existing_interview = interviews_collection.find_one({
        'job_id': job_id,
        'user_id': user_id
    })
    
    if existing_interview:
        flash(f'An interview is already scheduled for {user["name"]} for the position of {job["job_title"]} at {job["company"]} on {existing_interview["scheduled_date"]} at {existing_interview["scheduled_time"]}', 'warning')
        return redirect(url_for('list_applicants', job_id=job_id))

    try:
        scheduled_date = request.form.get('date')
        scheduled_time = request.form.get('time')

        interview_data = {
            'user_id': user_id,
            'user_name': user['name'],
            'email': user['email'],
            'job_id': job_id,
            'job_name': job['job_title'],
            'company': job['company'],
            'scheduled_date': scheduled_date,
            'scheduled_time': scheduled_time,
            'recruiter_id': session.get('user_id'),
            'created_at': datetime.now()
        }

        interviews_collection.insert_one(interview_data)
        
        # Send email notification to the applicant
        msg = Message(
            subject=f"Interview Scheduled - {job['job_title']} at {job['company']}",
            recipients=[user['email']]
        )
        
        msg.html = render_template(
            'interview-notification.html',
            user_name=user['name'],
            job_title=job['job_title'],
            company=job['company'],
            date=scheduled_date,
            time=scheduled_time
        )
        
        mail.send(msg)
        
        flash('Interview scheduled successfully and notification sent!', 'success')
    except Exception as e:
        flash(f'Error scheduling interview: {str(e)}', 'danger')

    return redirect(url_for('list_applicants', job_id=job_id))

@app.route('/scheduled-interviews', methods=['GET'])
@login_required
def scheduled_interviews():
    if session.get('role') != 'recruiter':
        flash('Only recruiters can view scheduled interviews', 'danger')
        return redirect(url_for('home'))

    recruiter_id = session.get('user_id')
    search_query = request.args.get('search', '').strip().lower()

    query = {'recruiter_id': recruiter_id}
    if search_query:
        query['$or'] = [
            {'user_name': {'$regex': search_query, '$options': 'i'}},
            {'job_name': {'$regex': search_query, '$options': 'i'}},
            {'email': {'$regex': search_query, '$options': 'i'}}
        ]

    interviews = list(interviews_collection.find(query))
    return render_template('schedule-admin.html', interviews=interviews)

@app.route('/reject-interview/<interview_id>', methods=['POST'])
@login_required
def reject_interview(interview_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can reject interviews', 'danger')
        return redirect(url_for('home'))
    
    interview = interviews_collection.find_one({
        '_id': ObjectId(interview_id),
        'recruiter_id': session.get('user_id')
    })
    
    if not interview:
        flash('Interview not found or you do not have permission to modify it', 'danger')
        return redirect(url_for('scheduled_interviews'))
    
    try:
        # Remove the interview
        interviews_collection.delete_one({'_id': ObjectId(interview_id)})
        
        # Also remove the applicant from the job's applied list if needed
        job_id = interview['job_id']
        user_id = interview['user_id']
        
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$pull': {'applied': {'user_id': user_id}}}
        )
        
        flash('Interview rejected successfully!', 'success')
    except Exception as e:
        flash(f'Error rejecting interview: {str(e)}', 'danger')
    
    return redirect(url_for('scheduled_interviews'))

@app.route('/select-applicant/<interview_id>', methods=['POST'])
@login_required
def select_applicant(interview_id):
    if session.get('role') != 'recruiter':
        flash('Only recruiters can select applicants', 'danger')
        return redirect(url_for('home'))
    
    interview = interviews_collection.find_one({
        '_id': ObjectId(interview_id),
        'recruiter_id': session.get('user_id')
    })
    
    if not interview:
        flash('Interview not found or you do not have permission to modify it', 'danger')
        return redirect(url_for('scheduled_interviews'))
    
    try:
        # Send email notification to the selected applicant
        msg = Message(
            subject=f"Congratulations! You've Been Selected - {interview['job_name']} at {interview['company']}",
            recipients=[interview['email']]
        )
        
        msg.html = render_template(
            'selection-notification.html',
            user_name=interview['user_name'],
            job_title=interview['job_name'],
            company=interview['company'],
            scheduled_date=interview['scheduled_date'],
            scheduled_time=interview['scheduled_time']
        )
        
        mail.send(msg)
        
        # Remove the interview from interviews_collection
        interviews_collection.delete_one({'_id': ObjectId(interview_id)})
        
        # Remove the applicant from the job's applied array
        job_id = interview['job_id']
        user_id = interview['user_id']
        
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$pull': {'applied': {'user_id': user_id}}}
        )
        
        flash('Applicant selected successfully, notification sent, and application removed!', 'success')
    except Exception as e:
        flash(f'Error selecting applicant: {str(e)}', 'danger')
    
    return redirect(url_for('scheduled_interviews'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))  # Railway provides PORT, fallback to 5000 locally
    host = "0.0.0.0"  # Bind to all interfaces for Railway
    app.run(host=host, port=port, debug=False)  # Disable debug for production
