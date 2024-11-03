# File: /server/services/langchain/chat.py

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.schema import SystemMessage
from server.services.langchain.llms.gemini import build_llm
from server.services.langchain.memories.memory import build_memory
from server.models.course import Course


def build_prompt(course: Course = None):
    system_template = """
    Sen bir öğretmen asistanısın. Öğrencilere ders içeriğini adım adım öğretmekle görevlisin.
    
    Görevlerin:
    1. Her adımı sırayla ve detaylı şekilde anlatmak
    2. Öğrencinin cevaplarını değerlendirmek
    3. Beklenen yanıtları kontrol etmek
    4. Öğrenciyi motive etmek
    
    Kurallar:
    1. Her seferinde sadece mevcut adımın içeriğine odaklan
    2. Öğrenci doğru cevap vermeden bir sonraki adıma geçme
    3. Yanlış cevaplarda ipucu ver ve tekrar denemesini iste
    4. Öğrenciyi Türkçe olarak yanıtla
    
    {course_info}
    """

    course_info = ""
    if course:
        current_section = course.sections[course.current_section]
        current_step = current_section.steps[current_section.current_step]

        course_info = f"""
        Kurs: {course.title}
        Açıklama: {course.description}
        Mevcut Bölüm: {current_section.title}
        Mevcut Adım: {current_step.step}
        İçerik: {current_step.content}
        Beklenen Yanıtlar: {', '.join(current_step.expected_responses) if current_step.expected_responses else 'Serbest yanıt'}
        """

    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(system_template),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    ).partial(course_info=course_info)


def initialize_chat(conversation_id: str, chat_history: list, course: Course = None):
    llm = build_llm()
    memory = build_memory(username=conversation_id, history=chat_history)
    prompt = build_prompt(course)

    tools = []  # Gerekirse araçlar burada tanımlanabilir

    agent = create_tool_calling_agent(llm=llm, prompt=prompt, tools=tools)

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        return_intermediate_steps=True,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=1,  # Sonsuz döngüyü engellemek için
    )

    return agent_executor
