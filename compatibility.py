# compatibility_scorer.py
import fitz  # PyMuPDF
import requests
import re
import json
import os

# Google Gemini setup
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyAfBnFjJ-80s7iy71wLVGNh2q3NccSjVo0')
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY

def extract_text_from_pdf(pdf_path):
    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text.lower()
    except Exception as e:
        print(f"Failed to extract text from PDF: {str(e)}")
        return ""

def get_compatibility_score(resume_text, job_data):
    prompt = f"""
You are a smart recruiter AI. Analyze the following resume and job details to determine how compatible the candidate is for the job. Be lenient and supportive—if the candidate has related skills or projects, that should be considered. Respond with a score out of 100. If the candidate has everything mentioned dont look for additional things, he'll be a perfect match.

Job Title: {job_data['job_title']}
Company: {job_data['company']}
Experience Required: {job_data['experience']} years
Skills: {', '.join(job_data['skills'])}
Description: {job_data['description']}

Resume Text:
{resume_text}

Respond in this format:
Score: [number out of 100]
Explanation: [why this score was given]
"""

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(GEMINI_URL, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            output = response.json()
            reply = output["candidates"][0]["content"]["parts"][0]["text"]

            score_match = re.search(r"Score:\s*(\d+\.?\d*)", reply)
            explanation_match = re.search(r"Explanation:\s*(.*)", reply, re.DOTALL)

            score = float(score_match.group(1)) if score_match else 0.0
            explanation = explanation_match.group(1).strip() if explanation_match else "Explanation not found."

            return round(score), explanation
        else:
            print(f"Gemini API Error: {response.status_code} - {response.text}")
            return 0, "Failed to get response from Gemini."
    except Exception as e:
        print(f"Exception during Gemini call: {str(e)}")
        return 0, "Exception occurred."