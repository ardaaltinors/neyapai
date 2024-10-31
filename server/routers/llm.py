from fastapi import APIRouter, HTTPException, Depends
from server.models.llm import LLMRequest, LLMResponse
from server.models.chat import Message, ChatHistory
from server.models.course import Course, Step
from server.services.langchain.chat import initialize_chat
from server.services.course_loader import load_course_content
from server.database import db
from datetime import datetime
import logging

from server.utils.async_utils import async_retry

router = APIRouter(prefix="/llm", tags=["LLM"])

logger = logging.getLogger(__name__)
chat_collection = db.get_collection("chat_history")
course_collection = db.get_collection("courses")

@async_retry(max_retries=3, delay=2)  # Adjust retries and delay as needed
async def invoke_llm_with_retry(agent_executor, user_input: str) -> dict:
    """
    Invokes the LLM with retry mechanism.
    
    Args:
        agent_executor: The initialized agent executor for the LLM.
        user_input (str): The input string from the user.

    Returns:
        dict: The response from the LLM.
    """
    try:
        response = await agent_executor.ainvoke({"input": user_input})
        return response
    except Exception as e:
        logger.error(f"LLM invocation failed: {str(e)}")
        raise  # Re-raise exception to trigger retry


@router.post("/start-course/{course_id}")
async def start_course(course_id: str, user_id: str = "default_user"):
    try:
        # Load course content
        course = load_course_content(course_id)

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
    user_input = request.input
    
    try:
        course_state, chat_history = await fetch_user_data(user_id)
        if not course_state:
            raise HTTPException(status_code=400, detail="No active course found")

        course, current_section_obj, current_step_obj = load_course_details(course_state)
        messages_list = prepare_chat_history(chat_history)

        agent_executor = initialize_chat(
            conversation_id=user_id, chat_history=messages_list, course=course
        )
        
        agent_response = await invoke_llm_with_retry(agent_executor, user_input)

        await update_chat_history(user_id, user_input, agent_response["output"])
        
        return LLMResponse(output=agent_response["output"])

    except ValueError as ve:
        logger.error(f"LLM invocation failed after retries: {str(ve)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again later.")
    except HTTPException as he:
        raise he  # Re-raise HTTPExceptions to be handled by FastAPI
    except Exception as e:
        logger.error(f"Unexpected error in llm_completions endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


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


async def update_chat_history(user_id, user_input, assistant_response):
    """Update chat history with user and assistant messages."""
    await chat_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "messages": {
                    "$each": [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": assistant_response},
                    ]
                }
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
    
@router.post("/next-step", response_model=Step)
async def next_step(user_id: str = "default_user"):
    """
    Advance the user to the next step in the current course.
    """
    try:
        # Fetch user's current course state
        course_state = await course_collection.find_one({"user_id": user_id})
        if not course_state:
            raise HTTPException(status_code=400, detail="No active course found for user.")

        # Load course details
        course = load_course_content(course_state["course_id"])
        current_section_idx = course_state.get("current_section", 0)
        current_step_idx = course_state.get("current_step", 0)

        # Get current section and step
        if current_section_idx >= len(course.sections):
            raise HTTPException(status_code=400, detail="All sections completed.")

        current_section = course.sections[current_section_idx]
        if current_step_idx >= len(current_section.steps):
            # Move to next section
            current_section_idx += 1
            if current_section_idx >= len(course.sections):
                # Course completed
                return {"message": "Tebrikler! Tüm dersi tamamladınız."}
            current_step_idx = 0
            current_section = course.sections[current_section_idx]

        # Get the next step
        next_step = current_section.steps[current_step_idx]

        # Update course state in the database
        await course_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "current_section": current_section_idx,
                    "current_step": current_step_idx + 1,
                    "updated_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        # Optionally, you can send the next step's content as a message to the user
        assistant_message = Message(
            role="assistant",
            content=next_step.content,
        )
        await chat_collection.update_one(
            {"user_id": user_id},
            {
                "$push": {"messages": assistant_message.dict()},
                "$set": {"updated_at": datetime.utcnow()},
            },
            upsert=True,
        )

        return next_step

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error advancing to next step: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
