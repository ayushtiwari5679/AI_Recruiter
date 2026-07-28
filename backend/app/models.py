from sqlalchemy import Column, Integer, String, Float, Text
from .database import Base

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    college = Column(String, default="")
    branch = Column(String, default="")
    cgpa = Column(Float, default=0)
    best_ai_project = Column(Text, default="")
    research_work = Column(Text, default="")
    github_profile = Column(String, default="")
    resume_link = Column(String, default="")
    resume_text = Column(Text, default="")
    resume_score = Column(Float, default=0)
    github_score = Column(Float, default=0)
    screening_score = Column(Float, default=0)
    logical_score = Column(Float, default=0)
    coding_score = Column(Float, default=0)
    final_score = Column(Float, default=0)
    status = Column(String, default="uploaded")
