import os, re, json, math
from collections import Counter

SKILLS=[
 "python","sql","machine learning","deep learning","data analysis","data visualization","pandas","numpy","scikit-learn","tensorflow","pytorch","nlp","natural language processing","statistics","probability","power bi","tableau","excel","aws","azure","docker","fastapi","flask","react","typescript","javascript","postgresql","mongodb","git","feature engineering","model evaluation","computer vision","llm","generative ai","prompt engineering","matplotlib","seaborn","spark","hadoop","airflow","etl","api","linear regression","classification","clustering",
 "java","c++","c#","html","css","node.js","next.js","rest api","graphql","testing","unit testing","integration testing","ci/cd","kubernetes","linux","system design","data structures","algorithms","security","networking","cloud computing","microservices","accessibility","responsive design","figma","ui/ux","user research","wireframing","prototyping",
 "accounting","financial modeling","financial analysis","valuation","budgeting","forecasting","cash flow","balance sheet","financial statements","gaap","ifrs","auditing","risk management","financial reporting","powerpoint","stakeholder management","project management","agile","scrum","product strategy","product analytics","market research","competitive analysis","business intelligence","kpi","requirements gathering","process improvement","operations","procurement","logistics","supply chain",
 "seo","content marketing","digital marketing","google analytics","social media","brand strategy","copywriting","campaign management","lead generation","crm","salesforce","customer service","negotiation","recruitment","talent acquisition","onboarding","employee relations","training","performance management","instructional design","curriculum design","lesson planning","classroom management","patient care","clinical documentation","healthcare compliance","case management","contract law","legal research","legal writing","compliance","public policy","research methods","qualitative research","quantitative research"
]

def skills(text):
    """Prefer token boundaries over substring matching ('api' should not match 'capital')."""
    t=(text or "").casefold()
    return sorted({skill for skill in SKILLS if re.search(r'(?<![\w])'+re.escape(skill)+r'(?![\w])', t)})

def analyze(text):
    t=(text or "").lower()
    sections={"contact":bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+",text or "")),
      "skills":any(x in t for x in ["skills","technical skills","technologies"]),
      "education":any(x in t for x in ["education","university","bachelor"]),
      "projects":"project" in t,"experience":any(x in t for x in ["experience","internship","employment"])}
    found=skills(text)
    score=min(100,sum(sections.values())*14+min(len(found),8)*3+(10 if len(text)>1200 else 0))
    tips=[]
    for k,msg in [("contact","Add a professional email address."),("skills","Add a clearly labeled Skills section."),("education","Include your degree and institution."),("projects","Add projects with tools used and measurable outcomes."),("experience","Include relevant internships, research, or practical experience.")]:
        if not sections[k]: tips.append(msg)
    if len(text)<800: tips.append("Add more detail about projects, decisions, and outcomes.")
    return {"quality_score":score,"skills":found,"sections":sections,"suggestions":tips,"word_count":len(text.split()),
            "note":"Heuristic checklist score, not an employer ATS score."}

def match(resume, job, role='', company='', researched=False):
    """Explainable keyword/evidence alignment, never a hiring probability."""
    rs, js = set(skills(resume)), set(skills(job))
    overlap = len(rs & js) / max(1, len(js))
    # Dependency-light TF-IDF cosine similarity keeps the API small enough for
    # serverless deployment, without pretending this is an employer ATS model.
    def terms(value):
        words = re.findall(r"[a-z][a-z0-9+#.]{1,}", (value or '').casefold())
        stop = {'the','and','for','with','from','that','this','you','your','are','was','have',
                'has','our','their','into','about','will','can','its','a','an','of','in','to','on','or','is','as','by','at'}
        words = [w for w in words if w not in stop]
        return words + [f'{x} {y}' for x,y in zip(words,words[1:])]
    a,b = Counter(terms(resume)), Counter(terms(job))
    common=set(a)&set(b)
    # Two-document smoothed IDF. Frequencies are sublinear so long resumes
    # don't dominate. Same formula for both vectors.
    def weight(t,c):
        df=int(t in a)+int(t in b)
        return (1+math.log(c[t]))*(math.log(3/(1+df))+1) if t in c else 0
    dot=sum(weight(t,a)*weight(t,b) for t in common)
    denom=math.sqrt(sum(weight(t,a)**2 for t in a)*sum(weight(t,b)**2 for t in b))
    sim=dot/denom if denom else 0.0
    # A skill mentioned without proof gets less weight than evidence tied to a project or experience.
    evidence = []
    lower = resume.casefold()
    for skill in sorted(rs & js):
        occurrences = [m.start() for m in re.finditer(r'(?<![\w])'+re.escape(skill)+r'(?![\w])', lower)]
        context = [lower[max(0,pos-100):pos+110] for pos in occurrences]
        strong = any(re.search(r'\b(built|developed|implemented|deployed|improved|designed|led|managed|automated|created|delivered|analyzed|measured|optimized|tested)\b', window) for window in context)
        evidence.append({'skill': skill, 'evidence': 'contextual example found' if strong else 'mentioned only'})
    evidence_rate = sum(x['evidence'] == 'contextual example found' for x in evidence)/max(1, len(js))
    raw = round(100*(.55*overlap + .25*sim + .20*evidence_rate))
    return {
        'compatibility_score': max(0, min(raw, 100)),
        'assessment_status': 'research-assisted estimate' if researched else 'provisional text estimate',
        'role': role, 'company': company,
        'matched_skills': sorted(rs & js), 'missing_skills': sorted(js-rs),
        'resume_skills': sorted(rs), 'job_skills': sorted(js),
        'skill_evidence': evidence, 'skill_overlap': round(overlap, 3), 'tfidf_similarity': round(sim, 3),
        'formula': '55% listed requirements overlap + 25% text similarity + 20% evidence-context heuristic',
        'recommendations': [f'Add truthful project or work evidence for {s}, if you have it.' for s in sorted(js-rs)[:5]] +
             ['Quantify your relevant experience using outcomes you can verify.'],
        'note': 'An explainable resume-to-text alignment estimate, not a hiring probability, verified ATS result, or assessment of personal worth.'
    }

BANK=[
("Walk me through a project you are proud of and the decisions you made.","Behavioral",["Set the context and goal","Explain your own contribution","Describe a measurable result and learning"]),
("Tell me about a time you received difficult feedback. What did you change?","Behavioral",["Describe the situation calmly","Explain the feedback and action","Share the outcome and lesson"]),
("Describe a time you disagreed with a teammate. How did you resolve it?","Behavioral",["Explain both perspectives fairly","Use evidence and communication","Describe the resolution"]),
("How do you prioritize when several urgent tasks compete?","Situational",["Assess impact and deadlines","Communicate trade-offs","Revisit priorities as facts change"]),
("Tell me about a mistake you made and how you handled it.","Behavioral",["Take ownership","Explain corrective action","Share prevention and learning"]),
("How would you explain a complex idea to a non-specialist?","Communication",["Adapt to audience","Use an example or analogy","Check understanding"]),
("How would you investigate a problem when the requirements are unclear?","Situational",["Clarify goals and constraints","Identify assumptions","Propose a testable next step"]),
("What would you do if you noticed an ethical or privacy risk in your work?","Situational",["Protect affected people and data","Escalate through appropriate channels","Document and reduce risk"]),
("How do you decide whether evidence is strong enough to support a recommendation?","Analytical",["Assess evidence quality and bias","Consider alternatives and uncertainty","Explain limitations"]),
("Describe a time you had to learn a new tool or subject quickly.","Behavioral",["Break learning into steps","Use reliable resources and practice","Apply and verify the learning"]),
("What would your first 30 days in this role look like?","Role fit",["Learn goals and processes","Build relationships","Agree on measurable priorities"]),
("How would you respond if a stakeholder requested something that conflicts with the project goal?","Situational",["Understand the underlying need","Explain trade-offs with evidence","Agree on an aligned option"]),
("How would you handle missing values in a dataset?","Technical",["Understand why values are missing","Assess amount and pattern","Choose deletion or imputation based on context","Avoid data leakage"]),
("Explain the bias-variance trade-off and how you would spot it.","Technical",["Define bias and variance","Compare training and validation results","Discuss complexity and regularization"]),
("How would you evaluate an imbalanced classification model?","Technical",["Do not rely on accuracy alone","Use precision, recall, F1 and PR-AUC","Choose metrics based on error costs"]),
("What is data leakage, and how would you prevent it in a pipeline?","Technical",["Define leakage","Split before fitting transformations","Use pipelines and time-aware splits when needed"]),
("How would you debug a slow API endpoint in production?","Technical",["Measure before changing code","Inspect traces, database and network","Test and monitor the fix"]),
("Explain how you would design a reliable REST API for a new feature.","Technical",["Define resources and contracts","Validate inputs and errors","Consider auth, versioning and tests"]),
("How would you test a software feature before release?","Technical",["Unit and integration tests","Cover edge cases and regressions","Use staging and monitoring"]),
("How would you investigate a sudden drop in a product metric?","Analytics",["Verify instrumentation and segment data","Compare cohorts and time periods","Test likely causes"]),
("How would you prioritize a product roadmap with limited engineering capacity?","Product",["Estimate user impact and effort","Use evidence and strategic fit","Make trade-offs transparent"]),
("How would you respond to an unhappy customer whose issue has no immediate fix?","Customer service",["Listen and acknowledge impact","Explain honestly without overpromising","Offer next steps and follow up"]),
("How would you plan a campaign when the target audience is not responding?","Marketing",["Check audience and funnel data","Form a testable hypothesis","Run controlled experiments and measure outcomes"]),
("How would you handle confidential information in a professional setting?","Professional judgment",["Follow policy and applicable law","Limit access and sharing","Escalate uncertainty appropriately"]),
("How would you explain a complex legal or policy issue to a client in plain language?","Communication",["Clarify the question and context","Explain options and uncertainty","Avoid overclaiming and document advice"]),
("How would you prioritize patient or client needs when several require attention?","Situational",["Use urgency and risk criteria","Follow professional protocols","Communicate and document decisions"]),
("How would you design a lesson for learners with different starting levels?","Education",["Assess prior knowledge","Provide multiple paths and checks","Use feedback to adapt"]),
("How would you evaluate whether a business proposal is financially viable?","Finance",["State assumptions","Estimate costs, cash flows and risks","Test sensitivity and alternatives"]),
("How would you respond to a project that is behind schedule and over budget?","Management",["Establish facts and root causes","Re-plan scope and resources","Communicate risks and milestones"]),
("How would you evaluate a design concept against user needs and constraints?","Creative",["Define user and success criteria","Compare alternatives and test prototypes","Use feedback to iterate"]),
]

def llm(prompt, system="You are a careful interview coach."):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key: return None
    try:
        from openai import OpenAI
        c=OpenAI(api_key=key)
        r=c.chat.completions.create(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),
          messages=[{"role":"system","content":system},{"role":"user","content":prompt}],temperature=.35)
        return r.choices[0].message.content
    except Exception: return None

def _normalize_question(value):
    return re.sub(r"\W+", " ", (value or "").casefold()).strip()


def _is_repeat(question, prior):
    """Exact and near-text duplicate filter; semantic duplicates may still occur."""
    from difflib import SequenceMatcher
    norm = _normalize_question(question)
    if not norm:
        return True
    for previous in prior:
        if norm == previous or (len(norm) > 35 and len(previous) > 35 and
                SequenceMatcher(None, norm, previous).ratio() >= 0.88):
            return True
    return False


def _candidate(question, category, points):
    return {"question": question, "category": category,
            "ideal_points": list(points)[:5]}


def _offline_questions(role, experience, kind, difficulty, count, seen, job):
    """Select field-specific and level-specific prompts without random unrelated questions."""
    from .question_bank import CATALOG, BEHAVIORAL, SITUATIONAL, domain_for
    import secrets

    domain = domain_for(role)
    # For unfamiliar custom roles, use role-linked case questions rather than
    # pretending the software-engineering or data-science bank matches the role.
    if domain is None:
        domain_items = [
            (f"What are the core responsibilities of a {role}, and how do they support the organisation?",
             f"How would you handle a typical challenge faced by a {role}? Walk through your approach.",
             f"Describe a high-stakes decision a {role} might face, and explain how you would assess risks and trade-offs.",
             ["Role understanding", "Structured reasoning", "Relevant example"]),
            (f"What skills are important for someone working as a {role}?",
             f"How would you demonstrate your ability to perform as a {role} on a new team?",
             f"How would you evaluate success and manage competing priorities in the {role} role?",
             ["Job-related competencies", "Evidence", "Measurement"]),
            (f"What tools or methods are commonly used in the {role} field?",
             f"Which method would you choose for a realistic {role} task, and why?",
             f"Compare alternative approaches to a complex {role} task, including limitations.",
             ["Methods", "Choice rationale", "Practical limits"]),
        ]
    else:
        domain_items = CATALOG[domain]

    diff_index = {"easy": 0, "medium": 1, "hard": 2}.get(difficulty.casefold(), 1)
    k = kind.casefold().strip()
    technical = k in ("technical", "domain knowledge")
    behavioral = k in ("behavioral", "hr")
    situational = k in ("situational",)
    case = k in ("case study", "case")
    portfolio = k in ("portfolio",)

    domain_prompts = [_candidate(item[diff_index], "Domain knowledge" if not case else "Case study", item[3])
                      for item in domain_items]
    # Prioritize concepts that appear in a supplied job description when the
    # question explicitly shares terminology; do not invent company specifics.
    if job and not (behavioral or situational):
        words = set(re.findall(r"[a-zA-Z]{4,}", job.lower()))
        domain_prompts.sort(key=lambda item: -len(words & set(re.findall(r"[a-zA-Z]{4,}", item["question"].lower()))))

    behavioral_prompts = [_candidate(q, "Behavioral", pts) for q, pts in BEHAVIORAL]
    if experience.casefold() in ("student", "entry level"):
        behavioral_prompts = [
            _candidate(p["question"] + " You may use a class, volunteer, or personal project example.", p["category"], p["ideal_points"])
            for p in behavioral_prompts
        ]
    situational_prompts = [_candidate(q, "Situational", pts) for q, pts in SITUATIONAL]

    # Preserve the intent of the selected interview round.
    if technical:
        base = domain_prompts
    elif behavioral:
        base = behavioral_prompts
    elif situational:
        base = situational_prompts + domain_prompts
    elif case:
        # Harder prompts already involve design, decision-making, and trade-offs.
        base = domain_prompts + situational_prompts
    elif portfolio:
        base = [_candidate(f"Describe a project relevant to a {role} role. What problem did you solve and how did you validate the outcome?", "Portfolio", ["Goal", "Individual contribution", "Evidence"]),
                _candidate(f"Walk through a major technical or professional decision in your {role} portfolio.", "Portfolio", ["Decision", "Alternatives", "Result"]),
                _candidate(f"What would you improve if you revisited a {role} project you completed?", "Portfolio", ["Reflection", "Trade-offs", "Iteration"])] + domain_prompts
    else:
        # Mixed: alternate domain and behavioral/situational prompts so no role
        # gets a full interview of generic soft-skills questions.
        common = behavioral_prompts + situational_prompts
        base = []
        for i in range(max(len(domain_prompts), len(common))):
            if i < len(domain_prompts):
                base.append(domain_prompts[i])
            if i < len(common) and (i % 2 == 0 or i >= len(domain_prompts)):
                base.append(common[i])
        base += common

    past = {_normalize_question(q) for q in (seen or []) if q}
    picked = []
    local = set()
    # Rotate starting topic to vary question coverage between sessions while
    # maintaining the relevance ranking in job-description mode.
    if len(base) > 1 and not job:
        offset = secrets.randbelow(len(base))
        base = base[offset:] + base[:offset]

    def attempt(q):
        n = _normalize_question(q["question"])
        if _is_repeat(q["question"], past | local):
            return False
        picked.append(q)
        local.add(n)
        return True

    # Use the base question first, then progressively vary the *actual scenario*
    # (rather than appending meaningless random nonce/variation labels).
    for item in base:
        attempt(item)
        if len(picked) >= count:
            return picked, "demo"

    scenarios = [
        "a team launching a new service with limited resources",
        "a small organisation with incomplete documentation",
        "a distributed team supporting users across regions",
        "a rapidly growing organisation dealing with unexpected demand",
        "a team modernising a legacy workflow",
        "an organisation with strict accessibility and privacy expectations",
        "a public-facing project with multiple stakeholders",
        "a cross-functional team preparing for an important release",
        "a new initiative with limited historical data",
        "a team responding to repeated service complaints",
        "an organisation balancing cost with service quality",
        "a project where requirements change shortly before launch",
        "a high-volume operation where quality needs improvement",
        "a team adopting a new process without disrupting existing work",
        "a project involving collaborators with conflicting priorities",
        "an organisation testing a new approach before scaling it",
    ]
    # No exact text repeats from earlier sessions. Each variant introduces a
    # different credible scenario, rather than pretending to be unique simply
    # because a random identifier was appended.
    for scenario in scenarios:
        for item in base:
            q = _candidate(f"Context: {scenario}. {item['question']}",
                           item["category"], item["ideal_points"])
            attempt(q)
            if len(picked) >= count:
                return picked, "demo"

    # If past history exhausts the finite offline catalog, maintain distinct
    # text using more specific scenario combinations, but be transparent that
    # no finite fallback can guarantee new concepts indefinitely.
    counter = 1
    while len(picked) < count:
        item = base[(counter - 1) % len(base)]
        context = scenarios[(counter - 1) % len(scenarios)]
        question = f"In a {role} role, scenario {counter}: consider {context}. {item['question']}"
        attempt(_candidate(question, item["category"], item["ideal_points"]))
        counter += 1
    return picked, "demo"


def questions(role, experience, kind, difficulty, count, resume="", job="", seen=None, company=""):
    """Generate interview questions with sensible fallbacks and history filtering."""
    seen = seen or []
    prior = {_normalize_question(q) for q in seen if q}
    requested = max(1, min(12, int(count)))
    role = (role or "General professional role").strip() or "General professional role"
    experience = experience or "Entry level"
    kind = kind or "Mixed"
    difficulty = difficulty if difficulty in ("Easy", "Medium", "Hard") else "Medium"
    import secrets
    nonce = secrets.token_hex(4)
    # Use LLM only when user provided a key; never claim non-LLM feedback is AI.
    prompt = f"""Generate exactly {requested} interview questions as a JSON ARRAY.
Role: {role}; company (do not assume facts): {company or 'unspecified'}.
Candidate level: {experience}. Interview round: {kind}. Difficulty: {difficulty}.
Difficulty guidance: Easy = fundamentals and straightforward examples;
Medium = practical applied reasoning and trade-offs;
Hard = ambiguous, multistep real-world scenarios, edge cases and justification.
Only ask questions relevant to the stated role and round; avoid generic ML/engineering
questions for non-technical professions. A student may draw on coursework or projects.
For each item include: question (string), category (string), ideal_points (array of
3-5 specific, verifiable evaluation criteria). Use accurate terminology.
Job description/topics: {job[:2500]}. Candidate background: {resume[:1500]}.
Do not reuse or closely paraphrase: {json.dumps(seen[-100:], ensure_ascii=False)[:8500]}.
Avoid repeating concepts within this session. Randomisation key: {nonce}.
Return only valid JSON."""
    out = llm(prompt, "You are an experienced, fair interviewer. Use accurate domain knowledge. Return ONLY a JSON array of objects.")
    selected = []
    selected_norm = set(prior)
    if out:
        try:
            data = json.loads(out[out.find("["):out.rfind("]") + 1])
            if not isinstance(data, list):
                data = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                q = str(item.get("question", "")).strip()
                pts = item.get("ideal_points", [])
                if not isinstance(pts, list):
                    continue
                points = [str(p).strip() for p in pts if str(p).strip()][:5]
                if len(q) < 20 or len(points) < 2 or _is_repeat(q, selected_norm):
                    continue
                selected.append(_candidate(q, str(item.get("category", kind)), points))
                selected_norm.add(_normalize_question(q))
                if len(selected) >= requested:
                    break
        except (ValueError, TypeError):
            pass

    llm_question_count = len(selected)
    if len(selected) < requested:
        filler, _ = _offline_questions(role, experience, kind, difficulty,
                                      requested - len(selected),
                                      seen + [q["question"] for q in selected], job)
        selected += filler
    return selected[:requested], ("live" if llm_question_count == requested else "demo")


def evaluate(question, answer, ideal):
    prompt=f"""Evaluate this practice answer. Return JSON with score 0-100, rubric object with correctness/relevance/depth/clarity (0-100), strengths array, improvements array, sample_answer string. Be constructive. Question: {question}; expected points: {ideal}; answer: {answer}"""
    out=llm(prompt,"You are a fair interview coach. Evaluate only answer content. Return valid JSON.")
    if out:
        try:
            d=json.loads(out[out.find("{"):out.rfind("}")+1]); d["score"]=max(0,min(100,float(d.get("score",0)))); return d,"live"
        except Exception: pass
    words=re.findall(r"\b[\w+#.-]+\b",answer.lower())
    grammar_patterns=[(r"\bi am agree\b","Use “I agree” instead of “I am agree.”"),(r"\bhe don't\b|\bshe don't\b","Use “doesn't” with he/she."),(r"\bi didn't went\b","Use the base verb after “didn't” (for example, “didn't go”)."),(r"\bmore better\b","Avoid the double comparative; use “better.”"),(r"\bdiscuss about\b","Use “discuss the topic,” without “about.”"),(r"\bi has\b","Use “I have,” not “I has.”"),(r"\bthey was\b","Use “they were,” not “they was.”")]
    grammar_tips=[tip for pattern,tip in grammar_patterns if re.search(pattern,answer,re.I)]
    covered=sum(any(tok in answer.lower() for tok in re.findall(r"[a-zA-Z]{4,}",p.lower())[:3]) for p in ideal)
    score=round(min(100,min(35,len(words)*1.2)+(55*covered/max(1,len(ideal)))+(10 if len(words)>=35 else 4 if len(words)>=12 else 0)))
    tips=[]
    if len(words)<25: tips.append("Add detail and explain your reasoning step by step.")
    for p in ideal:
        toks=re.findall(r"[a-zA-Z]{4,}",p.lower())[:3]
        if not any(t in answer.lower() for t in toks): tips.append("Consider covering: "+p+".")
    return {"score":score,"rubric":{"correctness":score,"relevance":score,"depth":min(100,len(words)*2),"clarity":65},
      "strengths":["You submitted an answer; use the feedback to refine it."],"improvements":(tips+grammar_tips)[:8] or ["Add a concrete example or discuss trade-offs."],
      "grammar_suggestions":grammar_tips,
      "sample_answer":"Address the question directly, explain your reasoning, and include a relevant example." ,
      "note":"Rule-based demo feedback; configure an LLM API for richer evaluation."},"demo"
