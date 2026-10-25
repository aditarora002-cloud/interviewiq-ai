"""Persistent, user-scoped application data. DATABASE_URL supports PostgreSQL for deployment."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text


def _db_url():
    url = os.getenv('DATABASE_URL', '').strip()
    if url:
        if url.startswith('postgres://'):
            url = 'postgresql+psycopg://' + url[len('postgres://'):]
        elif url.startswith('postgresql://'):
            url = 'postgresql+psycopg://' + url[len('postgresql://'):]
        return url
    raw = Path(os.getenv('DATABASE_PATH', './interviewiq.db'))
    if not raw.is_absolute():
        raw = Path(__file__).resolve().parents[1] / raw
    raw.parent.mkdir(parents=True, exist_ok=True)
    return 'sqlite:///' + str(raw.resolve()).replace('\\', '/')

DB_URL = _db_url()
engine = create_engine(DB_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite:') else {})


def now():
    return datetime.now(timezone.utc).isoformat()


def init():
    with engine.begin() as c:
        c.execute(text('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS auth_tokens (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL, created_at TEXT NOT NULL)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS interviews (
            id TEXT PRIMARY KEY, role TEXT, kind TEXT, difficulty TEXT, questions TEXT,
            answers TEXT, created_at TEXT, completed INTEGER DEFAULT 0, score REAL, feedback TEXT,
            user_id TEXT)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS career_records (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, record_type TEXT NOT NULL,
            role TEXT, company TEXT, resume_text TEXT, job_description TEXT,
            result TEXT NOT NULL, created_at TEXT NOT NULL)'''))
        # Migration from existing single-user SQLite projects. Never assign legacy
        # anonymous interviews to a newly registered account automatically.
        if DB_URL.startswith('sqlite:'):
            cols = {r[1] for r in c.exec_driver_sql('PRAGMA table_info(interviews)')}
            if 'user_id' not in cols:
                c.exec_driver_sql('ALTER TABLE interviews ADD COLUMN user_id TEXT')


def create_user(uid, email, name, password_hash):
    with engine.begin() as c:
        c.execute(text('INSERT INTO users (id,email,name,password_hash,created_at) VALUES (:id,:email,:name,:password,:created)'),
                  {'id': uid, 'email': email, 'name': name, 'password': password_hash, 'created': now()})


def user_by_email(email):
    with engine.connect() as c:
        row = c.execute(text('SELECT * FROM users WHERE email=:email'), {'email': email}).mappings().first()
        return dict(row) if row else None


def user_by_token(token_hash):
    with engine.connect() as c:
        row = c.execute(text('''SELECT u.id,u.email,u.name FROM users u
            JOIN auth_tokens t ON t.user_id=u.id WHERE t.token_hash=:h AND t.expires_at > :now'''),
                        {'h': token_hash, 'now': now()}).mappings().first()
        return dict(row) if row else None


def save_token(token_hash, user_id, expires_at):
    with engine.begin() as c:
        c.execute(text('INSERT INTO auth_tokens (token_hash,user_id,expires_at,created_at) VALUES (:h,:id,:expiry,:created)'),
                  {'h': token_hash, 'id': user_id, 'expiry': expires_at, 'created': now()})


def revoke_token(token_hash):
    with engine.begin() as c:
        c.execute(text('DELETE FROM auth_tokens WHERE token_hash=:h'), {'h': token_hash})


def create(i, role, kind, difficulty, questions, user_id):
    with engine.begin() as c:
        c.execute(text('''INSERT INTO interviews
          (id,role,kind,difficulty,questions,answers,created_at,completed,score,feedback,user_id)
          VALUES (:id,:role,:kind,:difficulty,:questions,:answers,:created,0,NULL,NULL,:user)'''),
          {'id': i, 'role': role, 'kind': kind, 'difficulty': difficulty, 'questions': json.dumps(questions),
           'answers': '[]', 'created': now(), 'user': user_id})


def get(i, user_id):
    with engine.connect() as c:
        row = c.execute(text('SELECT * FROM interviews WHERE id=:id AND user_id=:user'),
                        {'id': i, 'user': user_id}).mappings().first()
        return dict(row) if row else None


def save_answers(i, answers, user_id):
    with engine.begin() as c:
        c.execute(text('UPDATE interviews SET answers=:answers WHERE id=:id AND user_id=:user'),
                  {'answers': json.dumps(answers), 'id': i, 'user': user_id})


def finish(i, score, feedback, user_id):
    with engine.begin() as c:
        c.execute(text('UPDATE interviews SET completed=1,score=:score,feedback=:feedback WHERE id=:id AND user_id=:user'),
                  {'score': score, 'feedback': json.dumps(feedback), 'id': i, 'user': user_id})


def listing(user_id):
    with engine.connect() as c:
        rows = c.execute(text('''SELECT id,role,kind,difficulty,created_at,completed,score
             FROM interviews WHERE user_id=:user ORDER BY created_at DESC LIMIT 100'''),
             {'user': user_id}).mappings().all()
        return [dict(r) for r in rows]


def stats(user_id):
    rows = listing(user_id)
    done = [r for r in rows if r['completed'] and r['score'] is not None]
    return {'total': len(rows), 'completed': len(done),
            'average': round(sum(r['score'] for r in done) / len(done), 1) if done else 0,
            'trend': [{'date': r['created_at'][:10], 'score': r['score']} for r in reversed(done)],
            'recent': rows[:8]}


def previous_questions(user_id, limit=1000):
    with engine.connect() as c:
        rows = c.execute(text('''SELECT questions FROM interviews WHERE user_id=:user
             ORDER BY created_at DESC LIMIT :lim'''), {'user': user_id, 'lim': limit}).all()
    seen = []
    for row in rows:
        try:
            seen.extend(str(q.get('question', '')).strip() for q in json.loads(row[0] or '[]'))
        except (ValueError, TypeError):
            continue
    return seen


def save_record(record_id, user_id, record_type, role, company, resume_text, job_description, result):
    with engine.begin() as c:
        c.execute(text('''INSERT INTO career_records
          (id,user_id,record_type,role,company,resume_text,job_description,result,created_at)
          VALUES (:id,:user,:type,:role,:company,:resume,:job,:result,:created)'''),
          {'id': record_id, 'user': user_id, 'type': record_type, 'role': role, 'company': company,
           'resume': resume_text, 'job': job_description, 'result': json.dumps(result), 'created': now()})


def records(user_id, record_type=None):
    with engine.connect() as c:
        rows = c.execute(text('''SELECT id,record_type,role,company,result,created_at,
             CASE WHEN resume_text IS NOT NULL AND resume_text != '' THEN 1 ELSE 0 END AS has_resume
             FROM career_records WHERE user_id=:user
             AND (:type IS NULL OR record_type=:type)
             ORDER BY created_at DESC LIMIT 100'''),
             {'user': user_id, 'type': record_type}).mappings().all()
    output = []
    for r in rows:
        d = dict(r); d['result'] = json.loads(d['result']); output.append(d)
    return output


def record_detail(record_id, user_id):
    with engine.connect() as c:
        row = c.execute(text('SELECT * FROM career_records WHERE id=:id AND user_id=:user'),
                        {'id': record_id, 'user': user_id}).mappings().first()
    if not row:
        return None
    d = dict(row); d['result'] = json.loads(d['result']); return d


def delete_record(record_id, user_id):
    with engine.begin() as c:
        return c.execute(text('DELETE FROM career_records WHERE id=:id AND user_id=:user'),
                         {'id': record_id, 'user': user_id}).rowcount
