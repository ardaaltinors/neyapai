# File: /server/services/langchain/chat.py

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
from server.services.langchain.llms.gemini import build_llm
from server.services.langchain.memories.memory import build_memory
from server.models.course import Course

def build_prompt(course: Course = None):
    system_content = """
    Sen bir öğretmen asistanısın. Öğrencilere ders içeriğini adım adım öğretmekle görevlisin.
    
    Görevlerin:
    1. Her bölümü sırayla ve detaylı şekilde anlatmak
    2. Öğrencinin anlayıp anlamadığını kontrol etmek
    3. Öğrenci hazır olduğunda bir sonraki bölüme geçmek
    4. Her bölümün sonunda öğrenme hedeflerine ulaşılıp ulaşılmadığını kontrol etmek
    
    Kurallar:
    1. Her seferinde sadece mevcut bölümün içeriğine odaklan
    2. Öğrenci anlamadan yeni bölüme geçme
    3. Her bölümün sonunda özet yap ve öğrencinin hazır olup olmadığını kontrol et
    4. Öğrenci hazırsa, bir sonraki bölüme geçmek için onay iste
    5. Her yanıtın sonuna şu formatla ilerleme durumunu ekle:
       [PROGRESS: CONTINUE] - Aynı bölüme devam et
       [PROGRESS: NEXT] - Bir sonraki bölüme geç
       [PROGRESS: REVIEW] - Bölümü tekrar et
    """
    
    if course:
        current_section = course.sections[course.current_section]
        system_content += f"""
        Kurs: {course.title}
        Açıklama: {course.description}
        Toplam Bölüm: {len(course.sections)}
        Mevcut Bölüm: {current_section.title}
        Bölüm İçeriği: {current_section.content}
        
        Öğrenme Hedefleri:
        {current_section.content.split('Öğrenme Hedefleri:')[1].strip() if 'Öğrenme Hedefleri:' in current_section.content else 'Belirtilmemiş'}
        """
    
    return ChatPromptTemplate(
        messages=[
            SystemMessage(content=system_content),
            MessagesPlaceholder(variable_name="chat_history", n_messages=6),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )

def initialize_chat(conversation_id: str, chat_history: list, course: Course = None):
    llm = build_llm()
    memory = build_memory(username=conversation_id, history=chat_history)
    prompt = build_prompt(course)
    
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
