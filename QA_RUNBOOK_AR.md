# دليل التحقق من HRM Core بعد المرحلة السابعة

هذا الدليل لتجربة المشروع ببيانات وهمية فقط. لا يتضمن حسابات عملاء أو بريدًا
حقيقيًا، ولا يعطي موافقة على نشر بيانات الموظفين.

لإنشاء البيانات الوهمية بأمر آمن دون الكتابة فوق ملف موجود، اتبع
[`docs/DEMO_AND_CAPTURE_AR.md`](docs/DEMO_AND_CAPTURE_AR.md). يرجى تشغيل
`python scripts/check_public_artifacts.py` من جذر المشروع قبل رفعه.

## ما يمكن اختباره على Windows 11

1. ثبّت Python 3.12+ وFlutter SDK مع أدوات Android وGit.
2. من مجلد `backend` في PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:HRM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:HRM_PLATFORM_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m unittest discover -s tests -v
python -m app.bootstrap
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

تشغيل `app.bootstrap` يطلب بيانات شركة تجريبية من الطرفية. افتح نافذة طرفية
ثانية لتشغيل الاختبارات أو Flutter. لا تنسخ القيم السرية إلى المستودع.

3. من مجلد `flutter_client`:

```powershell
flutter create --empty --platforms=android,web .
flutter pub get
flutter analyze
flutter test
flutter run -d chrome --dart-define=HRM_API_BASE_URL=http://127.0.0.1:8000
flutter build web --release --dart-define=HRM_API_BASE_URL=https://hrm.example.invalid
flutter build apk --release --dart-define=HRM_API_BASE_URL=https://hrm.example.invalid
```

ضع رابط API الحقيقي الآمن بدل `example.invalid` قبل توزيع أي إصدار.
في Web المحلي اضبط `HRM_CORS_ORIGINS` على عنوان الواجهة الفعلي، وفي محاكي
Android استخدم عنوان المضيف `10.0.2.2` بدل `127.0.0.1`.

## PostgreSQL المؤقت وGitHub Actions

يوجد اختبار PostgreSQL فعلي اختياري في
`backend/tests/test_postgres_live.py`، ويُشغّل فقط عندما تكون هناك قاعدة
مخصصة للاختبار وتُضبط متغيرات `HRM_TEST_POSTGRES_DSN` و
`HRM_PG_TEST_ALLOW_SCHEMA_CREATE=1`. ينشئ الاختبار مخططًا مؤقتًا ويحذفه.

يوفر الملف `.github/workflows/ci.yml` وظيفة تلقائية تنشئ PostgreSQL
مؤقتًا، وتشغّل اختبارات Python وFlutter، وتحاول بناء Android وWeb.
تشغَّل مهمة iOS يدويًا باستخدام `workflow_dispatch` على macOS، بدون توقيع.

**لم يُنفَّذ هذا المسار في بيئة التطوير الحالية بسبب غياب PostgreSQL وFlutter،
ولم يُرفع المشروع إلى مستودع GitHub بعد.** اعتبر جميع نتائج CI مرتقبة حتى
تظهر سجلات تشغيل ناجحة في المستودع الفعلي.

## تجربة طابور البريد المشفر

- في التطوير الافتراضي تُكتب الرموز إلى ملفات محلية محمية ضمن `backend/data`.
- إذا عُيّن `HRM_MAIL_OUTBOX_KEY` بمفتاح عشوائي ثابت من 64 خانة ست عشرية،
  تُحفظ رموز الرسائل مشفرة في نفس معاملة قاعدة البيانات.
- لتجهيز الرسائل المعلقة بعد الحفظ، شغّل `python -m app.mail_worker --max-jobs 50`
  بمتغير المفتاح نفسه. يحتاج الإنتاج إلى SMTP موثوق ومراقبة عامل الإرسال.
- لتنظيف سجلات الرموز المنتهية فقط بعد مراجعة مدة الاحتفاظ، شغّل
  `python -m app.maintenance --confirm`.

## ما يُعتبر نجاحًا للمرحلة السابعة

- جميع وظائف CI خضراء فعلًا، مع أرشيف أدلة تشغيل.
- اختبارات جهاز/متصفح للتسجيل، والدعوة، والاستعادة، وإدارة الموظفين،
  والجلسات، والاشتراك المعلّق، وضعف الاتصال.
- واجهة عربية RTL ودعم الشاشات الصغيرة والمتوسطة والكبيرة، بلا تجاوزات عرض.
- لا توجد بيانات أو مفاتيح أو سجلات محلية في مستودع GitHub.
