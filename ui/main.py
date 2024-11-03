import os
from pathlib import Path
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
COMPLETIONS_URL = f"{API_BASE_URL}/llm/completions"
START_COURSE_URL = f"{API_BASE_URL}/llm/start-course"

# Ana dizini belirle
ROOT_DIR = Path(__file__).parent.parent


# Statik dosya yolunu ayarla
def get_image_path(image_path: str) -> str:
    """Convert image path to absolute path"""
    if image_path.startswith("/"):
        image_path = image_path[1:]
    return str(ROOT_DIR / image_path)


def start_course(course_id: str, user_id: str = "default_user"):
    try:
        response = requests.post(
            f"{START_COURSE_URL}/{course_id}", params={"user_id": user_id}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Kurs başlatılırken hata oluştu: {str(e)}")
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
    st.markdown(
        """
        # 🎓 NeYapAI: Yapay Zeka Destekli İnteraktif Öğrenme Platformu

        NeYapAI, öğrenme deneyiminizi dönüştüren yenilikçi bir eğitim platformudur.

        ## 🌟 Platform Özellikleri:
        - **👤 Kişiselleştirilmiş Öğrenme**: Her öğrencinin ihtiyaçlarına özel içerik
        - **🔄 Etkileşimli İçerik**: Adım adım ilerleyen dinamik kurs yapısı
        - **⚡ Anlık Geri Bildirim**: Yapay zeka destekli değerlendirmeler
        - **📊 İlerleme Takibi**: Detaylı öğrenme analitikleri

        Gemini destekli yapay zeka asistanımız, öğrenme yolculuğunuzda size rehberlik etmek için hazır!
        """
    )

    # Course selection and start
    if not st.session_state.course_started:
        try:
            # Get available courses
            response = requests.get(f"{API_BASE_URL}/llm/available-courses")
            courses = response.json()

            # Create course selection options
            course_options = {course["title"]: course["id"] for course in courses}

            selected_title = st.selectbox(
                "Bir kurs seçin:", options=list(course_options.keys())
            )

            # Get selected course ID
            selected_course_id = course_options[selected_title]

            if st.button("Kursa Başla"):
                result = start_course(selected_course_id)
                if result:
                    welcome_message = result["message"]
                    st.session_state.messages.append(welcome_message)
                    st.session_state.course_started = True
                    # Store selected course ID in session state
                    st.session_state.current_course_id = selected_course_id
                    st.rerun()

        except Exception as e:
            st.error(f"Kurslar yüklenirken hata oluştu: {str(e)}")

    # Chat interface
    if st.session_state.course_started:
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                content = message["content"]

                # Markdown içeriğini parçalara ayır (resim ve metin)
                if "![" in content and "](/images/" in content:
                    # Metni parçalara ayır
                    parts = content.split("![")

                    # İlk metin parçasını göster
                    st.markdown(parts[0])

                    # Resim ve sonraki metin parçalarını işle
                    for part in parts[1:]:
                        if "](" in part:
                            img_title, rest = part.split("](")
                            img_path, text = rest.split(")", 1)

                            # Resim yolunu düzelt
                            if img_path.startswith("/images/"):
                                img_path = img_path.replace("/images/", "")
                                full_path = str(ROOT_DIR / "images" / img_path)

                                # Resmi göster
                                try:
                                    st.image(full_path, caption=img_title)
                                except Exception as e:
                                    st.error(f"Resim yüklenirken hata oluştu: {str(e)}")

                            # Kalan metni göster
                            if text:
                                st.markdown(text)
                else:
                    # Resim yoksa normal markdown olarak göster
                    st.markdown(content)

        # Kursun tamamlanıp tamamlanmadığını kontrol et
        is_course_completed = len(
            st.session_state.messages
        ) > 0 and "Tebrikler! 🎉 Kursu başarıyla tamamladın" in st.session_state.messages[
            -1
        ].get(
            "content", ""
        )

        # Chat input - sadece kurs tamamlanmamışsa göster
        if not is_course_completed:
            if prompt := st.chat_input("Mesajınızı buraya yazın..."):
                # Add user message to chat
                st.session_state.messages.append({"role": "user", "content": prompt})

                # Get AI response
                try:
                    response = requests.post(
                        COMPLETIONS_URL,
                        json={"input": prompt},
                        params={"user_id": "default_user"},
                    )
                    response.raise_for_status()

                    ai_message = {
                        "role": "assistant",
                        "content": response.json()["output"],
                    }
                    st.session_state.messages.append(ai_message)
                    st.rerun()

                except Exception as e:
                    st.error(f"Hata: {str(e)}")
        else:
            # Kurs tamamlandığında gösterilecek mesaj
            st.info(
                "Kurs tamamlandı! Yeni bir kursa başlamak için sidebar'daki 'Yeni Kursa Başla' butonunu kullanabilirsiniz."
            )

# Sidebar with course progress
with col2:
    if st.session_state.course_started:
        st.sidebar.title("Kurs İlerlemesi")

        try:
            # Get current course state
            response_state = requests.get(
                f"{API_BASE_URL}/llm/course-state/default_user"
            )
            course_state = response_state.json()
            current_section = course_state.get("current_section", 0)
            current_step = course_state.get("current_step", -1)

            # Get course content for the selected course
            current_course_id = st.session_state.get("current_course_id")
            if current_course_id:
                response = requests.get(
                    f"{API_BASE_URL}/llm/course-content/{current_course_id}"
                )
                course_data = response.json()

                # Kurs tamamlanma kontrolü
                is_completed = False
                if current_step >= 0:
                    current_section_data = course_data["sections"][current_section]
                    if current_step < len(current_section_data["steps"]):
                        current_step_obj = current_section_data["steps"][current_step]
                        is_completed = current_step_obj.get(
                            "next_action"
                        ) == "FINISH" and "Tebrikler! 🎉 Kursu başarıyla tamamladın" in st.session_state.messages[
                            -1
                        ].get(
                            "content", ""
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

                        st.sidebar.subheader("Genel İlerleme")
                        st.sidebar.progress(section_progress)

                        st.sidebar.subheader("Mevcut Bölüm İlerlemesi")
                        st.sidebar.progress(step_progress)

                        # Display sections with status
                        for section in course_data["sections"]:
                            section_index = section["order"] - 1
                            if section_index < current_section:
                                st.sidebar.success(f"✅ {section['title']}")
                            elif section_index == current_section:
                                steps_text = f"(Adım {current_step + 1}/{total_steps})"
                                st.sidebar.info(f"📚 {section['title']} {steps_text}")
                            else:
                                st.sidebar.text(f"⏳ {section['title']}")

                        # Display remaining sections
                        remaining_sections = total_sections - current_section
                        if remaining_sections > 0:
                            st.sidebar.info(f"📝 {remaining_sections} bölüm kaldı")
                    else:
                        st.sidebar.info("Kursa başlamak için 'evet' yazın.")

        except Exception as e:
            logger.error(f"Sidebar hatası: {str(e)}")  # Log the error
            st.sidebar.error(f"Kurs içeriği yüklenirken hata oluştu: {str(e)}")
