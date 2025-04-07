from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
from bson.objectid import ObjectId

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# MongoDB Atlas connection
# Replace with your MongoDB Atlas connection string
# Format: mongodb+srv://<username>:<password>@<cluster-url>/
# Example: mongodb+srv://myuser:mypassword@cluster0.abcde.mongodb.net/
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://sahilmurhekar2004:sahilmurhekar@firstinstance.lend0.mongodb.net/?retryWrites=true&w=majority&appName=FirstInstance')

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['HireCrest']  # Database name
users_collection = db['Users']  # Collection name

# Create unique indexes for username and email
users_collection.create_index('username', unique=True)
users_collection.create_index('email', unique=True)

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
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        gender = request.form['gender']
        role = request.form['role']
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        # Check if username exists
        if users_collection.find_one({'username': username}):
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Check if email exists
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user document
        new_user = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'gender': gender,
            'role': role
        }
        
        # Insert new user
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
        return render_template('jobs-client.html')  # Redirect to student portal
    elif user['role'] == 'recruiter':
        return render_template('jobs-admin.html')  # Redirect to recruiter portal
    else:
        flash('Invalid role detected', 'danger')
        return redirect(url_for('logout'))  # Logout if role is invalid

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=3000)