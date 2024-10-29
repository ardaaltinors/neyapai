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
        course_id = st.selectbox(
            "Select a course:",
            ["solar_system", "basic_math", "programming_101"]
        )
        
        if st.button("Start Course"):
            result = start_course(course_id)
            if result:
                welcome_message = result["message"]
                st.session_state.messages.append(welcome_message)
                st.session_state.course_started = True
                st.rerun()

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
        
        # Get course content and current progress
        try:
            # Get current course state
            response_state = requests.get(f"{API_BASE_URL}/llm/course-state/default_user")
            course_state = response_state.json()
            current_section = course_state.get("current_section", 0)
            current_step = course_state.get("current_step", 0)
            
            # Get course content
            response = requests.get(f"{API_BASE_URL}/llm/course-content/solar_system")
            course_data = response.json()
            
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
                    st.markdown(current_section_data["content"])
                    
                if "Öğrenme Hedefleri:" in current_section_data["content"]:
                    with st.sidebar.expander("Learning Objectives"):
                        objectives = current_section_data["content"].split("Öğrenme Hedefleri:")[1].strip()
                        st.markdown(objectives)
            
            # Display completion status
            if current_section >= total_sections - 1 and current_step >= total_steps - 1:
                st.sidebar.success("🎉 Course Completed!")
            else:
                remaining_sections = total_sections - current_section
                st.sidebar.info(f"📝 {remaining_sections} sections remaining")
                    
        except Exception as e:
            st.sidebar.error(f"Error loading course content: {str(e)}")
