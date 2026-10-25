"""Run from backend folder: python -m unittest -v test_interview_generation.py"""
import os
import tempfile
import unittest
from pathlib import Path

from app import engine, db, main
from app.question_bank import domain_for
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

class TestInterviewGenerator(unittest.TestCase):
    def setUp(self):
        self.old_llm = engine.llm
        engine.llm = lambda *a, **k: None

    def tearDown(self):
        engine.llm = self.old_llm

    def test_every_listed_role_has_domain_questions(self):
        roles = ["Software Engineer", "Frontend Developer", "Backend Developer", "Full-Stack Developer",
                 "Cybersecurity Analyst", "Cloud Engineer", "Data Analyst", "Data Scientist", "AI Engineer",
                 "Machine Learning Engineer", "Product Manager", "Business Analyst", "Financial Analyst",
                 "Accountant", "Marketing Specialist", "Sales Executive", "Human Resources", "Teacher / Educator",
                 "Healthcare Professional", "Legal Associate", "Operations Manager", "UX/UI Designer",
                 "Graphic Designer", "Researcher", "Government / Public Service"]
        for role in roles:
            with self.subTest(role=role):
                self.assertIsNotNone(domain_for(role))
                for difficulty in ("Easy", "Medium", "Hard"):
                    q, mode = engine.questions(role, "Entry level", "Technical", difficulty, 12)
                    self.assertEqual(mode, "demo")
                    self.assertEqual(len(q), 12)
                    self.assertEqual(len({item["question"] for item in q}), 12)
                    self.assertTrue(all(item["ideal_points"] for item in q))

    def test_difficulty_really_changes_question(self):
        for role in ("Frontend Developer", "Financial Analyst", "Legal Associate", "Human Resources"):
            easy = {q['question'] for q in engine.questions(role, 'Student', 'Technical', 'Easy', 8)[0]}
            medium = {q['question'] for q in engine.questions(role, 'Student', 'Technical', 'Medium', 8)[0]}
            hard = {q['question'] for q in engine.questions(role, 'Student', 'Technical', 'Hard', 8)[0]}
            self.assertFalse(easy & medium)
            self.assertFalse(medium & hard)

    def test_no_exact_repeats_in_next_session(self):
        used = []
        for _ in range(8):
            q, mode = engine.questions('AI Engineer', 'Entry level', 'Technical', 'Hard', 12, seen=used)
            seen = [x['question'] for x in q]
            self.assertTrue(set(seen).isdisjoint(used))
            used.extend(seen)

    def test_rounds_are_different(self):
        tech = engine.questions('Accountant', 'Student', 'Technical', 'Easy', 5)[0]
        beh = engine.questions('Accountant', 'Student', 'Behavioral', 'Easy', 5)[0]
        self.assertTrue(all(q['category'] == 'Domain knowledge' for q in tech))
        self.assertTrue(all(q['category'] == 'Behavioral' for q in beh))

    def test_custom_role_does_not_use_generic_ml_questions(self):
        q, _ = engine.questions('Museum Curator', 'Entry level', 'Technical', 'Medium', 5)
        self.assertTrue(any('Museum Curator' in item['question'] for item in q))
        self.assertFalse(any('bias-variance' in item['question'] for item in q))

    def test_api_respects_settings_and_persists_history(self):
        with tempfile.TemporaryDirectory() as td:
            previous_db = db.engine
            db.engine = create_engine('sqlite:///' + str(Path(td) / 'test.db'))
            try:
                db.init()
                client = TestClient(main.app)
                auth=client.post('/api/auth/register',json={'name':'Tester','email':'tester@example.com','password':'strong-pass-123'})
                self.assertEqual(auth.status_code,200,auth.text)
                headers={'Authorization':'Bearer '+auth.json()['token']}
                body = {"role":"UX/UI Designer","experience":"Student","interview_type":"Technical","difficulty":"Hard","question_count":3}
                r = client.post('/api/interviews/generate', json=body,headers=headers)
                self.assertEqual(r.status_code, 200, r.text)
                data = r.json()
                self.assertEqual(len(data['questions']), 3)
                self.assertEqual(data['difficulty'], 'Hard')
                self.assertEqual(db.get(data['session_id'],auth.json()['user']['id'])['difficulty'], 'Hard')
                reply = client.post(f"/api/interviews/{data['session_id']}/answer", json={
                    "question_index": 0, "answer": "I would clarify the goal, test a prototype with users, and measure results."},headers=headers)
                self.assertEqual(reply.status_code, 200, reply.text)
                self.assertIn('score', reply.json()['feedback'])
                finished = client.post(f"/api/interviews/{data['session_id']}/finish",headers=headers)
                self.assertEqual(finished.status_code, 200, finished.text)
                self.assertEqual(finished.json()['answered'], 1)
                r2 = client.post('/api/interviews/generate', json=body,headers=headers)
                self.assertEqual(r2.status_code, 200, r2.text)
                old = {q['question'] for q in data['questions']}
                new = {q['question'] for q in r2.json()['questions']}
                self.assertTrue(old.isdisjoint(new))
            finally:
                db.engine.dispose()
                db.engine = previous_db

if __name__ == '__main__':
    unittest.main()
