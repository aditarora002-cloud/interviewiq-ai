import io
import json
import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from . import db
from .auth import RegisterBody, LoginBody, register, login, logout, current_user
from .engine import analyze, match, questions, evaluate
from .research import research
from . import studio

app = FastAPI(title='InterviewIQ AI API', version='3.0.0')
origins = ['http://localhost:5173', 'http://127.0.0.1:5173'] + [x.strip().rstrip('/') for x in os.getenv('FRONTEND_ORIGIN', '').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=list(set(origins)), allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type'])
if os.getenv('VERCEL') and not os.getenv('DATABASE_URL', '').strip():
    raise RuntimeError('DATABASE_URL is mandatory on Vercel. Configure hosted PostgreSQL before deployment.')
db.init()
studio.initialize()
app.include_router(studio.router)

class MatchBody(BaseModel):
    resume_text: str = Field(min_length=10, max_length=50000)
    job_description: str = Field(default='', max_length=20000)
    role: str = Field(min_length=2, max_length=160)
    company: str = Field(default='', max_length=160)
    live_research: bool = True

class ResearchBody(BaseModel):
    role: str = Field(min_length=2, max_length=160)
    company: str = Field(min_length=2, max_length=160)
    job_description: str = Field(default='', max_length=20000)

class InterviewBody(BaseModel):
    role: str = 'Data Scientist'
    experience: str = 'Entry level'
    interview_type: str = 'Mixed'
    difficulty: str = 'Medium'
    question_count: int = Field(default=5, ge=1, le=12)
    resume_text: str = Field(default='', max_length=50000)
    job_description: str = Field(default='', max_length=20000)
    company: str = Field(default='', max_length=200)

class AnswerBody(BaseModel):
    question_index: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=10000)

@app.get('/api/health')
def health():
    return {'status': 'ok', 'llm_configured': bool(os.getenv('OPENAI_API_KEY', '').strip()),
            'research_configured': bool(os.getenv('BRAVE_SEARCH_API_KEY', '').strip())}

@app.post('/api/auth/register')
def auth_register(body: RegisterBody):
    return register(body)

@app.post('/api/auth/login')
def auth_login(body: LoginBody):
    return login(body)

@app.post('/api/auth/logout')
def auth_logout(result=Depends(logout)):
    return result

@app.get('/api/auth/me')
def auth_me(user=Depends(current_user)):
    return user


def enriched_match(resume_text, role, company, job_description, live_research=True):
    researched = research(role, company, job_description) if live_research else {
        'status': 'not_requested', 'sources': [], 'research_excerpt': '',
        'note': 'Live research was not requested.', 'role': role, 'company': company
    }
    # Explicit role description is primary evidence. Search snippets only complement
    # it; do not present snippets as full job-posting requirements.
    reference = job_description.strip()
    if not reference and researched['sources']:
        reference = researched['research_excerpt']
    if not reference:
        raise HTTPException(422, 'Paste a genuine job description or configure BRAVE_SEARCH_API_KEY and supply a company to research. No compatibility score was invented.')
    result = match(resume_text, reference, role, company, bool(researched['sources']))
    result['research'] = researched
    result['reference_type'] = 'user-provided job description' if job_description.strip() else 'public web snippets (provisional)'
    result['research_quality'] = 'job-description-grounded' if job_description.strip() else 'weak-search-snippet-evidence'
    result['limitations'] = [
        'Job listings change; open the linked sources to verify current requirements.',
        'A numerical match is an approximate text-alignment score, not a prediction of employer decisions.',
        'Skills or experiences not documented in the resume cannot be inferred.'
    ]
    return result

@app.post('/api/careers/research')
def career_research(body: ResearchBody, user=Depends(current_user)):
    return research(body.role, body.company, body.job_description)

@app.post('/api/resume/analyze')
async def resume(file: UploadFile = File(...),
                 role: str = Form(default=''), company: str = Form(default=''),
                 job_description: str = Form(default=''), live_research: bool = Form(default=True),
                 user=Depends(current_user)):
    name = (file.filename or '').lower()
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, 'File exceeds 5 MB limit.')
    try:
        if name.endswith('.pdf'):
            text_value = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(content)).pages)
        elif name.endswith('.docx'):
            text_value = '\n'.join(p.text for p in Document(io.BytesIO(content)).paragraphs)
        elif name.endswith('.txt'):
            text_value = content.decode('utf-8', errors='replace')
        else:
            raise HTTPException(400, 'Upload a PDF, DOCX, or TXT file.')
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, 'Could not read this document.') from exc
    if not text_value.strip():
        raise HTTPException(400, 'No readable text found. Scanned PDFs may need OCR.')
    text_value = text_value[:50000]
    result = {'filename': file.filename, 'extracted_text': text_value, **analyze(text_value)}
    if role.strip():
        result['target'] = {'role': role.strip(), 'company': company.strip()}
        # Allow a resume-quality check without a job description.
        try:
            result['target_match'] = enriched_match(text_value, role, company, job_description, live_research)
        except HTTPException as exc:
            result['match_unavailable'] = exc.detail
    db.save_record(str(uuid.uuid4()), user['id'], 'resume', role, company, text_value, job_description,
                   {key: value for key, value in result.items() if key != 'extracted_text'})
    return result

@app.post('/api/match')
def do_match(body: MatchBody, user=Depends(current_user)):
    result = enriched_match(body.resume_text, body.role, body.company, body.job_description, body.live_research)
    db.save_record(str(uuid.uuid4()), user['id'], 'match', body.role, body.company,
                   body.resume_text, body.job_description, result)
    return result

@app.get('/api/careers/history')
def career_history(user=Depends(current_user)):
    return db.records(user['id'])

@app.get('/api/careers/history/{record_id}')
def career_detail(record_id: str, user=Depends(current_user)):
    result = db.record_detail(record_id, user['id'])
    if not result: raise HTTPException(404, 'Career analysis not found.')
    return result

@app.delete('/api/careers/history/{record_id}')
def career_delete(record_id: str, user=Depends(current_user)):
    if not db.delete_record(record_id, user['id']):
        raise HTTPException(404, 'Career analysis not found.')
    return {'deleted': True}

@app.post('/api/interviews/generate')
def generate(body: InterviewBody, user=Depends(current_user)):
    qs, mode = questions(body.role, body.experience, body.interview_type, body.difficulty,
                         body.question_count, body.resume_text, body.job_description,
                         db.previous_questions(user['id']), body.company)
    sid = str(uuid.uuid4())
    db.create(sid, body.role, body.interview_type, body.difficulty, qs, user['id'])
    return {'session_id': sid, 'role': body.role, 'interview_type': body.interview_type,
            'difficulty': body.difficulty, 'questions': qs, 'mode': mode}

@app.post('/api/interviews/{sid}/answer')
def answer(sid: str, body: AnswerBody, user=Depends(current_user)):
    session = db.get(sid, user['id'])
    if not session: raise HTTPException(404, 'Interview session not found.')
    qs = json.loads(session['questions']); answers = json.loads(session['answers'])
    if body.question_index >= len(qs): raise HTTPException(400, 'Question index out of range.')
    answers = [a for a in answers if a['question_index'] != body.question_index]
    fb, mode = evaluate(qs[body.question_index]['question'], body.answer,
                        qs[body.question_index].get('ideal_points', []))
    answers.append({'question_index': body.question_index, 'answer': body.answer, 'feedback': fb, 'mode': mode})
    db.save_answers(sid, answers, user['id'])
    return {'question_index': body.question_index, 'feedback': fb, 'mode': mode}

@app.post('/api/interviews/{sid}/finish')
def finish(sid: str, user=Depends(current_user)):
    session = db.get(sid, user['id'])
    if not session: raise HTTPException(404, 'Interview session not found.')
    answers = json.loads(session['answers'])
    if not answers: raise HTTPException(400, 'Answer at least one question before finishing.')
    score = round(sum(a['feedback']['score'] for a in answers)/len(answers), 1)
    feedback = {'answered': len(answers), 'total_questions': len(json.loads(session['questions'])),
                'strengths': list(dict.fromkeys(x for a in answers for x in a['feedback'].get('strengths', [])))[:5],
                'improvements': list(dict.fromkeys(x for a in answers for x in a['feedback'].get('improvements', [])))[:8]}
    db.finish(sid, score, feedback, user['id'])
    return {'session_id': sid, 'score': score, **feedback}

@app.get('/api/interviews')
def history(user=Depends(current_user)):
    return db.listing(user['id'])

@app.get('/api/interviews/{sid}')
def detail(sid: str, user=Depends(current_user)):
    session = db.get(sid, user['id'])
    if not session: raise HTTPException(404, 'Interview session not found.')
    session['questions'] = json.loads(session['questions']); session['answers'] = json.loads(session['answers'])
    session['feedback'] = json.loads(session['feedback']) if session['feedback'] else None
    return session

@app.get('/api/analytics')
def analytics(user=Depends(current_user)):
    return db.stats(user['id'])

@app.get('/api/interviews/{sid}/report')
def report(sid: str, user=Depends(current_user)):
    session = db.get(sid, user['id'])
    if not session: raise HTTPException(404, 'Interview session not found.')
    qs = json.loads(session['questions']); answers = json.loads(session['answers']); buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter); _, height = letter; y = height - 50
    c.setFont('Helvetica-Bold', 17); c.drawString(45, y, 'InterviewIQ AI - Practice Report'); y -= 30
    c.setFont('Helvetica', 10)
    for line in [f"Role: {session['role']}", f"Type: {session['kind']} | Difficulty: {session['difficulty']}",
                 f"Date: {session['created_at'][:10]}",
                 f"Overall score: {session['score'] if session['score'] is not None else 'Not completed'}",
                 'Practice feedback only; not a hiring prediction.']:
        c.drawString(45, y, line[:105]); y -= 17
    y -= 10
    for a in answers:
        q = qs[a['question_index']]
        for line in [f"Q{a['question_index']+1}: {q['question']}", f"Score: {a['feedback']['score']}",
                     'Answer: ' + a['answer'][:200],
                     'Improvements: ' + '; '.join(a['feedback'].get('improvements', [])[:3])]:
            if y < 65: c.showPage(); y = height - 50; c.setFont('Helvetica', 10)
            c.drawString(45, y, line.encode('latin1', 'replace').decode('latin1')[:105]); y -= 15
        y -= 8
    c.save(); buf.seek(0)
    return StreamingResponse(buf, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="interviewiq-{sid[:8]}.pdf"'})
