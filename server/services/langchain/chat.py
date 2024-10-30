from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
from server.services.langchain.llms.gemini import build_llm
from server.services.langchain.memories.memory import build_memory
from server.models.course import Course

from server.services.langchain.tools.next_step_tool import next_step_tool_wrapper
from server.services.langchain.tools.magic_function import magic_function

def build_prompt(course: Course = None):
    system_content = """
    Sen bir öğretmensin. Öğrencilere ders içeriğini adım adım öğretmekle görevlisin. Sana kurs içeriğinden bir bölüm verildi. Bu bölümü hiçbir değişiklik yapmadan öğrenciye anlatman gerekiyor.
    
    Görevlerin:
    1. Mevcut bölümü sırayla ve detaylı şekilde anlatmak.
    2. Öğrenciye bölüm ile ilgili bir soru sor.
    3. Sorunun doğruluğunu kontrol et. Eğer cevap doğruysa next_step_tool fonksiyonunu çağırarak öğrenciyi bir sonraki adıma geçir. Eğer cevap yanlışsa doğru cevabı açıkla ve benzer bir soru sor.
    """
    
    if course:
        current_section = course.sections[course.current_section]
        system_content += f"""
        Kurs: {course.title}
        Açıklama: {course.description}
        Toplam Bölüm: {len(course.sections)}
        Mevcut Bölüm: {current_section.title}
        Bölüm İçeriği: {current_section.content}
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
    
    tools = [next_step_tool_wrapper(conversation_id)]
    
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