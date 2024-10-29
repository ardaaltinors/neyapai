from fastapi import APIRouter, HTTPException, Depends
from server.models.llm import LLMRequest, LLMResponse
from server.models.chat import Message, ChatHistory
from server.models.course import Course
from server.services.langchain.chat import initialize_chat
from server.services.course_loader import load_course_content
from server.database import db
from datetime import datetime
import logging

router = APIRouter(
    prefix="/llm",
    tags=["LLM"]
)

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
            conversation_id=user_id,
            chat_history=[],
            course=course
        )
        
        # Create welcome message
        welcome_message = Message(
            role="assistant",
            content=f"Merhaba! {course.title} dersine hoş geldin! Başlamaya hazır mısın?"
        )
        
        # Store course state in database
        await course_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "course_id": course_id,
                    "current_section": 0,
                    "current_step": 0,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        # Clear and initialize chat history
        await chat_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "messages": [welcome_message.dict()],
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {"message": welcome_message.dict()}
    except Exception as e:
        logger.error(f"Error starting course: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/completions", response_model=LLMResponse)
async def llm_completions(request: LLMRequest, user_id: str = "default_user"):
    try:
        # Fetch course state and chat history
        course_state = await course_collection.find_one({"user_id": user_id})
        chat_history = await chat_collection.find_one({"user_id": user_id})
        
        if not course_state:
            raise HTTPException(status_code=400, detail="No active course found")
            
        # Load course content
        course = load_course_content(course_state["course_id"])
        current_section = course_state["current_section"]
        current_step = course_state.get("current_step", 0)
        
        # Get current step
        current_section_obj = course.sections[current_section]
        current_step_obj = current_section_obj.steps[current_step]
        
        # Initialize chat with history and course context
        messages_list = []
        if chat_history and "messages" in chat_history:
            messages_list = [
                {
                    "role": msg.get("role", ""),
                    "content": msg.get("content", "")
                }
                for msg in chat_history["messages"]
                if "role" in msg and "content" in msg
            ]
        
        # Initialize agent_executor
        agent_executor = initialize_chat(
            conversation_id=user_id,
            chat_history=messages_list,
            course=course
        )
        
        # Process user input and generate response
        new_message = Message(role="user", content=request.input)
        llm_output = ""
        next_step = None
        
        # Check if current step has expected responses
        if current_step_obj.expected_responses:
            user_input_lower = request.input.lower()
            
            # Special handling for first step (ready to start)
            if current_step == 0 and current_section == 0:
                ready_responses = ["evet", "hazırım", "başlayalım", "evet hazırım"]
                if any(resp in user_input_lower for resp in ready_responses):
                    next_step = 1
                    await course_collection.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {
                                "current_step": next_step,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    llm_output = current_section_obj.steps[next_step].content
                    return LLMResponse(output=llm_output)
                else:
                    llm_output = "Hazır olduğunda 'evet' yazabilirsin."
                    return LLMResponse(output=llm_output)
            
            # Regular flow for other steps
            # Check for skip/pass responses
            skip_responses = ["bilmiyorum", "hayır", "istemiyorum", "geç", "pass", "skip"]
            if any(skip in user_input_lower for skip in skip_responses):
                if current_step < len(current_section_obj.steps) - 1:
                    next_step = current_step + 1
                    llm_output = f"Anlamadığın noktaları açıklayayım:\n\n"
                    llm_output += current_section_obj.steps[next_step].content
            else:
                # Send both user input and expected responses to LLM for validation
                validation_prompt = f"""
                Öğrenci cevabı: {user_input_lower}
                Beklenen cevaplar: {', '.join(current_step_obj.expected_responses)}
                
                Öğrencinin cevabı doğru mu? Eğer doğruysa neden doğru olduğunu, yanlışsa doğru cevabı açıkla.
                Cevabını şu formatta ver:
                DOĞRU/YANLIŞ: <açıklama>
                """
                
                try:
                    validation_response = await agent_executor.ainvoke({"input": validation_prompt})
                    response_text = validation_response.get("output", "").lower()
                    is_correct = "doğru:" in response_text
                    
                    if is_correct:
                        if current_step < len(current_section_obj.steps) - 1:
                            next_step = current_step + 1
                            explanation = response_text.split("doğru:")[1].strip()
                            llm_output = f"{explanation}\n\nŞimdi devam edelim:\n\n{current_section_obj.steps[next_step].content}"
                    else:
                        if current_step < len(current_section_obj.steps) - 1:
                            next_step = current_step + 1
                            explanation = response_text.split("yanliş:")[1].strip() if "yanliş:" in response_text else response_text
                            llm_output = f"{explanation}\n\nDevam edelim:\n\n{current_section_obj.steps[next_step].content}"
                        
                except Exception as e:
                    logger.error(f"LLM validation error: {str(e)}")
                    # If validation fails, continue with next step
                    if current_step < len(current_section_obj.steps) - 1:
                        next_step = current_step + 1
                        llm_output = f"Cevabını tam olarak değerlendiremedim. Devam edelim:\n\n{current_section_obj.steps[next_step].content}"

        # Update step if needed
        if next_step is not None:
            await course_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "current_step": next_step,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        # Handle section transitions
        if current_step == len(current_section_obj.steps) - 1:
            if current_section < len(course.sections) - 1:
                next_section = current_section + 1
                await course_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_section": next_section,
                            "current_step": 0,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                section_intro = f"\n\nHarika! Bu bölümü tamamladın. Şimdi {course.sections[next_section].title} bölümüne geçiyoruz.\n\n"
                section_intro += course.sections[next_section].steps[0].content
                llm_output = section_intro
            else:
                llm_output = "\n\nTebrikler! Tüm kursu başarıyla tamamladın! 🎉"
        
        # Update chat history
        assistant_message = Message(role="assistant", content=llm_output)
        await chat_collection.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [
                            new_message.dict(),
                            assistant_message.dict()
                        ]
                    }
                },
                "$set": {"updated_at": datetime.utcnow()}
            },
            upsert=True
        )
        
        return LLMResponse(output=llm_output)
        
    except Exception as e:
        logger.error(f"Error in llm_completions endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
        "current_step": course_state.get("current_step", 0)
    }
