# Hirecrest - Job Recruitment Platform

Hirecrest is a Flask-based web application designed to streamline job recruitment processes. It allows recruiters to post job listings, students to apply with resumes, and facilitates interview scheduling with email notifications. The app features role-based access (recruiters and students), resume compatibility scoring, and MongoDB Atlas for data persistence.

## Features

- **User Authentication**: Register and log in as a student or recruiter with secure password hashing.
- **Job Management**:
  - Recruiters can post, view, and delete job listings.
  - Students can browse and apply to jobs with resume uploads.
- **Application Management**:
  - Students can view and withdraw their applications.
  - Recruiters can view applicants, download resumes, and reject candidates.
- **Interview Scheduling**:
  - Recruiters can schedule interviews and notify candidates via email.
  - Options to reject or select candidates post-interview with automated notifications.
- **Resume Compatibility**: Automatically scores resumes against job requirements.
- **Search Functionality**: Filter jobs, applications, and interviews by keywords.
- **Email Notifications**: Integrated with Flask-Mail for interview and selection updates.

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: MongoDB Atlas (via PyMongo)
- **Security**: Werkzeug for password hashing
- **File Uploads**: Supports PDF, DOC, DOCX resumes (16MB max)
- **Email**: Flask-Mail with SMTP (Gmail configured)
- **Environment**: Managed via `.env` file with python-dotenv

## Prerequisites

- Python 3.8+
- MongoDB Atlas account
- Gmail account for email notifications (or another SMTP server)
- Git (optional, for cloning)

## Installation

1. **Clone the Repository**:
   ```
   git clone https://github.com/sahilmurhekar/HireCrest
   cd hirecrest
2. **Set Up a Virtual Environment:**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
3. **Install Dependencies**:
   ```
   pip install -r requirements.txt
4. **Configure Environment Variables**:
   Create a .env file in the root directory with the following:
   ```
   SECRET_KEY=your-secret-key
   MONGO_URI=your-mongodb-atlas-uri
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=your-email-app-password
   GEMINI_API_KEY=gemini-api
5. **Set Up Upload Folder**:
   The app automatically creates static/uploads/resumes for resume storage.


## Usage

1. **Run the Application**:
   ```
   python app.py
  The app runs on http://127.0.0.1:5000 in debug mode.

## Structure

```
hirecrest/
├── static/
│   ├── uploads/
│   │   └── resumes/    # Resume storage
│   └── ...             # CSS, JS, etc.
├── templates/          # HTML templates
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── jobs-client.html
│   ├── jobs-admin.html
│   ├── list-client.html
│   ├── list-admin.html
│   ├── schedule-admin.html
│   ├── interview-notification.html
│   └── selection-notification.html
├── .env                # Environment variables (not tracked)
├── app.py              # Main Flask application
├── compatibility.py    # Resume extraction and scoring logic
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Contributing

1. Fork the repository.
2. Create a feature branch (git checkout -b feature-name).
3. Commit changes (git commit -m "Add feature").
4. Push to the branch (git push origin feature-name).
5. Open a Pull Request.
