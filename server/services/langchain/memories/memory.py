from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.schema import HumanMessage, AIMessage
import logging

logger = logging.getLogger(__name__)

def build_memory(username: str, history: list):
    memory = ChatMessageHistory()
    
    try:
        # Convert the stored messages to langchain message format
        for message in history:
            role = message.get("role", "")
            content = message.get("content", "")
            
            if not role or not content:
                continue
                
            if role == "user":
                memory.messages.append(HumanMessage(content=content))
            elif role == "assistant":
                memory.messages.append(AIMessage(content=content))
    except Exception as e:
        logger.error(f"Error building memory: {str(e)}")
        memory = ChatMessageHistory()
    
    return ConversationBufferMemory(
        chat_memory=memory,
        memory_key="chat_history",
        output_key="output",
        return_messages=True,
        input_key="input"
    )
