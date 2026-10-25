"""Contract tests for InterviewIQ Studio. Run python -m unittest -v test_studio."""
import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app import db,main,studio

class StudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=db.engine
        db.engine=create_engine('sqlite:///'+str(Path(self.tmp.name)/'test.db'))
        db.init();studio.initialize()
        self.c=TestClient(main.app)
        self.a=self.c.post('/api/auth/register',json={'name':'Alice','email':'a@example.com','password':'StrongPassword123!'}).json()
        self.b=self.c.post('/api/auth/register',json={'name':'Bob','email':'b@example.com','password':'StrongPassword123!'}).json()
        self.h={'Authorization':f'Bearer {self.a["token"]}'}
        self.hb={'Authorization':f'Bearer {self.b["token"]}'}
    def tearDown(self):
        db.engine.dispose();db.engine=self.old;self.tmp.cleanup()
    def test_permissions_and_pipeline(self):
        self.assertEqual(self.c.get('/api/studio/applications').status_code,401)
        x=self.c.post('/api/studio/applications',headers=self.h,json={'company':'Acme','role':'Analyst','stage':'Applied'})
        self.assertEqual(x.status_code,200,x.text)
        rid=x.json()['id']
        self.assertEqual(len(self.c.get('/api/studio/applications',headers=self.hb).json()),0)
        self.assertEqual(self.c.put('/api/studio/applications/'+rid,headers=self.hb,json={'company':'Bad','role':'Test'}).status_code,404)
        self.assertEqual(self.c.delete('/api/studio/applications/'+rid,headers=self.hb).status_code,404)
        self.assertEqual(self.c.put('/api/studio/applications/'+rid,headers=self.h,json={'company':'Acme','role':'Analyst','stage':'Interview','next_action':'Practice'}).status_code,200)
        self.assertEqual(self.c.get('/api/studio/applications',headers=self.h).json()[0]['stage'],'Interview')
        self.assertEqual(self.c.delete('/api/studio/applications/'+rid,headers=self.h).status_code,200)
    def test_tasks_roadmap_and_pulse(self):
        r=self.c.post('/api/match',headers=self.h,json={'resume_text':'React and CSS project design','job_description':'React, CSS, TypeScript and accessibility and unit testing','role':'Frontend Developer','live_research':False})
        self.assertEqual(r.status_code,200,r.text)
        roadmap=self.c.get('/api/studio/roadmap',headers=self.h)
        self.assertGreater(len(roadmap.json()['tasks']),0)
        tasks=roadmap.json()['tasks'][:3]
        b=self.c.post('/api/studio/tasks/batch',headers=self.h,json={'tasks':tasks})
        self.assertEqual(b.status_code,200,b.text)
        b2=self.c.post('/api/studio/tasks/batch',headers=self.h,json={'tasks':tasks})
        self.assertEqual(b2.json()['added'],0)
        x=self.c.get('/api/studio/tasks',headers=self.h).json()[0]
        self.assertEqual(self.c.put('/api/studio/tasks/'+x['id'],headers=self.h,json={**x,'done':True}).status_code,200)
        self.assertEqual(self.c.get('/api/studio/pulse',headers=self.h).json()['tasks_done'],1)
        self.assertEqual(self.c.get('/api/studio/pulse',headers=self.hb).json()['tasks_total'],0)
    def test_flashcard_scheduling(self):
        r=self.c.post('/api/studio/cards',headers=self.h,json={'front':'What is a hash map?','back':'A key-value collection','topic':'DSA'})
        self.assertEqual(r.status_code,200,r.text)
        card=r.json()['id']
        self.assertEqual(self.c.post(f'/api/studio/cards/{card}/review',headers=self.hb,json={'result':'good'}).status_code,404)
        first=self.c.post(f'/api/studio/cards/{card}/review',headers=self.h,json={'result':'good'})
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['interval_days'],1)
        self.assertEqual(self.c.post(f'/api/studio/cards/{card}/review',headers=self.h,json={'result':'unknown'}).status_code,422)
        self.assertEqual(self.c.get('/api/studio/cards',headers=self.hb).json(),[])
    def test_daily_challenge_and_export(self):
        q=self.c.get('/api/studio/daily?role=Data%20Analyst',headers=self.h)
        self.assertEqual(q.status_code,200,q.text)
        payload={'date_key':q.json()['date'],'question':q.json()['question'],'role':'Data Analyst',
                 'answer':'I would investigate the requirements and data quality, validate assumptions and describe the results.'}
        r=self.c.post('/api/studio/daily/answer',headers=self.h,json=payload)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.c.post('/api/studio/daily/answer',headers=self.hb,json=payload).status_code,409)
        ex=self.c.get('/api/studio/export',headers=self.h).json()
        self.assertEqual(len(ex['daily_attempts']),1)
        self.assertNotIn('password_hash',json.dumps(ex))
    def test_profile_password_revoke_and_delete(self):
        p=self.c.put('/api/studio/profile',headers=self.h,json={'name':'Alice Revised'})
        self.assertEqual(p.status_code,200,p.text)
        self.assertEqual(self.c.get('/api/auth/me',headers=self.h).json()['name'],'Alice Revised')
        r=self.c.post('/api/studio/profile/password',headers=self.h,json={'old_password':'StrongPassword123!','new_password':'AnotherStrong1234'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.c.get('/api/auth/me',headers=self.h).status_code,401)
        logged=self.c.post('/api/auth/login',json={'email':'a@example.com','password':'AnotherStrong1234'})
        self.assertEqual(logged.status_code,200)
        h={'Authorization':f'Bearer {logged.json()["token"]}'}
        self.assertEqual(self.c.post('/api/studio/profile/delete',headers=h,json={'password':'AnotherStrong1234','confirmation':'WRONG'}).status_code,422)
        self.assertEqual(self.c.post('/api/studio/profile/delete',headers=h,json={'password':'AnotherStrong1234','confirmation':'DELETE MY ACCOUNT'}).status_code,200)
        self.assertEqual(self.c.get('/api/auth/me',headers=h).status_code,401)
        self.assertEqual(self.c.get('/api/auth/me',headers=self.hb).status_code,200)

if __name__=='__main__':unittest.main()
