import yaml
import os
from server.models.course import Course, CourseSection, Step

def load_course_content(course_id: str) -> Course:
    """Load course content from a YAML file"""
    course_path = f"courses/{course_id}.yaml"
    
    if not os.path.exists(course_path):
        raise FileNotFoundError(f"Course {course_id} not found")
        
    with open(course_path, 'r', encoding='utf-8') as file:
        course_data = yaml.safe_load(file)
        
    sections = []
    for idx, section_data in enumerate(course_data.get('course_sections', [])):
        first_step_content = section_data.get('steps', [{}])[0].get('content', '')
        
        steps = [
            Step(
                step=step['step'],
                content=step['content'].strip(),
                expected_responses=step.get('expected_responses', []),
                next_action=step.get('next_action', 'CONTINUE')
            )
            for step in section_data.get('steps', [])
        ]
        
        sections.append(
            CourseSection(
                title=section_data['sub_title'],
                content=first_step_content,
                order=idx + 1,
                steps=steps
            )
        )
    
    return Course(
        title=course_data['course_title'],
        description=course_data['course_description'],
        sections=sections
    ) 