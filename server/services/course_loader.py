import yaml
import os
from server.models.course import Course, CourseSection

def load_course_content(course_id: str) -> Course:
    """Load course content from a YAML file"""
    course_path = f"courses/{course_id}.yaml"
    
    if not os.path.exists(course_path):
        raise FileNotFoundError(f"Course {course_id} not found")
        
    with open(course_path, 'r', encoding='utf-8') as file:
        course_data = yaml.safe_load(file)
        
    sections = [
        CourseSection(**section) 
        for section in course_data.get('sections', [])
    ]
    
    return Course(
        title=course_data['title'],
        description=course_data['description'],
        sections=sections
    ) 