import io
import json
import requests
import pandas as pd
from typing import Dict, Any, List
import database

def sync_to_google_sheet(record: Dict[str, Any]) -> bool:
    """
    إرسال بيانات العملية فورياً إلى Google Sheets عبر رابط Webhook (Apps Script)
    """
    webhook_url = database.get_setting("google_webhook_url", "").strip()
    if not webhook_url:
        return False
    
    payload = {
        "id": record.get("id"),
        "branch_name": record.get("branch_name"),
        "employee_name": record.get("employee_name", ""),
        "doc_type": record.get("doc_type"),
        "unique_id": str(record.get("unique_id", "")),
        "title_or_name": record.get("title_or_name", ""),
        "secondary_data": record.get("secondary_data", ""),
        "all_details": record.get("all_details", ""),
        "is_duplicate": "مكرر ⚠️" if record.get("is_duplicate") else "جديد ✅",
        "duplicate_note": record.get("duplicate_note", ""),
        "created_at": record.get("created_at")
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=8)
        if response.status_code in [200, 201, 302]:
            database.mark_synced(record["id"])
            return True
        return False
    except Exception as e:
        print(f"[Google Sync Error]: {e}")
        return False

def export_to_excel_bytes() -> bytes:
    """
    تصدير كافة سجلات الفروع إلى ملف Excel بتنسيق عربي احترافي
    """
    records = database.get_records(limit=10000)
    
    if not records:
        df = pd.DataFrame([{
            "رقم العملية": 1,
            "الفرع": "لا توجد بيانات حالياً",
            "الموظف": "",
            "نوع المستند": "",
            "الرقم الفريد (القومي/السيريال)": "",
            "الاسم / الموديل": "",
            "بيانات إضافية": "",
            "تفاصيل كاملة": "",
            "حالة التكرار": "",
            "ملاحظة التكرار": "",
            "تاريخ ووقت الإدخال": ""
        }])
    else:
        rows = []
        for r in records:
            rows.append({
                "رقم العملية": r["id"],
                "الفرع": r["branch_name"],
                "الموظف": r["employee_name"],
                "نوع المستند": r["doc_type"],
                "الرقم الفريد (القومي/السيريال)": f"'{r['unique_id']}",  # علامة تنصيص لضمان عدم حذف الصفر في أول الرقم
                "الاسم / الموديل": r["title_or_name"],
                "بيانات إضافية": r["secondary_data"],
                "تفاصيل كاملة": r["all_details"],
                "حالة التكرار": "مكرر ⚠️" if r["is_duplicate"] else "جديد ✅",
                "ملاحظة التكرار": r["duplicate_note"],
                "تاريخ ووقت الإدخال": r["created_at"]
            })
        df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="سجلات الفروع الموحدة")
    
    return output.getvalue()
