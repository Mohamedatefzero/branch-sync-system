import base64
import json
import os
import re
import requests
from typing import Dict, Any
import database

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_INSTRUCTION = """
أنت نظام ذكاء اصطناعي متخصص في فحص المستندات واستخراج البيانات بدقة متناهية.
الصور المدخلة تنتمي إلى أحد نوعين رئيسيين:
1. بطاقة رقم قومي / بطاقة شخصية (غالباً مصرية أو عربية).
2. شاشة فك باسورد جهاز تسجيل كاميرات مراقبة (DVR / NVR) تابع لشركة زيروتك (ZeroTech) أو ما يشابهها (مثل شاشات استرجاع الباسورد، شاشة السيريال والكود، QR Code، تاريخ ووقت الجهاز).

المطلوب:
تحليل الصورة المرفقة واستخراج البيانات وإرجاع النتيجة بتنسيق JSON فقط بدون أي نصوص إضافية أو علامات تظليل (pure JSON):
{
  "doc_type": "بطاقة شخصية" أو "فك باسورد زيروتك" أو "أخرى",
  "unique_id": "الرقم القومي (14 رقم بالضبط بدون مسافات) أو الرقم التسلسلي للسيريال (Serial Number / Device SN) في جهاز زيروتك",
  "title_or_name": "اسم صاحب البطاقة ثلاثي/رباعي أو موديل الجهاز ونوعه",
  "secondary_data": "كود فك الباسورد / تاريخ ووقت الجهاز / تاريخ الميلاد",
  "all_details": "ملخص كامل لباقي البيانات المستخرجة (مثل: العنوان، المحافظة، الوظيفة، أو الماك أدريس MAC، رمز الأمان Security Code، رقم النسخة Firmware)",
  "confidence": "عالية" أو "متوسطة" أو "منخفضة"
}

ملاحظات هامة جداً:
- في بطاقة الرقم القومي: تأكد من قراءة الـ 14 رقم بالكامل بدقة.
- في شاشة زيروتك: ركز على حقل Serial No أو SN أو Device Serial والكود الظاهر (مثل Dynamic Password / Super Password / QR info) وتاريخ الجهاز (Device Time).
- إذا كانت الصورة غير واضحة، ضع ما استطعت قراءته وحدد confidence كمنخفضة.
"""

def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def get_mime_type(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".webp":
        return "image/webp"
    return "image/jpeg"

def extract_data_from_image(image_path: str) -> Dict[str, Any]:
    """
    تحليل الصورة عبر الذكاء الاصطناعي واستخراج البيانات المطلوبة
    """
    api_key = database.get_setting("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    if api_key:
        try:
            b64_image = image_to_base64(image_path)
            mime_type = get_mime_type(image_path)
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": SYSTEM_INSTRUCTION},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_image
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }

            url = f"{GEMINI_API_URL}?key={api_key}"
            response = requests.post(url, json=payload, timeout=25)
            
            if response.status_code == 200:
                result = response.json()
                text_content = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                # تنظيف الـ JSON في حال تضمن ```json
                text_content = re.sub(r"^```json\s*", "", text_content)
                text_content = re.sub(r"\s*```$", "", text_content)
                data = json.loads(text_content)
                return data
            else:
                print(f"[Gemini API Error] Status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[Gemini Extraction Exception]: {e}")

    # وضع الاستخراج الذكي التلقائي (في حال لم يتم تفعيل مفتاح الـ API بعد)
    return fallback_local_extraction(image_path)

def fallback_local_extraction(image_path: str) -> Dict[str, Any]:
    """
    محرك احتياطي ذكي للتجربة والاختبار السريع عند عدم توفر مفتاح API
    """
    filename = os.path.basename(image_path).lower()
    
    # فحص ما إذا كان اسم الملف أو الصورة يلمح لنوع معين
    if "zero" in filename or "dvr" in filename or "nvr" in filename or "reset" in filename or "pass" in filename:
        return {
            "doc_type": "فك باسورد زيروتك",
            "unique_id": "SN-ZT88492031",
            "title_or_name": "ZeroTech XVR 8CH H.265",
            "secondary_data": "كود فك مؤقت: 849201 | تاريخ الجهاز: 2026-11-14 18:22",
            "all_details": "تم الاستخراج التجريبي - الرجاء إدخال مفتاح Gemini API في الإعدادات لدقة 100% للصور الحية",
            "confidence": "تجريبي"
        }
    else:
        return {
            "doc_type": "بطاقة شخصية",
            "unique_id": "29801011234567",
            "title_or_name": "أحمد محمد محمود إبراهيم",
            "secondary_data": "تاريخ الميلاد: 01/01/1998 | محافظة القاهرة",
            "all_details": "تم الاستخراج التجريبي - يرجى وضع مفتاح Gemini API في الإعدادات لقراءة البطاقات الحقيقية بدقة",
            "confidence": "تجريبي"
        }
