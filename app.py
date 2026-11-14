import os
import shutil
import uuid
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import database
import ocr_engine
import google_sheets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="نظام مزامنة الفروع وقراءة المستندات الموحد")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
templates = Jinja2Templates(directory=[TEMPLATES_DIR, BASE_DIR])

class SaveRecordRequest(BaseModel):
    branch_name: str
    employee_name: Optional[str] = ""
    doc_type: str
    unique_id: str
    title_or_name: Optional[str] = ""
    secondary_data: Optional[str] = ""
    all_details: Optional[str] = ""
    image_filename: Optional[str] = ""
    is_duplicate: bool = False
    duplicate_note: Optional[str] = ""

class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = ""
    google_webhook_url: Optional[str] = ""
    branches_list: Optional[str] = ""

@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def index_page(request: Request):
    branches_raw = database.get_setting("branches_list", "فرع القاهرة الرئيسي,فرع الإسكندرية,فرع الجيزة,فرع طنطا,فرع المنصورة,فرع أسيوط")
    branches = [b.strip() for b in branches_raw.split(",") if b.strip()]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "branches": branches
    })

@app.post("/api/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    branch_name: str = Form(...),
    employee_name: str = Form("")
):
    """
    تحليل الصورة وفحص وجود تكرار مسبق
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="الملف المرفوع يجب أن يكون صورة")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if not file_ext:
        file_ext = ".jpg"
    unique_filename = f"{uuid.uuid4().hex[:12]}{file_ext}"
    saved_path = os.path.join(UPLOADS_DIR, unique_filename)

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # استخراج البيانات عبر الذكاء الاصطناعي
    extracted = ocr_engine.extract_data_from_image(saved_path)
    
    unique_id = extracted.get("unique_id", "").strip()
    doc_type = extracted.get("doc_type", "غير محدد")
    
    # فحص التكرار في قاعدة البيانات الموحدة
    duplicate_info = None
    if unique_id:
        duplicate_info = database.check_duplicate(unique_id, doc_type)

    return JSONResponse({
        "success": True,
        "image_filename": unique_filename,
        "image_url": f"/uploads/{unique_filename}",
        "extracted": extracted,
        "is_duplicate": duplicate_info is not None,
        "duplicate_info": duplicate_info
    })

@app.post("/api/save")
async def save_record(payload: SaveRecordRequest):
    """
    حفظ البيانات نهائياً في قاعدة البيانات المركزية ومزامنتها مع Google Sheets
    """
    record_id = database.add_record(
        branch_name=payload.branch_name,
        employee_name=payload.employee_name,
        doc_type=payload.doc_type,
        unique_id=payload.unique_id,
        title_or_name=payload.title_or_name,
        secondary_data=payload.secondary_data,
        all_details=payload.all_details,
        image_path=payload.image_filename,
        is_duplicate=payload.is_duplicate,
        duplicate_note=payload.duplicate_note
    )

    # جلب السجل الكامل للمزامنة
    records = database.get_records(limit=1)
    if records and records[0]["id"] == record_id:
        new_record = records[0]
        # مزامنة سحابية مع Google Sheets
        synced = google_sheets.sync_to_google_sheet(new_record)
    else:
        synced = False

    return JSONResponse({
        "success": True,
        "record_id": record_id,
        "google_synced": synced,
        "message": "تم حفظ العملية بنجاح وتحديث الشيت"
    })

@app.get("/api/records")
async def list_records(branch: Optional[str] = None, limit: int = 100):
    records = database.get_records(limit=limit, branch=branch)
    return JSONResponse({
        "success": True,
        "records": records
    })

@app.get("/api/export-excel")
async def export_excel():
    """
    تنزيل شيت إكسيل مجمع لكل الفروع لحظياً
    """
    excel_bytes = google_sheets.export_to_excel_bytes()
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=all_branches_records.xlsx"}
    )

@app.get("/api/settings")
async def get_settings():
    return JSONResponse({
        "gemini_api_key": database.get_setting("gemini_api_key", ""),
        "google_webhook_url": database.get_setting("google_webhook_url", ""),
        "branches_list": database.get_setting("branches_list", "فرع القاهرة الرئيسي,فرع الإسكندرية,فرع الجيزة,فرع طنطا,فرع المنصورة,فرع أسيوط")
    })

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    if settings.gemini_api_key is not None:
        database.set_setting("gemini_api_key", settings.gemini_api_key.strip())
    if settings.google_webhook_url is not None:
        database.set_setting("google_webhook_url", settings.google_webhook_url.strip())
    if settings.branches_list is not None:
        database.set_setting("branches_list", settings.branches_list.strip())
    return JSONResponse({"success": True, "message": "تم حفظ الإعدادات بنجاح"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
