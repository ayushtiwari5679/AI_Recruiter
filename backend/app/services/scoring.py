import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TECH = {"python","java","javascript","typescript","react","node","fastapi","flask","django","sql","postgresql","mongodb","aws","azure","docker","kubernetes","machine learning","ai","llm","rag","langchain","git"}

def text_similarity(a: str, b: str) -> float:
    if not a.strip() or not b.strip(): return 0.0
    m = TfidfVectorizer(stop_words="english").fit_transform([a,b])
    return float(cosine_similarity(m[0:1], m[1:2])[0][0] * 100)

def explain_match(candidate_text: str, jd: str):
    c, j = candidate_text.lower(), jd.lower()
    required = sorted(t for t in TECH if t in j)
    matched = [t for t in required if t in c]
    missing = [t for t in required if t not in c]
    semantic = text_similarity(candidate_text, jd)
    skill = 100 * len(matched) / max(1, len(required))
    score = round(0.65*semantic + 0.35*skill, 2)
    return {"score": score, "semantic_score": round(semantic,2), "skill_score": round(skill,2), "matched_skills": matched, "missing_skills": missing}

def screening_score(resume_score, github_score, cgpa=0):
    education = min(100, max(0, float(cgpa or 0)*10))
    return round(0.65*resume_score + 0.25*github_score + 0.10*education, 2)

def final_score(screening, logical, coding):
    return round(0.60*screening + 0.15*logical + 0.25*coding, 2)
