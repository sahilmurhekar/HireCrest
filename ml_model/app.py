import streamlit as st
import fitz  # PyMuPDF
import requests
import re
import json

# === Google Gemini setup ===
GEMINI_API_KEY = "AIzaSyAfBnFjJ-80s7iy71wLVGNh2q3NccSjVo0"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY

# === Extract PDF resume text ===
def extract_text_from_pdf(pdf_file):
    try:
        text = ""
        with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text.lower()
    except Exception as e:
        st.error(f"Failed to extract text from PDF: {str(e)}")
        return ""

# === Call Gemini to analyze job + resume ===
def get_gemini_analysis(resume_text, job_data):
    prompt = f"""
You are a smart recruiter AI. Analyze the following resume and job details to determine how compatible the candidate is for the job. Be lenient and supportive—if the candidate has related skills or projects, that should be considered. Respond with a score out of 100 and give a brief explanation. If the candidate has everything mentioned dont look for additional things, he'll be a perfect match.

Job Title: {job_data['job_title']}
Company: {job_data['company_name']}
Experience Required: {job_data['experience']} years
Skills: {job_data['skills']}
Description: {job_data['job_description']}

Resume Text:
{resume_text}

Respond in this format:
Score: [number out of 100]
Explanation: [why this score was given]
"""

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
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

            return score, explanation
        else:
            st.error(f"Gemini API Error: {response.status_code} - {response.text}")
            return 0.0, "Failed to get response from Gemini."
    except Exception as e:
        st.error(f"Exception during Gemini call: {str(e)}")
        return 0.0, "Exception occurred."

# === Streamlit App ===
def main():
    st.title("AI Job Compatibility Analyzer (Powered by Gemini)")

    st.sidebar.header("Instructions")
    st.sidebar.write("""
    1. Fill in the job details and upload the resume (PDF).
    2. View the compatibility score and explanation.
    """)

    st.header("Job Details")
    with st.form("job_form"):
        job_title = st.text_input("Job Title")
        company_name = st.text_input("Company Name")
        experience = st.number_input("Experience Required (years)", min_value=0.0)
        salary = st.number_input("Salary Offered (INR)", min_value=0)
        job_type = st.selectbox("Job Type", ["Internship", "Full time", "Part time", "Freelance"])
        location_type = st.selectbox("Location Type", ["On-site", "Hybrid", "Remote"])
        skills = st.text_input("Key Skills (comma-separated)")
        job_desc = st.text_area("Job Description")
        submitted = st.form_submit_button("Submit Job Details")

    st.header("Upload Resume")
    resume_file = st.file_uploader("Upload Resume (PDF only)", type=["pdf"])

    if submitted and resume_file:
        job_data = {
            "job_title": job_title,
            "company_name": company_name,
            "experience": experience,
            "salary": salary,
            "job_type": job_type,
            "location_type": location_type,
            "skills": skills,
            "job_description": job_desc
        }

        with st.spinner("Reading resume and analyzing with Gemini..."):
            resume_text = extract_text_from_pdf(resume_file)
            if resume_text:
                score, explanation = get_gemini_analysis(resume_text, job_data)
                st.subheader("Gemini Compatibility Score")
                st.write(f"Score: {score:.1f}%")
                st.progress(min(score / 100, 1.0))
                st.write("Explanation:")
                st.write(explanation)

                with st.expander("View Raw Resume Text"):
                    st.text(resume_text)

if __name__ == "__main__":
    main()
