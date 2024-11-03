import os
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
COMPLETIONS_URL = f"{API_BASE_URL}/llm/completions"
START_COURSE_URL = f"{API_BASE_URL}/llm/start-course"

def start_course(course_id: str, user_id: str = "default_user"):
    try:
        response = requests.post(
            f"{START_COURSE_URL}/{course_id}",
            params={"user_id": user_id}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error starting course: {str(e)}")
        return None

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "course_started" not in st.session_state:
    st.session_state.course_started = False
    
if "current_section" not in st.session_state:
    st.session_state.current_section = 0

# Page layout
st.set_page_config(layout="wide")

# Main UI
col1, col2 = st.columns([3, 1])

with col1:
    st.title("Interactive Course Assistant")

    # Course selection and start
    if not st.session_state.course_started:
        try:
            # Get available courses
            response = requests.get(f"{API_BASE_URL}/llm/available-courses")
            courses = response.json()
            
            # Create course selection options
            course_options = {
                course["title"]: course["id"] 
                for course in courses
            }
            
            selected_title = st.selectbox(
                "Select a course:",
                options=list(course_options.keys())
            )
            
            # Get selected course ID
            selected_course_id = course_options[selected_title]
            
            if st.button("Start Course"):
                result = start_course(selected_course_id)
                if result:
                    welcome_message = result["message"]
                    st.session_state.messages.append(welcome_message)
                    st.session_state.course_started = True
                    # Store selected course ID in session state
                    st.session_state.current_course_id = selected_course_id
                    st.rerun()
                
        except Exception as e:
            st.error(f"Error loading courses: {str(e)}")

    # Chat interface
    if st.session_state.course_started:
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Add user message to chat
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Get AI response
            try:
                response = requests.post(
                    COMPLETIONS_URL,
                    json={"input": prompt},
                    params={"user_id": "default_user"}
                )
                response.raise_for_status()
                
                ai_message = {
                    "role": "assistant",
                    "content": response.json()["output"]
                }
                st.session_state.messages.append(ai_message)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {str(e)}")

# Sidebar with course progress
with col2:
    if st.session_state.course_started:
        st.sidebar.title("Course Progress")
        
        try:
            # Get current course state
            response_state = requests.get(f"{API_BASE_URL}/llm/course-state/default_user")
            course_state = response_state.json()
            current_section = course_state.get("current_section", 0)
            current_step = course_state.get("current_step", -1)
            
            # Get course content for the selected course
            current_course_id = st.session_state.get("current_course_id")
            if current_course_id:
                response = requests.get(f"{API_BASE_URL}/llm/course-content/{current_course_id}")
                course_data = response.json()
                
                # Kurs tamamlanma kontrolü
                is_completed = False
                if current_step >= 0:
                    current_section_data = course_data["sections"][current_section]
                    if current_step < len(current_section_data["steps"]):
                        current_step_obj = current_section_data["steps"][current_step]
                        is_completed = (
                            current_step_obj.get("next_action") == "FINISH" and
                            "Tebrikler! 🎉 Kursu başarıyla tamamladın" in st.session_state.messages[-1].get("content", "")
                        )
                
                # Kurs tamamlandıysa
                if is_completed or course_state.get("completed", False):
                    st.sidebar.success("🎉 Kurs Tamamlandı!")
                    st.sidebar.balloons()  # Kutlama efekti
                    if st.sidebar.button("Yeni Kursa Başla"):
                        st.session_state.course_started = False
                        st.rerun()
                
                # Kurs devam ediyorsa
                else:
                    if current_step >= 0:
                        # Progress bars
                        total_sections = len(course_data["sections"])
                        section_progress = (current_section + 1) / total_sections
                        
                        current_section_data = course_data["sections"][current_section]
                        total_steps = len(current_section_data["steps"])
                        step_progress = (current_step + 1) / total_steps
                        
                        st.sidebar.subheader("Overall Progress")
                        st.sidebar.progress(section_progress)
                        
                        st.sidebar.subheader("Current Section Progress")
                        st.sidebar.progress(step_progress)
                        
                        # Display sections with status
                        for section in course_data["sections"]:
                            section_index = section["order"] - 1
                            if section_index < current_section:
                                st.sidebar.success(f"✅ {section['title']}")
                            elif section_index == current_section:
                                steps_text = f"(Step {current_step + 1}/{total_steps})"
                                st.sidebar.info(f"📚 {section['title']} {steps_text}")
                            else:
                                st.sidebar.text(f"⏳ {section['title']}")
                        
                        # Display current content
                        if current_section_data:
                            with st.sidebar.expander("Current Section Details"):
                                if current_step < len(current_section_data["steps"]):
                                    current_step_content = current_section_data["steps"][current_step]["content"]
                                    st.markdown(current_step_content)
                        
                        # Display remaining sections
                        remaining_sections = total_sections - current_section
                        if remaining_sections > 0:
                            st.sidebar.info(f"📝 {remaining_sections} sections remaining")
                    else:
                        st.sidebar.info("Kursa başlamak için 'evet' yazın.")
                    
        except Exception as e:
            logger.error(f"Error in sidebar: {str(e)}")  # Log the error
            st.sidebar.error(f"Error loading course content: {str(e)}")
