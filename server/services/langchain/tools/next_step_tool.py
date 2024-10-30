from langchain.tools import tool
from server.database import db
from server.services.course_loader import load_course_content
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
course_collection = db.get_collection("courses")

def next_step_tool_wrapper(user_id: str) -> str:
    @tool("next_step_tool", return_direct=True)
    def next_step_tool(processNextStep: bool) -> str:
        """
        Eğer verilen cevap doğruysa, öğrenciyi sonraki seviyeye geçirir. Eğer yanlışsa, doğru cevabı açıklar ve benzer bir soru sorar.

        Args:
            processNextStep (bool): Sonra ki adıma geçilip geçilmeyeceği bilgisi. True ise sonraki adıma geçilir, False ise doğru cevap açıklanır ve benzer bir soru sorulur.
        """
        if processNextStep:
            try:
                logger.info(f"Kullanıcı {user_id} için adım artırılıyor.")

                # Kullanıcının mevcut kurs durumunu al
                course_state = course_collection.find_one({"user_id": user_id})
                if not course_state:
                    logger.error(f"Kurs durumu bulunamadı: user_id={user_id}")
                    return "Kurs durumu bulunamadı."

                course_id = course_state["course_id"]
                current_section = course_state.get("current_section", 0)
                current_step = course_state.get("current_step", 0)

                # Kurs içeriğini yükle
                course = load_course_content(course_id)
                sections = course.sections

                # Mevcut bölüm ve adım bilgilerini al
                if current_section >= len(sections):
                    logger.warning(f"Kullanıcı {user_id} tüm bölümleri tamamladı.")
                    return "Tebrikler! Tüm kursu tamamladınız."

                current_section_obj = sections[current_section]
                total_steps = len(current_section_obj.steps)

                if current_step + 1 < total_steps:
                    # Aynı bölüm içinde bir sonraki adıma geç
                    new_step = current_step + 1
                    course_collection.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {
                                "current_step": new_step,
                                "updated_at": datetime.utcnow(),
                            }
                        }
                    )
                    logger.info(f"Kullanıcı {user_id} adımı {new_step} olarak güncellendi.")
                    return "Sonraki adıma geçildi."
                else:
                    # Son adım tamamlandığında bir sonraki bölüme geç
                    if current_section + 1 < len(sections):
                        new_section = current_section + 1
                        course_collection.update_one(
                            {"user_id": user_id},
                            {
                                "$set": {
                                    "current_section": new_section,
                                    "current_step": 0,
                                    "updated_at": datetime.utcnow(),
                                }
                            }
                        )
                        logger.info(f"Kullanıcı {user_id} bölümü {new_section} olarak güncellendi.")
                        return "Sonraki bölüme geçildi."
                    else:
                        # Tüm kurs tamamlandı
                        course_collection.update_one(
                            {"user_id": user_id},
                            {
                                "$set": {
                                    "current_section": new_section,
                                    "current_step": 0,
                                    "updated_at": datetime.utcnow(),
                                }
                            }
                        )
                        logger.info(f"Kullanıcı {user_id} tüm kursu tamamladı.")
                        return "Tebrikler! Tüm kursu tamamladınız."
            except Exception as e:
                logger.error(f"Adım artırma sırasında hata oluştu: {str(e)}")
                return "Adım artırma sırasında bir hata oluştu."
        else:
            logger.info(f"Kullanıcı {user_id} yanlış cevap verdi. Doğru cevabı açıklanacak ve benzer bir soru sorulacak.")
            return "Yanlış cevap. Doğru cevabı açıklayacağım ve benzer bir soru soracağım."
    return next_step_tool
