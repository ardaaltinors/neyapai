# File: /server/services/langchain/chat.py

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
from server.services.langchain.llms.gemini import build_llm
from server.services.langchain.memories.memory import build_memory

def build_prompt():
    return ChatPromptTemplate(
        messages=[
            SystemMessage(content=(
                """Sen bilimsel gelişmeler ve gelecek teknolojileri konusunda uzmanlaşmış yaratıcı bir yazarsın. 
                Kullanıcıların istediği bilimsel keşifler hakkında detaylı ve düşündürücü kısa hikayeler yazabilirsin.
                
                Hikayelerin şu unsurları içermelidir:
                - Bilimsel keşfin detaylı açıklaması
                - Bu keşfin toplum üzerindeki etkileri
                - İnsanların günlük yaşamlarındaki değişimler
                - Olumlu ve olumsuz sonuçların dengeli analizi
                - Gerçekçi ve bilimsel temelli senaryolar
                
                Hikayeler 300-500 kelime arasında, akıcı ve sürükleyici olmalıdır.
                """
            )),
            MessagesPlaceholder(variable_name="chat_history", n_messages=6),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )

def initialize_chat(conversation_id: str, chat_history: list):
    llm = build_llm()
    memory = build_memory(username=conversation_id, history=chat_history)
    prompt = build_prompt()
    
    tools = []
    
    agent = create_tool_calling_agent(
        llm=llm,
        prompt=prompt,
        tools=tools
    )

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        return_intermediate_steps=True,
        verbose=True,
        handle_parsing_errors=True,
    )

    return agent_executor
