from fastapi import APIRouter, HTTPException, Depends
from server.models.llm import LLMRequest, LLMResponse
from server.models.chat import Message, ChatHistory
from server.models.course import Course
from server.services.langchain.chat import initialize_chat
from server.services.course_loader import load_course_content
from server.database import db
from datetime import datetime
import logging
import os

router = APIRouter(prefix="/llm", tags=["LLM"])

logger = logging.getLogger(__name__)
chat_collection = db.get_collection("chat_history")
course_collection = db.get_collection("courses")


@router.post("/start-course/{course_id}")
async def start_course(course_id: str, user_id: str = "default_user"):
    try:
        # Load course content
        course = load_course_content(course_id)

        # Initialize chat with course context
        agent_executor = initialize_chat(
            conversation_id=user_id, chat_history=[], course=course
        )

        # Create welcome message
        welcome_message = Message(
            role="assistant",
            content=f"Merhaba! {course.title} dersine hoş geldin! Başlamaya hazır mısın? (Evet/Hayır)",
        )

        # Store course state in database with special initial step
        await course_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "course_id": course_id,
                    "current_section": 0,
                    "current_step": -1,  # Özel başlangıç adımı
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        # Clear and initialize chat history
        await chat_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "messages": [welcome_message.dict()],
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        return {"message": welcome_message.dict()}
    except Exception as e:
        logger.error(f"Error starting course: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/completions", response_model=LLMResponse)
async def llm_completions(request: LLMRequest, user_id: str = "default_user"):
    try:
        # Debug için
        logger.info(f"Request: {request.dict()}")
        logger.info(f"User ID: {user_id}")
        
        course_state, chat_history = await fetch_user_data(user_id)
        if not course_state:
            raise HTTPException(status_code=400, detail="No active course found")

        # Debug için
        logger.info(f"Course State: {course_state}")
        logger.info(f"Chat History: {chat_history}")

        course, current_section_obj, current_step_obj = load_course_details(course_state)
        
        # Debug için
        logger.info(f"Current Section: {current_section_obj}")
        logger.info(f"Current Step: {current_step_obj}")
        
        messages_list = prepare_chat_history(chat_history)
        agent_executor = initialize_chat(conversation_id=user_id, chat_history=messages_list, course=course)
        
        user_input = request.input.lower()
        llm_output = await process_user_input(
            user_input,
            current_step_obj,
            current_section_obj,
            course_state,
            agent_executor,
            user_id,
        )
        
        await update_chat_history(user_id, request.input, llm_output)
        return LLMResponse(output=llm_output)
        
    except Exception as e:
        logger.error(f"Error in llm_completions endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def fetch_user_data(user_id):
    """Fetch user's course state and chat history."""
    course_state = await course_collection.find_one({"user_id": user_id})
    chat_history = await chat_collection.find_one({"user_id": user_id})
    return course_state, chat_history


def load_course_details(course_state):
    """Load course details and current section/step information."""
    try:
        course = load_course_content(course_state["course_id"])
        current_section = course_state["current_section"]
        current_step = course_state.get("current_step", 0)
        
        # Bölüm ve adım sınırlarını kontrol et
        if current_section >= len(course.sections):
            current_section = len(course.sections) - 1
            
        current_section_obj = course.sections[current_section]
        
        if current_step >= len(current_section_obj.steps):
            current_step = 0
            current_section += 1
            if current_section < len(course.sections):
                current_section_obj = course.sections[current_section]
        
        current_step_obj = current_section_obj.steps[current_step]
        
        # Course state'i güncelle
        course.current_section = current_section
        current_section_obj.current_step = current_step
        
        return course, current_section_obj, current_step_obj
    except Exception as e:
        logger.error(f"Error in load_course_details: {str(e)}")
        raise


def prepare_chat_history(chat_history):
    """Prepare chat history as a list of messages."""
    if chat_history and "messages" in chat_history:
        return [
            {"role": msg.get("role", ""), "content": msg.get("content", "")}
            for msg in chat_history["messages"]
            if "role" in msg and "content" in msg
        ]
    return []


async def process_user_input(
    user_input,
    current_step_obj,
    current_section_obj,
    course_state,
    agent_executor,
    user_id,
):
    """Process user input and determine appropriate response."""
    try:
        current_step = course_state["current_step"]
        current_section = course_state["current_section"]
        
        # Başlangıç kontrolü
        if current_step == -1:
            if "evet" in user_input.lower():
                await course_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {"current_step": 0}}
                )
                return current_section_obj.steps[0].content
            else:
                return "Hazır olduğunda 'evet' yazabilirsin. Başlamak için sabırsızlanıyorum!"

        # Normal akış - beklenen yanıtları kontrol et
        if current_step_obj.expected_responses:
            is_correct = any(
                expected.lower() in user_input.lower()
                for expected in current_step_obj.expected_responses
            )
            
            if is_correct:
                try:
                    # Önce mevcut adımın next_action'ını kontrol et
                    if current_step_obj.next_action == "FINISH":
                        # Kursu bitir
                        await course_collection.update_one(
                            {"user_id": user_id},
                            {
                                "$set": {
                                    "completed": True,
                                    "completed_at": datetime.utcnow(),
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )
                        return "Tebrikler! 🎉 Kursu başarıyla tamamladın! Harika bir iş çıkardın!"

                    # Normal akış - sonraki adıma geç
                    next_step = current_step + 1
                    next_section = current_section
                    
                    # Mevcut bölümün son adımında mıyız kontrol et
                    if next_step >= len(current_section_obj.steps):
                        if current_step_obj.next_action == "NEXT":
                            next_section = current_section + 1
                            next_step = 0
                    
                    # Course state'i güncelle
                    await course_collection.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {
                                "current_step": next_step,
                                "current_section": next_section,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    
                    # Yeni course state'i yükle
                    updated_course = load_course_content(course_state["course_id"])
                    
                    # Bölüm değişti mi kontrol et
                    if next_section != current_section and next_section < len(updated_course.sections):
                        next_section_obj = updated_course.sections[next_section]
                        return f"Tebrikler! '{current_section_obj.title}' bölümünü tamamladın.\n\nYeni bölüm: {next_section_obj.title}\n\n{next_section_obj.steps[0].content}"
                    
                    # Aynı bölümde devam
                    elif next_step < len(current_section_obj.steps):
                        return f"Harika! Doğru cevap verdin.\n\n{current_section_obj.steps[next_step].content}"
                        
                except Exception as e:
                    logger.error(f"Error processing correct answer: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail="Doğru cevap işlenirken bir hata oluştu"
                    )
            else:
                # Yanlış yanıt durumu
                return f"Tekrar denemelisin. İpucu: Beklenen cevaplardan biri: {current_step_obj.expected_responses[0]}"
        
        # Normal sohbet yanıtı için context oluştur
        context_prompt = create_context_prompt(current_step_obj, user_input)
        response = await agent_executor.ainvoke({"input": context_prompt})
        return response.get("output", "")
        
    except Exception as e:
        logger.error(f"Error in process_user_input: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"İşlem sırasında bir hata oluştu: {str(e)}"
        )


def create_context_prompt(current_step_obj, user_input):
    """Create context prompt for the AI model based on current step and user input."""
    return f"""
    MEVCUT DERS DURUMU:
    {current_step_obj.content}
    
    ÖĞRENCİ CEVABI:
    {user_input}
    
    BEKLENEN CEVAPLAR:
    {', '.join(current_step_obj.expected_responses) if current_step_obj.expected_responses else 'Beklenen cevap yok'}
    
    GÖREV:
    1. Öğrencinin cevabını değerlendir
    2. Eğer doğruysa, neden doğru olduğunu açıkla ve konuyu genişlet
    3. Eğer yanlışsa, nazikçe düzelt ve doğru cevabı detaylı açıkla
    4. Bir sonraki konuya geçiş yap
    5. Öğrenciyi motive edici bir dille yanıt ver
    
    Yanıtını şu formatta ver:
    DEĞERLENDİRME: (Doğru/Yanlış)
    AÇIKLAMA: (Detaylı açıklama)
    DEVAM: (Bir sonraki adımın içeriği)
    """


async def get_llm_response(agent_executor, context_prompt):
    """Invoke the AI model and return its response."""
    response = await agent_executor.ainvoke({"input": context_prompt})
    return response.get("output", "")


async def update_course_step(user_id, next_step):
    """Update the course step for the user in the database."""
    await course_collection.update_one(
        {"user_id": user_id},
        {"$set": {"current_step": next_step, "updated_at": datetime.utcnow()}},
    )


async def parse_and_update_steps(
    response_text, current_step_obj, current_section_obj, course_state, user_id
):
    """Parse AI response, update steps, and return formatted output."""
    # Parse response for explanation and continuation

    # print(f"response_text: {response_text}")
    is_correct, explanation, continuation = parse_response_text(response_text)

    # print(f"is_correct: {is_correct}")
    # print(f"explanation: {explanation}")
    # print(f"continuation: {continuation}")

    next_step = course_state["current_step"] + 1
    await update_course_step(user_id, next_step)

    return f"{explanation}\n\n{continuation}\n\n{current_section_obj.steps[next_step].content}"


def parse_response_text(response_text):
    """Parse the response text from AI model to extract key components."""
    is_correct = False
    explanation = ""
    continuation = ""

    # Satırları ayır
    parts = response_text.split("\n")

    for part in parts:
        part = part.strip()
        if part.startswith("DEĞERLENDİRME:"):
            # "Doğru" kelimesini bulup is_correct olarak ayarla
            is_correct = "Doğru" in part
        elif part.startswith("AÇIKLAMA:"):
            # AÇIKLAMA kısmının tamamını al
            explanation = part.split("AÇIKLAMA:", 1)[1].strip()
        elif part.startswith("DEVAM:"):
            # DEVAM kısmının tamamını al
            continuation = part.split("DEVAM:", 1)[1].strip()

    return is_correct, explanation, continuation


async def update_chat_history(user_id, user_input, assistant_response):
    """Update chat history with user and assistant messages."""
    await chat_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "messages": [
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": assistant_response},
                ]
            },
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )


@router.get("/history/{user_id}")
async def get_chat_history(user_id: str):
    """
    Get chat history for a specific user
    """
    chat_history = await chat_collection.find_one({"user_id": user_id})
    if not chat_history:
        return {"messages": []}
    return chat_history


@router.get("/course-content/{course_id}")
async def get_course_content(course_id: str):
    """
    Get course content and structure
    """
    try:
        course = load_course_content(course_id)
        return course.dict()
    except Exception as e:
        logger.error(f"Error loading course content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/course-state/{user_id}")
async def get_course_state(user_id: str):
    """
    Get current course state for a user
    """
    course_state = await course_collection.find_one({"user_id": user_id})
    if not course_state:
        return {"current_section": 0, "current_step": 0}
    return {
        "current_section": course_state.get("current_section", 0),
        "current_step": course_state.get("current_step", 0),
    }


@router.get("/available-courses")
async def get_available_courses():
    """
    Get list of available courses
    """
    try:
        # courses klasöründeki tüm yaml dosyalarını listele
        courses_dir = "courses"
        course_files = [f.replace('.yaml', '') for f in os.listdir(courses_dir) if f.endswith('.yaml')]
        
        # Her kurs için başlık ve açıklamayı al
        courses = []
        for course_id in course_files:
            try:
                course = load_course_content(course_id)
                courses.append({
                    "id": course_id,
                    "title": course.title,
                    "description": course.description
                })
            except Exception as e:
                logger.error(f"Error loading course {course_id}: {str(e)}")
                continue
                
        return courses
    except Exception as e:
        logger.error(f"Error getting available courses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
