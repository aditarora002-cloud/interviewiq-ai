"""Run: python -m unittest -v test_accounts_and_matching.py"""
import io
import tempfile
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from app import db, main


class AccountAndMatchingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_engine = db.engine
        db.engine = create_engine('sqlite:///' + str(Path(self.temp.name)/'test.db'))
        db.init()
        self.client = TestClient(main.app)
        self.a = self.client.post('/api/auth/register', json={
            'name': 'Alice', 'email': 'Alice@EXAMPLE.COM', 'password': 'alice-password-123'})
        self.b = self.client.post('/api/auth/register', json={
            'name': 'Bob', 'email': 'bob@example.com', 'password': 'bob-password-123'})
        assert self.a.status_code == self.b.status_code == 200, (self.a.text,self.b.text)
        self.ha = {'Authorization': 'Bearer ' + self.a.json()['token']}
        self.hb = {'Authorization': 'Bearer ' + self.b.json()['token']}

    def tearDown(self):
        db.engine.dispose()
        db.engine = self.old_engine
        self.temp.cleanup()

    def test_auth_and_logout(self):
        self.assertEqual(self.client.get('/api/interviews').status_code, 401)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.ha).json()['email'], 'alice@example.com')
        wrong = self.client.post('/api/auth/login', json={'email':'alice@example.com','password':'bad'})
        self.assertEqual(wrong.status_code, 401)
        correct = self.client.post('/api/auth/login', json={'email':'alice@example.com','password':'alice-password-123'})
        self.assertEqual(correct.status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout', headers=self.ha).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me', headers=self.ha).status_code, 401)
        self.assertEqual(self.client.get('/api/auth/me', headers={'Authorization':'Bearer '+correct.json()['token']}).status_code, 200)

    def test_resume_job_match_history_are_private(self):
        data = {
            'role': 'Frontend Developer', 'company': 'ExampleCorp',
            'resume_text': 'I built React websites with TypeScript, JavaScript, HTML and CSS. I improved accessibility.',
            'job_description': 'Frontend Developer role needs React, TypeScript, HTML, CSS, accessibility and testing.',
            'live_research': False,
        }
        matched = self.client.post('/api/match', json=data, headers=self.ha)
        self.assertEqual(matched.status_code, 200, matched.text)
        self.assertIn('compatibility_score', matched.json())
        self.assertIn('testing', matched.json()['missing_skills'])
        self.assertEqual(matched.json()['research']['status'], 'not_requested')
        self.assertEqual(self.client.get('/api/careers/history', headers=self.hb).json(), [])
        history = self.client.get('/api/careers/history', headers=self.ha).json()
        self.assertEqual(len(history), 1)
        record_id = history[0]['id']
        self.assertEqual(self.client.get('/api/careers/history/'+record_id, headers=self.hb).status_code, 404)
        self.assertEqual(self.client.get('/api/careers/history/'+record_id, headers=self.ha).status_code, 200)
        self.assertEqual(self.client.delete('/api/careers/history/'+record_id, headers=self.hb).status_code, 404)
        self.assertEqual(self.client.delete('/api/careers/history/'+record_id, headers=self.ha).status_code, 200)
        self.assertEqual(self.client.get('/api/careers/history', headers=self.ha).json(), [])

    def test_no_fabricated_company_research(self):
        no_evidence = self.client.post('/api/match', json={
            'role': 'Researcher', 'company': 'ExampleCorp', 'resume_text': 'Research methods experience and writing.'}, headers=self.ha)
        # Without credentials for a search provider or a job description no score can be justified.
        self.assertEqual(no_evidence.status_code, 422, no_evidence.text)
        research = self.client.post('/api/careers/research', json={
            'role':'Researcher', 'company':'ExampleCorp'}, headers=self.ha)
        self.assertEqual(research.status_code, 200)
        self.assertIn(research.json()['status'], {'not_configured','search_unavailable','no_sources','sources_found'})

    def test_resume_upload_and_account_separation(self):
        payload={'file':('resume.txt',io.BytesIO(b'My Projects: built React apps and tested accessibility. Skills: React, TypeScript, CSS. Education University. Email alice@example.com. Experience: Student projects.'),'text/plain')}
        result=self.client.post('/api/resume/analyze',headers=self.ha,files=payload,data={
            'role':'Frontend Developer','company':'ExampleCorp',
            'job_description':'React, TypeScript, accessibility and unit testing.'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn('target_match',result.json())
        self.assertEqual(len(self.client.get('/api/careers/history',headers=self.ha).json()),1)
        self.assertEqual(len(self.client.get('/api/careers/history',headers=self.hb).json()),0)

    def test_interviews_and_reports_private(self):
        data = {'role':'Data Scientist','difficulty':'Hard','question_count':3}
        r=self.client.post('/api/interviews/generate',json=data,headers=self.ha)
        self.assertEqual(r.status_code,200,r.text)
        sid=r.json()['session_id']
        self.assertEqual(self.client.get('/api/interviews/'+sid, headers=self.hb).status_code,404)
        self.assertEqual(self.client.get('/api/interviews/'+sid+'/report', headers=self.hb).status_code,404)
        self.assertEqual(len(self.client.get('/api/interviews',headers=self.hb).json()),0)
        self.assertEqual(len(self.client.get('/api/interviews',headers=self.ha).json()),1)

if __name__=='__main__':
    unittest.main()
