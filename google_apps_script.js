/**
 * كود ربط Google Sheets التلقائي بنظام الفروع الموحد
 * 
 * طريقة التركيب في 30 ثانية:
 * 1. افتح شيت جوجل جديد (Google Sheets).
 * 2. من القائمة العلوية اضغط: إضافات (Extensions) -> Apps Script.
 * 3. امسح أي كود موجود والصق هذا الكود بالكامل.
 * 4. اضغط حفظ (أيقونة الديسك)، ثم اضغط زر "نشر" (Deploy) باللون الأزرق -> "نشر جديد" (New deployment).
 * 5. اختر النوع: "Web app" (تطبيق ويب).
 * 6. في خانة "Who has access" (من يملك حق الوصول) اختر: "Anyone" (أي شخص).
 * 7. اضغط Deploy وانسخ الرابط النهائي (Web app URL) وضعه في إعدادات البرنامج!
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);
    
    // إذا كان الشيت فارغاً، نقوم بإنشاء العناوين الرئيسية فورياً وتنسيقها
    if (sheet.getLastRow() === 0) {
      var headers = [
        "رقم العملية",
        "الفرع",
        "الموظف",
        "نوع المستند",
        "الرقم الفريد (القومي/السيريال)",
        "الاسم / الموديل",
        "بيانات إضافية",
        "تفاصيل كاملة",
        "حالة التكرار",
        "ملاحظة التكرار",
        "تاريخ ووقت الإدخال"
      ];
      sheet.appendRow(headers);
      
      // تنسيق شريط العناوين بلون احترافي
      var headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setBackground("#1e293b");
      headerRange.setFontColor("#ffffff");
      headerRange.setFontWeight("bold");
      headerRange.setHorizontalAlignment("center");
      sheet.setFrozenRows(1);
    }
    
    // إضافة الصف الجديد
    var newRow = [
      data.id,
      data.branch_name,
      data.employee_name || "-",
      data.doc_type,
      "'" + String(data.unique_id), // علامة ' لضمان بقاء الرقم القومي كنص كامل
      data.title_or_name || "-",
      data.secondary_data || "-",
      data.all_details || "-",
      data.is_duplicate,
      data.duplicate_note || "-",
      data.created_at
    ];
    
    sheet.appendRow(newRow);
    
    // تلوين الصف باللون الأحمر الفاتح إذا كان مكرراً لسهولة تمييزه
    if (data.is_duplicate.indexOf("مكرر") !== -1) {
      var lastRowIdx = sheet.getLastRow();
      sheet.getRange(lastRowIdx, 1, 1, newRow.length).setBackground("#fee2e2");
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Row added successfully"
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
