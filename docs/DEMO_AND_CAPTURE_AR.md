# دليل تجربة وتصوير HRM Core لملف GitHub

**مهم:** يستخدم هذا الدليل بيانات افتراضية فقط.
أو أي قاعدة خاصة بعميل، ولا ترفع ملفات SQLite أو رموز الدخول أو ملفات البريد.

## 1. إنشاء بيانات العرض على Windows 11

افتح PowerShell من مجلد `backend` بعد تثبيت Python والاعتمادات:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
New-Item -ItemType Directory -Force data
python -m app.demo_seed --db-path .\data\demo.sqlite3 --confirm-demo
```

سيطلب الأمر كلمة مرور **خاصة بالعرض** لا تقل عن 12 حرفًا دون عرضها على الشاشة.
ينشئ شركتين خياليتين مستقلتين:

| رمز الشركة   | بريد مالك العرض               | عدد السجلات الوهمية |
| ------------ | ----------------------------- | ------------------: |
| `atlas-demo` | `owner@atlas.example.invalid` |                   8 |
| `cedar-demo` | `owner@cedar.example.invalid` |                  12 |

لا ينشئ الأمر قاعدة فوق ملف موجود. عند إعادة التجربة اختر اسم ملف جديدًا.
تُستخدم عناوين `example.invalid` عمدًا لمنع الخلط بينها وبين عناوين حقيقية.

## 2. تشغيل API محليًا

من النافذة نفسها:

```powershell
$env:HRM_DB_PATH = '.\data\demo.sqlite3'
$env:HRM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:HRM_PLATFORM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:HRM_CORS_ORIGINS = 'http://localhost:52525'
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

ملحوظة: إذا اخترت منفذ Web مختلفًا فغيّر `HRM_CORS_ORIGINS` ليتطابق معه.
لا تستخدم هذه القيم لإعدادات الإنتاج.

## 3. تشغيل تطبيق Flutter

من PowerShell آخر، داخل `flutter_client`:

```powershell
flutter create --empty --platforms=android,ios,web .
flutter pub get
flutter analyze
flutter test
flutter run -d chrome --web-port 52525 --dart-define=HRM_API_BASE_URL=http://127.0.0.1:8000
```

لتجربة Android على المحاكي استخدم:

```powershell
flutter run -d emulator-5554 --dart-define=HRM_API_BASE_URL=http://10.0.2.2:8000
```

المحاكي ورقم الجهاز أمثلة. في iOS يلزم تشغيل Flutter على جهاز Mac مناسب.

## 4. سيناريوهات العرض الواضحة

1. افتح صفحة الدخول واختر **العربية**؛ اختبر اتجاه RTL وعرض الجوال.
2. ادخل عبر `atlas-demo`، وافتح قائمة الموظفين الثمانية؛ ابحث باسم موظف أو رمز.
3. جرّب إضافة موظف وهمي، ثم التعديل والأرشفة؛ راقب استجابة الواجهة.
4. سجّل الخروج وادخل عبر `cedar-demo`؛ تأكد من ظهور 12 سجلًا مختلفًا وعدم
   ظهور أي سجل من الشركة الأولى.
5. غيّر اللغة إلى **English**؛ تحقق من اتجاه LTR، ثم كرر عرض الجوال والويب.
6. جرّب صلاحيات `viewer` من خلال دعوة حساب محلي عند الحاجة، دون إرسال رسائل
   لأشخاص حقيقيين. ميزة `platform_owner` تتطلب حسابًا ينشأ مستقلًا عبر CLI.

## 5. لقطات مطلوبة قبل وضعها في README

| اسم الملف المقترح                             | المحتوى                           | حالة الالتقاط الحالية |
| --------------------------------------------- | --------------------------------- | --------------------- |
| `assets/screenshots/login-ar-mobile.png`      | تسجيل الدخول بالعربية على 390px   | لم يُلتقط بعد         |
| `assets/screenshots/login-en-desktop.png`     | شاشة الدخول الواسعة بالإنجليزية   | لم يُلتقط بعد         |
| `assets/screenshots/employees-ar-web.png`     | سجلات وهمية لشركة Atlas           | لم يُلتقط بعد         |
| `assets/screenshots/employee-form-mobile.png` | نموذج إضافة موظف على الجوال       | لم يُلتقط بعد         |
| `assets/screenshots/platform-overview.png`    | لوحة إدارة المنصة بالحساب المنفصل | لم يُلتقط بعد         |

ضع صورًا **حقيقية من البرنامج بعد تشغيله**، واحذف/أخفِ رموز الدخول وعناوين
IP الحقيقية والأسرار من الصور. لا تستخدم تصميمات مولدة على أنها صور تشغيل.

## 6. اختبارات القبول قبل إعلان الجاهزية

- شغّل GitHub Actions على مستودع فعلي واحتفظ بروابط تشغيل ناجح؛ اختبر iOS يدويًا.
- اختبر Firefox/Chrome/Edge وAndroid وiOS بأحجام خط متعددة مع قارئ الشاشة.
- وثّق زمن استجابة الـAPI ومدة التحميل على أجهزة محددة قبل أي ادعاء أداء.
- افحص المستودع من أسرار وبيانات عميل قبل جعله عامًا.
