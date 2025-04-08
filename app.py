from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from functools import wraps
from bson.objectid import ObjectId
from flask import send_from_directory
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MongoDB Atlas connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://sahilmurhekar2004:sahilmurhekar@firstinstance.lend0.mongodb.net/?retryWrites=true&w=majority&appName=FirstInstance')
client = MongoClient(MONGO_URI)
db = client['Hirecrest']
users_collection = db['Users']
jobs_collection = db['Jobs']

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
            'name':name,
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

@app.route('/home')
@login_required
def home():
    user_id = session.get('user_id')
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    
    if user['role'] == 'student':
        jobs = list(jobs_collection.find())
        return render_template('jobs-client.html', jobs=jobs)
    elif user['role'] == 'recruiter':
        jobs = list(jobs_collection.find({'recruiter_id': user_id}))
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
        
        compatibility = 75  # Placeholder; implement actual logic if needed
        
        jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$push': {'applied': {
                'user_id': user_id,
                'resume': filename,
                'compatibility': compatibility,
                'applied_date': datetime.now()
            }}}
        )
        
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

@app.route('/list-applicants/<job_id>')
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
    
    applicants = []
    for applicant in job.get('applied', []):
        user = users_collection.find_one({'_id': ObjectId(applicant['user_id'])})
        if user:
            applicants.append({
                'name': user['name'],
                'username': user['username'],
                'email': user['email'],
                'resume': applicant['resume'],
                'compatibility': applicant['compatibility'],
                'applied_date': applicant['applied_date'],
                'user_id': applicant['user_id']  # Add this line
            })
    
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
        flash('Applicant rejected successfully!', 'success')
    except Exception as e:
        flash(f'Error rejecting applicant: {str(e)}', 'danger')
    
    return redirect(url_for('list_applicants', job_id=job_id))

@app.route('/my-applications')
@login_required
def my_applications():
    if session.get('role') != 'student':
        flash('Only students can view their applications', 'danger')
        return redirect(url_for('home'))
    
    user_id = session.get('user_id')
    applied_jobs = list(jobs_collection.find({'applied.user_id': user_id}))
    
    applications = []
    for job in applied_jobs:
        for applicant in job['applied']:
            if applicant['user_id'] == user_id:
                applications.append({
                    'job_title': job['job_title'],
                    'company': job['company'],
                    'resume': applicant['resume'],
                    'applied_date': applicant['applied_date'],
                    'job_id': str(job['_id'])
                })
    
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
        flash('Application withdrawn successfully!', 'success')
    except Exception as e:
        flash(f'Error withdrawing application: {str(e)}', 'danger')
    
    return redirect(url_for('my_applications'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)