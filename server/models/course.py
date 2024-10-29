from pydantic import BaseModel
from typing import List, Optional

class Step(BaseModel):
    step: int
    content: str
    expected_responses: Optional[List[str]] = None
    next_action: str  # "CONTINUE", "NEXT", "REVIEW"

class CourseSection(BaseModel):
    title: str
    content: str
    order: int
    steps: List[Step]
    resources: Optional[List[str]] = []
    current_step: int = 0

class Course(BaseModel):
    title: str
    description: str
    sections: List[CourseSection]
    current_section: int = 0 