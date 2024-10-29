from fastapi import APIRouter, HTTPException, Depends
from server.models.llm import LLMRequest, LLMResponse
from server.models.chat import Message, ChatHistory
from server.models.course import Course
from server.services.langchain.chat import initialize_chat
from server.services.course_loader import load_course_content
from server.database import db
from datetime import datetime
import logging

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
            content=f"Merhaba! {course.title} dersine hoş geldin! Başlamaya hazır mısın?",
        )

        # Store course state in database
        await course_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "course_id": course_id,
                    "current_section": 0,
                    "current_step": 0,
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
        course_state, chat_history = await fetch_user_data(user_id)
        if not course_state:
            raise HTTPException(status_code=400, detail="No active course found")

        course, current_section_obj, current_step_obj = load_course_details(
            course_state
        )
        messages_list = prepare_chat_history(chat_history)

        agent_executor = initialize_chat(
            conversation_id=user_id, chat_history=messages_list, course=course
        )

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
    course = load_course_content(course_state["course_id"])
    current_section = course_state["current_section"]
    current_step = course_state.get("current_step", 0)
    current_section_obj = course.sections[current_section]
    current_step_obj = current_section_obj.steps[current_step]
    return course, current_section_obj, current_step_obj


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
    if current_step_obj.expected_responses and check_for_ready_to_start(
        user_input, course_state
    ):
        return await handle_ready_response(current_section_obj, course_state, user_id)

    if check_for_skip_response(user_input):
        return await handle_skip_response(current_section_obj, course_state, user_id)

    context_prompt = create_context_prompt(current_step_obj, user_input)
    response_text = await get_llm_response(agent_executor, context_prompt)

    return await parse_and_update_steps(
        response_text, current_step_obj, current_section_obj, course_state, user_id
    )


def check_for_ready_to_start(user_input, course_state):
    """Check if user is ready to start the course."""
    return course_state["current_step"] == 0 and "evet" in user_input


def check_for_skip_response(user_input):
    """Check if user wants to skip the step."""
    skip_responses = ["bilmiyorum", "hayır", "istemiyorum", "geç", "pass", "skip"]
    return any(skip in user_input for skip in skip_responses)


async def handle_ready_response(current_section_obj, course_state, user_id):
    """Handle ready response from user."""
    next_step = 1
    await update_course_step(user_id, next_step)
    return current_section_obj.steps[next_step].content


async def handle_skip_response(current_section_obj, course_state, user_id):
    """Handle skip response and advance to next step."""
    next_step = course_state["current_step"] + 1
    await update_course_step(user_id, next_step)
    return f"Anlamadığın noktaları açıklayayım:\n\n{current_section_obj.steps[next_step].content}"


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

    print(f"response_text: {response_text}")
    is_correct, explanation, continuation = parse_response_text(response_text)

    print(f"is_correct: {is_correct}")
    print(f"explanation: {explanation}")
    print(f"continuation: {continuation}")

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
