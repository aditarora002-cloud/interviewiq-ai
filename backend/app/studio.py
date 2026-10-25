"""InterviewIQ Studio: account-scoped goal planner, application pipeline, learning cards,
practice challenges, profile controls, and portable user data. No external services required.
"""
import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from . import db
from .auth import current_user, hash_password, verify_password
from .engine import evaluate
from .question_bank import CATALOG, domain_for

router = APIRouter(prefix='/api/studio', tags=['Career Studio'])


def uid():
    return str(uuid.uuid4())


def initialize():
    with db.engine.begin() as c:
        c.execute(text('''CREATE TABLE IF NOT EXISTS applications (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, company TEXT NOT NULL, role TEXT NOT NULL,
          stage TEXT NOT NULL, url TEXT, location TEXT, salary TEXT, notes TEXT,
          next_action TEXT, due_date TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS study_tasks (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL,
          priority TEXT NOT NULL, due_date TEXT, done INTEGER NOT NULL DEFAULT 0,
          source TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS flashcards (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, front TEXT NOT NULL, back TEXT NOT NULL,
          topic TEXT NOT NULL, interval_days INTEGER NOT NULL DEFAULT 0,
          ease REAL NOT NULL DEFAULT 2.5, repetitions INTEGER NOT NULL DEFAULT 0,
          due_date TEXT NOT NULL, created_at TEXT NOT NULL)'''))
        c.execute(text('''CREATE TABLE IF NOT EXISTS daily_attempts (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL, date_key TEXT NOT NULL,
          role TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL,
          score REAL NOT NULL, feedback TEXT NOT NULL, created_at TEXT NOT NULL)'''))


class Application(BaseModel):
    company: str = Field(min_length=2, max_length=140)
    role: str = Field(min_length=2, max_length=140)
    stage: str = 'Wishlist'
    url: str = Field(default='', max_length=1000)
    location: str = Field(default='', max_length=160)
    salary: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=3000)
    next_action: str = Field(default='', max_length=250)
    due_date: str = Field(default='', max_length=10)


STAGES = ['Wishlist', 'Applied', 'Screening', 'Interview', 'Offer', 'Accepted', 'Rejected', 'Withdrawn']


class StudyTask(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    category: str = Field(default='General', max_length=80)
    priority: str = Field(default='Medium')
    due_date: str = Field(default='', max_length=10)
    source: str = Field(default='Manual', max_length=100)
    done: bool = False


class FlashCard(BaseModel):
    front: str = Field(min_length=5, max_length=900)
    back: str = Field(min_length=3, max_length=1400)
    topic: str = Field(default='General', max_length=80)


class Review(BaseModel):
    result: str


class ChallengeAnswer(BaseModel):
    role: str = Field(default='Software Engineer', min_length=2, max_length=160)
    date_key: str = Field(max_length=10)
    question: str = Field(min_length=12, max_length=1000)
    answer: str = Field(min_length=5, max_length=10000)


class ProfileChange(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=10, max_length=128)


class DeleteAccount(BaseModel):
    password: str
    confirmation: str


def rows(sql, args):
    with db.engine.connect() as c:
        return [dict(x) for x in c.execute(text(sql), args).mappings().all()]


def item(sql, args):
    with db.engine.connect() as c:
        r = c.execute(text(sql), args).mappings().first()
        return dict(r) if r else None


def execute(sql, args):
    with db.engine.begin() as c:
        return c.execute(text(sql), args).rowcount


def ensure_date(value):
    if value:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise HTTPException(422, 'Use YYYY-MM-DD for dates.')
    return value


@router.get('/applications')
def applications(user=Depends(current_user)):
    return rows('SELECT * FROM applications WHERE user_id=:u ORDER BY updated_at DESC', {'u': user['id']})


@router.post('/applications')
def add_application(data: Application, user=Depends(current_user)):
    if data.stage not in STAGES:
        raise HTTPException(422, 'Invalid application stage')
    ensure_date(data.due_date)
    if data.url and not re.match(r'^https?://[^/\s]+', data.url, re.I):
        raise HTTPException(422, 'Job posting links must start with https:// or http://')
    a = data.model_dump(); a.update(id=uid(), u=user['id'], time=db.now())
    execute('''INSERT INTO applications (id,user_id,company,role,stage,url,location,salary,notes,next_action,due_date,created_at,updated_at)
      VALUES (:id,:u,:company,:role,:stage,:url,:location,:salary,:notes,:next_action,:due_date,:time,:time)''', a)
    return {'id': a['id'], 'saved': True}


@router.put('/applications/{record_id}')
def edit_application(record_id: str, data: Application, user=Depends(current_user)):
    if data.stage not in STAGES:
        raise HTTPException(422, 'Invalid application stage')
    ensure_date(data.due_date)
    if data.url and not re.match(r'^https?://[^/\s]+', data.url, re.I):
        raise HTTPException(422, 'Job posting links must start with https:// or http://')
    a = data.model_dump(); a.update(id=record_id, u=user['id'], time=db.now())
    count=execute('''UPDATE applications SET company=:company,role=:role,stage=:stage,url=:url,
      location=:location,salary=:salary,notes=:notes,next_action=:next_action,
      due_date=:due_date,updated_at=:time WHERE id=:id AND user_id=:u''', a)
    if not count: raise HTTPException(404, 'Application not found')
    return {'updated': True}


@router.delete('/applications/{record_id}')
def delete_application(record_id: str, user=Depends(current_user)):
    if not execute('DELETE FROM applications WHERE id=:id AND user_id=:u', {'id':record_id,'u':user['id']}):
        raise HTTPException(404, 'Application not found')
    return {'deleted': True}


@router.get('/tasks')
def tasks(user=Depends(current_user)):
    return rows('SELECT * FROM study_tasks WHERE user_id=:u ORDER BY done, CASE priority WHEN \'High\' THEN 0 WHEN \'Medium\' THEN 1 ELSE 2 END, due_date, created_at DESC', {'u':user['id']})


@router.post('/tasks')
def add_task(data: StudyTask, user=Depends(current_user)):
    if data.priority not in ['Low','Medium','High']: raise HTTPException(422,'Invalid priority')
    ensure_date(data.due_date)
    x=data.model_dump(); x.update(id=uid(),u=user['id'],done=1 if data.done else 0,time=db.now())
    execute('''INSERT INTO study_tasks (id,user_id,title,category,priority,due_date,done,source,created_at,updated_at)
     VALUES (:id,:u,:title,:category,:priority,:due_date,:done,:source,:time,:time)''',x)
    return {'id':x['id'],'saved':True}


@router.put('/tasks/{record_id}')
def edit_task(record_id: str, data: StudyTask, user=Depends(current_user)):
    if data.priority not in ['Low','Medium','High']: raise HTTPException(422,'Invalid priority')
    ensure_date(data.due_date)
    x=data.model_dump(); x.update(id=record_id,u=user['id'],done=1 if data.done else 0,time=db.now())
    if not execute('''UPDATE study_tasks SET title=:title,category=:category,priority=:priority,
       due_date=:due_date,done=:done,source=:source,updated_at=:time WHERE id=:id AND user_id=:u''',x):
        raise HTTPException(404,'Task not found')
    return {'updated':True}


@router.delete('/tasks/{record_id}')
def delete_task(record_id: str, user=Depends(current_user)):
    if not execute('DELETE FROM study_tasks WHERE id=:id AND user_id=:u', {'id':record_id,'u':user['id']}):
        raise HTTPException(404,'Task not found')
    return {'deleted':True}


def plan_from_skill_gap(skills, role='Your target role'):
    output=[]
    for skill in [str(s) for s in skills][:8]:
        output.extend([
            {'title':f'Learn the fundamentals of {skill}', 'category':skill, 'priority':'High', 'source':f'Skill gap: {role}'[:100]},
            {'title':f'Build a small, original {skill} example or project', 'category':skill, 'priority':'Medium', 'source':f'Skill gap: {role}'[:100]},
            {'title':f'Explain {skill} in a mock interview', 'category':skill, 'priority':'Medium', 'source':f'Skill gap: {role}'[:100]},
        ])
    return output


@router.get('/roadmap')
def roadmap(user=Depends(current_user)):
    # Suggest study tasks from the user's most recent evidence-backed job comparison.
    matches=rows('''SELECT role,record_type,result FROM career_records WHERE user_id=:u
                     ORDER BY created_at DESC LIMIT 40''', {'u':user['id']})
    for m in matches:
        result=json.loads(m['result'])
        match=result.get('target_match',result) if m['record_type']=='resume' else result
        gaps=match.get('missing_skills',[])
        if gaps:
            return {'role':m['role'],'missing_skills':gaps,'tasks':plan_from_skill_gap(gaps,m['role'])}
    return {'role':'','missing_skills':[],'tasks':[],'message':'Run a job match with a real job description to generate your personalized learning roadmap.'}


class TaskBatch(BaseModel):
    tasks: list[StudyTask] = Field(min_length=1,max_length=30)


@router.post('/tasks/batch')
def batch_tasks(data: TaskBatch,user=Depends(current_user)):
    existing = {r['title'].strip().casefold() for r in rows('SELECT title FROM study_tasks WHERE user_id=:u', {'u':user['id']})}
    added=0
    for t in data.tasks:
        if t.title.strip().casefold() not in existing:
            add_task(t, user)
            existing.add(t.title.strip().casefold()); added+=1
    return {'added':added,'skipped':len(data.tasks)-added}


@router.get('/cards')
def cards(user=Depends(current_user)):
    return rows('SELECT * FROM flashcards WHERE user_id=:u ORDER BY due_date,created_at DESC', {'u':user['id']})


@router.post('/cards')
def add_card(data: FlashCard,user=Depends(current_user)):
    x=data.model_dump(); x.update(id=uid(),u=user['id'],today=date.today().isoformat(),time=db.now())
    execute('''INSERT INTO flashcards (id,user_id,front,back,topic,due_date,created_at)
              VALUES (:id,:u,:front,:back,:topic,:today,:time)''',x)
    return {'id':x['id'],'saved':True}


@router.post('/cards/{card_id}/review')
def review_card(card_id: str, data: Review, user=Depends(current_user)):
    if data.result not in ('again','hard','good','easy'): raise HTTPException(422,'Choose again, hard, good or easy')
    card=item('SELECT * FROM flashcards WHERE id=:id AND user_id=:u', {'id':card_id,'u':user['id']})
    if not card: raise HTTPException(404,'Card not found')
    ease=float(card['ease']); reps=int(card['repetitions']); interval=int(card['interval_days'])
    if data.result=='again':
        reps=0; interval=0; ease=max(1.3,ease-.2)
    elif data.result=='hard':
        reps+=1; interval=max(1,round(interval*1.2)); ease=max(1.3,ease-.15)
    elif data.result=='good':
        reps+=1; interval=1 if reps==1 else 3 if reps==2 else max(1,round(interval*ease))
    else:
        reps+=1; interval=3 if reps==1 else max(4,round(max(interval,1)*ease*1.3)); ease=min(3.0,ease+.1)
    due=(date.today()+timedelta(days=interval)).isoformat()
    execute('''UPDATE flashcards SET ease=:e,repetitions=:r,interval_days=:n,due_date=:d
              WHERE id=:id AND user_id=:u''',{'e':ease,'r':reps,'n':interval,'d':due,'id':card_id,'u':user['id']})
    return {'next_review':due,'interval_days':interval,'repetitions':reps}


@router.delete('/cards/{card_id}')
def remove_card(card_id:str,user=Depends(current_user)):
    if not execute('DELETE FROM flashcards WHERE id=:id AND user_id=:u', {'id':card_id,'u':user['id']}):
        raise HTTPException(404,'Card not found')
    return {'deleted':True}


@router.get('/daily')
def daily_challenge(role: str='Software Engineer',user=Depends(current_user)):
    role=role[:160]
    today=date.today().isoformat()
    group=domain_for(role)
    choices=CATALOG.get(group) or CATALOG['software']
    seed=hashlib.sha256(f'{user["id"]}|{today}|{role.casefold()}'.encode()).digest()
    index=int.from_bytes(seed[:4],'big')%len(choices)
    entry=choices[index]
    difficulty=['Easy','Medium','Hard'][seed[4]%3]
    slot={'Easy':0,'Medium':1,'Hard':2}[difficulty]
    question=entry[slot]
    attempts=rows('SELECT * FROM daily_attempts WHERE user_id=:u AND date_key=:d AND role=:role ORDER BY created_at DESC',
                  {'u':user['id'],'d':today,'role':role})
    return {'date':today,'role':role,'difficulty':difficulty,'question':question,'ideal_points':entry[3],
            'attempts':[{'score':x['score'],'created_at':x['created_at'],'feedback':json.loads(x['feedback'])} for x in attempts]}


@router.post('/daily/answer')
def daily_answer(data:ChallengeAnswer,user=Depends(current_user)):
    challenge=daily_challenge(data.role,user)
    if data.date_key!=challenge['date'] or data.question!=challenge['question']:
        raise HTTPException(409,'Challenge changed. Refresh the page and try again.')
    feedback,mode=evaluate(challenge['question'],data.answer,challenge['ideal_points'])
    execute('''INSERT INTO daily_attempts(id,user_id,date_key,role,question,answer,score,feedback,created_at)
                VALUES (:id,:u,:d,:role,:q,:a,:score,:fb,:time)''',
            {'id':uid(),'u':user['id'],'d':data.date_key,'role':data.role,'q':data.question,
             'a':data.answer,'score':feedback['score'],'fb':json.dumps(feedback),'time':db.now()})
    return {'feedback':feedback,'mode':mode}


@router.get('/pulse')
def pulse(user=Depends(current_user)):
    u=user['id']; today=date.today()
    apps=rows('SELECT stage,due_date FROM applications WHERE user_id=:u', {'u':u})
    tasks=rows('SELECT done,due_date FROM study_tasks WHERE user_id=:u', {'u':u})
    cards=rows('SELECT due_date FROM flashcards WHERE user_id=:u', {'u':u})
    interviews=rows('SELECT created_at,completed,score FROM interviews WHERE user_id=:u', {'u':u})
    challenges=rows('SELECT date_key,score FROM daily_attempts WHERE user_id=:u', {'u':u})
    activity_dates={x['created_at'][:10] for x in interviews if x['completed']} | {x['date_key'] for x in challenges}
    current=today; streak=0
    if current.isoformat() not in activity_dates: current-=timedelta(days=1)
    while current.isoformat() in activity_dates:
        streak+=1; current-=timedelta(days=1)
    completed=sum(bool(x['done']) for x in tasks)
    achievements=[
        {'name':'First Steps','description':'Complete your first interview','unlocked':any(x['completed'] for x in interviews)},
        {'name':'Consistency','description':'Practice on 3 consecutive days','unlocked':streak>=3},
        {'name':'Career Explorer','description':'Track 3 applications','unlocked':len(apps)>=3},
        {'name':'Study Sprint','description':'Complete 5 learning tasks','unlocked':completed>=5},
        {'name':'Knowledge Keeper','description':'Create 10 flashcards','unlocked':len(cards)>=10},
        {'name':'Interview Regular','description':'Finish 10 interviews','unlocked':sum(bool(x['completed']) for x in interviews)>=10},
    ]
    return {'streak':streak,'applications':len(apps),'active_applications':sum(x['stage'] not in ['Rejected','Withdrawn','Accepted'] for x in apps),
      'application_stages':dict(Counter(x['stage'] for x in apps)),
      'tasks_total':len(tasks),'tasks_done':completed,
      'tasks_overdue':sum(bool(not x['done'] and x['due_date'] and x['due_date']<today.isoformat()) for x in tasks),
      'cards_due':sum(x['due_date']<=today.isoformat() for x in cards),'cards_total':len(cards),
      'challenges_done':len(challenges),'interviews_finished':sum(bool(x['completed']) for x in interviews),
      'achievements':achievements}


@router.put('/profile')
def update_profile(data:ProfileChange,user=Depends(current_user)):
    execute('UPDATE users SET name=:n WHERE id=:u', {'n':data.name.strip(),'u':user['id']})
    return {'id':user['id'],'name':data.name.strip(),'email':user['email']}


@router.post('/profile/password')
def update_password(data:PasswordChange,user=Depends(current_user)):
    record=item('SELECT password_hash FROM users WHERE id=:u',{'u':user['id']})
    if not record or not verify_password(data.old_password,record['password_hash']):
        raise HTTPException(401,'Current password is incorrect.')
    execute('UPDATE users SET password_hash=:p WHERE id=:u',{'p':hash_password(data.new_password),'u':user['id']})
    execute('DELETE FROM auth_tokens WHERE user_id=:u',{'u':user['id']})
    return {'updated':True,'login_required':True}


@router.get('/export')
def export_data(user=Depends(current_user)):
    u={'u':user['id']}
    return {'exported_at':db.now(),'account':user,
       'interviews':rows('SELECT id,role,kind,difficulty,questions,answers,created_at,completed,score,feedback FROM interviews WHERE user_id=:u',u),
       'career_records':rows('SELECT id,record_type,role,company,resume_text,job_description,result,created_at FROM career_records WHERE user_id=:u',u),
       'applications':applications(user),'study_tasks':tasks(user),'flashcards':cards(user),
       'daily_attempts':rows('SELECT date_key,role,question,answer,score,feedback,created_at FROM daily_attempts WHERE user_id=:u',u)}


@router.post('/profile/delete')
def delete_account(data:DeleteAccount,user=Depends(current_user)):
    if data.confirmation!='DELETE MY ACCOUNT': raise HTTPException(422,'Type DELETE MY ACCOUNT to confirm.')
    record=item('SELECT password_hash FROM users WHERE id=:u',{'u':user['id']})
    if not record or not verify_password(data.password,record['password_hash']):
        raise HTTPException(401,'Incorrect password.')
    with db.engine.begin() as c:
        for table in ('daily_attempts','flashcards','study_tasks','applications','career_records','interviews','auth_tokens'):
            c.execute(text(f'DELETE FROM {table} WHERE user_id=:u'),{'u':user['id']})
        c.execute(text('DELETE FROM users WHERE id=:u'),{'u':user['id']})
    return {'deleted':True}
