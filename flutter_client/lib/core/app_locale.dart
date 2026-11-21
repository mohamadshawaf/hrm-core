import 'package:flutter/material.dart';

/// A small local catalog for the first bilingual product workflows.
/// Untranslated keys intentionally stay in English until the full ARB pass.
class AppText {
  AppText._();

  static const Map<String, String> _arabic = {
    'Sign in to your organization': 'تسجيل الدخول إلى شركتك',
    'Organization code': 'رمز الشركة',
    'Enter your organization code': 'أدخل رمز الشركة',
    'Email': 'البريد الإلكتروني',
    'Enter a valid email': 'أدخل بريدًا إلكترونيًا صحيحًا',
    'Password': 'كلمة المرور',
    'Show password': 'إظهار كلمة المرور',
    'Hide password': 'إخفاء كلمة المرور',
    'Enter your password': 'أدخل كلمة المرور',
    'Sign in': 'تسجيل الدخول',
    'Forgot password?': 'هل نسيت كلمة المرور؟',
    'Accept a company invitation': 'قبول دعوة شركة',
    'Create a company account': 'إنشاء حساب شركة',
    'Verify a pending company': 'التحقق من شركة قيد التفعيل',
    'Platform administration': 'إدارة المنصة',
    'Change language': 'تغيير اللغة',
    'Employee Management': 'إدارة الموظفين',
    'Company users': 'حسابات الشركة',
    'Signed-in devices': 'الأجهزة المسجلة',
    'Refresh': 'تحديث',
    'Sign out': 'تسجيل الخروج',
    'More actions': 'إجراءات أخرى',
    'Edit': 'تعديل',
    'Archive employee': 'أرشفة الموظف',
    'Add Employee': 'إضافة موظف',
    'Search by name or employee code': 'البحث بالاسم أو الرقم الوظيفي',
    'No matching employees.': 'لا توجد سجلات مطابقة.',
    'Retry': 'إعادة المحاولة',
    'Load more': 'عرض المزيد',
    'Active': 'نشط',
    'Inactive': 'غير نشط',
    'Cancel': 'إلغاء',
    'Archive': 'أرشفة',
    'Archive employee?': 'هل تريد أرشفة الموظف؟',
    'Employee added.': 'تمت إضافة الموظف.',
    'Employee updated.': 'تم تحديث بيانات الموظف.',
    'Employee archived.': 'تمت أرشفة الموظف.',
    'Unable to load employees.': 'تعذر تحميل الموظفين.',
    'Request failed. Please retry.': 'تعذر تنفيذ الطلب. حاول مرة أخرى.',
    'Unexpected response. Try again.': 'حدث خطأ غير متوقع. حاول مرة أخرى.',
    'Edit employee': 'تعديل موظف',
    'Add employee': 'إضافة موظف',
    'Employee code': 'الرقم الوظيفي',
    'Full name': 'الاسم الكامل',
    'Job title': 'المسمى الوظيفي',
    'Department': 'القسم',
    'Email (optional)': 'البريد الإلكتروني (اختياري)',
    'Phone (optional)': 'رقم الهاتف (اختياري)',
    'Status': 'الحالة',
    'Save': 'حفظ',
    'Add': 'إضافة',
    'Enter at least 2 characters': 'أدخل حرفين على الأقل',
    'Use 2-30 letters, numbers, underscores or hyphens':
        'استخدم 2–30 حرفًا أو رقمًا أو شرطة أو شرطة سفلية',
    'Employees': 'الموظفون',
    'Company workspace': 'مساحة عمل الشركة',
    'Secure HR operations across your teams': 'عمليات موارد بشرية منظمة وآمنة لفرق عملك',
    'Manage records, roles and devices from one workspace.':
        'إدارة السجلات والصلاحيات والأجهزة من مساحة عمل واحدة.',
    'Demo records only': 'بيانات تجريبية فقط',
    'Platform owner sign in': 'تسجيل دخول مالك المنصة',
    'This account is separate from company accounts.':
        'هذا الحساب مستقل عن حسابات الشركات.',
    'Platform owner email': 'البريد الإلكتروني لمالك المنصة',
    'Sign in as platform owner': 'دخول مالك المنصة',
    'Back to company sign in': 'العودة إلى دخول الشركات',
    'Unable to sign in. Try again.': 'تعذر تسجيل الدخول. حاول مرة أخرى.',
    'Overview': 'الملخص',
    'Companies': 'الشركات',
    'Plans': 'الباقات',
    'Platform overview': 'ملخص المنصة',
    'Pending verification': 'بانتظار التحقق',
    'Suspended': 'موقوفة',
    'Employee records': 'سجلات الموظفين',
    'Company management': 'إدارة الشركات',
    'Find a company by name or code': 'البحث عن شركة بالاسم أو الرمز',
    'Search': 'بحث',
    'No companies match this search.': 'لا توجد شركات مطابقة.',
    'Reactivate': 'إعادة التفعيل',
    'Suspend': 'إيقاف',
    'Manage plan': 'إدارة الباقة',
    'Subscription plans': 'باقات الاشتراك',
    'New plan': 'باقة جديدة',
    'Try again': 'حاول مرة أخرى',
    'Account active': 'الحساب نشط',
    'Invite user': 'دعوة مستخدم',
    'Recent invitations': 'الدعوات الأخيرة',
    'No invitations yet.': 'لا توجد دعوات بعد.',
    'HR manager': 'مدير الموارد البشرية',
    'Read-only viewer': 'مشاهد للقراءة فقط',
    'Role': 'الصلاحية',
    'Invite a colleague': 'دعوة زميل',
    'Send invitation': 'إرسال الدعوة',
    'Update company user': 'تحديث حساب الشركة',
    'Save changes': 'حفظ التغييرات',
    'Edit user': 'تعديل مستخدم',
    'Disabled': 'معطل',
    'Previous page': 'الصفحة السابقة',
    'Next page': 'الصفحة التالية',
    'We will email a one-time invitation. The invited person chooses their own password.':
        'سنرسل دعوة تستخدم مرة واحدة؛ يختار المدعو كلمة مروره بنفسه.',
    'The company owner account is protected. Invite HR managers or read-only viewers by email.':
        'حساب مالك الشركة محمي؛ يمكنك دعوة مسؤولي الموارد البشرية أو حسابات القراءة فقط.',
    'Accepted': 'مقبولة',
    'Pending': 'معلقة',
    'Expired or replaced': 'منتهية أو مستبدلة',
    'Company registration': 'تسجيل شركة جديدة',
    'Your organization is active': 'تم تفعيل شركتك',
    'Verify your email': 'التحقق من البريد الإلكتروني',
    'Set up your organization': 'إعداد شركتك',
    'Sign in with your organization code, email and password.':
        'سجّل الدخول برمز الشركة والبريد الإلكتروني وكلمة المرور.',
    'Enter your company details and the code from your email.':
        'أدخل بيانات الشركة والرمز المرسل إلى بريدك الإلكتروني.',
    'Create a dedicated workspace for your company.':
        'أنشئ مساحة عمل مستقلة لشركتك.',
    'Go to sign in': 'انتقل إلى تسجيل الدخول',
    'Owner email': 'بريد مالك الشركة',
    'Enter the owner email': 'أدخل بريد مالك الشركة',
    'Email verification code': 'رمز التحقق من البريد',
    'Enter the full code from your email': 'أدخل رمز التحقق الكامل',
    'Verify email and activate': 'تحقق من البريد وفعّل الشركة',
    'Resend verification code': 'إعادة إرسال رمز التحقق',
    'Company name': 'اسم الشركة',
    'Enter a company name': 'أدخل اسم الشركة',
    '2–40 lowercase letters, numbers, - or _':
        'من 2 إلى 40 حرفًا لاتينيًا صغيرًا أو رقمًا أو شرطة',
    'Choose a valid organization code': 'اختر رمزًا صحيحًا للشركة',
    'Enter a valid email address': 'أدخل بريدًا إلكترونيًا صحيحًا',
    'Password (at least 12 characters)': 'كلمة المرور (12 حرفًا على الأقل)',
    'Confirm password': 'تأكيد كلمة المرور',
    'Use at least 12 characters': 'استخدم 12 حرفًا على الأقل',
    'Passwords do not match': 'كلمتا المرور غير متطابقتين',
    'Create company account': 'إنشاء حساب الشركة',
    'Back to sign in': 'العودة إلى تسجيل الدخول',
    'Could not complete registration. Try again.':
        'تعذر إكمال التسجيل. حاول مرة أخرى.',
    'Verification failed. Try again.': 'فشل التحقق. حاول مرة أخرى.',
    'Enter a valid organization code and email first.':
        'أدخل رمز الشركة والبريد الإلكتروني بصورة صحيحة أولًا.',
    'If eligible, a new code will arrive. Wait at least 60 seconds between requests.':
        'إذا كانت البيانات مؤهلة فسيُرسل رمز جديد. انتظر 60 ثانية بين الطلبات.',
    'Could not request a new code. Try again.':
        'تعذر طلب رمز جديد. حاول مرة أخرى.',
    'Accept company invitation': 'قبول دعوة الشركة',
    'Enter the one-time code delivered by your company. Invitations expire after 48 hours.':
        'أدخل رمز الدعوة أحادي الاستخدام. تنتهي الدعوة بعد 48 ساعة.',
    'Invitation code': 'رمز الدعوة',
    'Enter the complete invitation code': 'أدخل رمز الدعوة كاملًا',
    'Create password (12+ characters)': 'إنشاء كلمة مرور (12 حرفًا فأكثر)',
    'Activate my account': 'تفعيل حسابي',
    'Account activated. Sign in with your company code.':
        'تم تفعيل الحساب. سجّل الدخول باستخدام رمز الشركة.',
    'Could not accept the invitation.': 'تعذر قبول الدعوة.',
    'Reset password': 'إعادة تعيين كلمة المرور',
    'Enter your company code and account email.':
        'أدخل رمز الشركة والبريد الإلكتروني لحسابك.',
    'Company code': 'رمز الشركة',
    'Enter the company code': 'أدخل رمز الشركة',
    'Recovery code': 'رمز الاسترداد',
    'Enter the complete recovery code': 'أدخل رمز الاسترداد كاملًا',
    'New password (12+ characters)': 'كلمة مرور جديدة (12 حرفًا فأكثر)',
    'Confirm new password': 'تأكيد كلمة المرور الجديدة',
    'Request recovery code': 'طلب رمز الاسترداد',
    'Set new password': 'تعيين كلمة المرور الجديدة',
    'Password updated. Sign in again.':
        'تم تحديث كلمة المرور. سجّل الدخول مجددًا.',
    'Request could not be completed.': 'تعذر إكمال الطلب.',
    'If your account exists, a recovery code will be sent. Check your email. Codes expire in 30 minutes.':
        'إذا كان الحساب موجودًا فسيُرسل رمز الاسترداد. تفقد بريدك؛ تنتهي صلاحية الرمز بعد 30 دقيقة.',
    'Review sessions associated with your account. Revoking a session immediately invalidates its access and refresh tokens.':
        'راجع الأجهزة المرتبطة بحسابك. إبطال الجلسة يلغي رموز الدخول والتجديد مباشرة.',
    'Unknown device': 'جهاز غير معروف',
    'Current': 'الحالي',
    'Expired or revoked': 'منتهي أو مُلغى',
    'Revoke': 'إبطال',
    'Sign out on every device': 'تسجيل الخروج من جميع الأجهزة',
    'Unable to load sessions.': 'تعذر تحميل الأجهزة.',
    'Could not revoke session.': 'تعذر إبطال الجلسة.',
    'Could not revoke sessions.': 'تعذر إبطال الجلسات.',
  };

  static String of(BuildContext context, String english) =>
      Localizations.localeOf(context).languageCode == 'ar'
          ? (_arabic[english] ?? english)
          : english;

  static String employeesCount(BuildContext context, int loaded, int total) =>
      Localizations.localeOf(context).languageCode == 'ar'
          ? 'عرض $loaded من أصل $total موظف'
          : '$loaded of $total employees';

  static String archivePrompt(BuildContext context, String name) =>
      Localizations.localeOf(context).languageCode == 'ar'
          ? 'هل تريد إخفاء سجل $name من قائمة الموظفين النشطين؟'
          : 'Archive $name? The record will be hidden from active lists.';

  static String hireDate(BuildContext context, String isoDate) =>
      Localizations.localeOf(context).languageCode == 'ar'
          ? 'تاريخ التعيين: $isoDate'
          : 'Hire date: $isoDate';

  static String emailVerificationPrompt(BuildContext context, String email) =>
      Localizations.localeOf(context).languageCode == 'ar'
          ? 'أدخل رمز التحقق أحادي الاستخدام المرسل إلى $email.'
          : 'Enter the one-time code sent to $email.';
}

/// Scope is inserted inside MaterialApp so any page can change the locale.
class AppLanguageActions extends InheritedWidget {
  const AppLanguageActions({
    super.key,
    required super.child,
    required this.setLocale,
  });

  final ValueChanged<Locale> setLocale;

  static AppLanguageActions of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppLanguageActions>()!;

  @override
  bool updateShouldNotify(AppLanguageActions oldWidget) =>
      setLocale != oldWidget.setLocale;
}

class LanguageSwitcher extends StatelessWidget {
  const LanguageSwitcher({super.key});

  @override
  Widget build(BuildContext context) => PopupMenuButton<String>(
        tooltip: AppText.of(context, 'Change language'),
        icon: const Icon(Icons.language_outlined),
        onSelected: (code) => AppLanguageActions.of(context).setLocale(Locale(code)),
        itemBuilder: (context) => const [
          PopupMenuItem(value: 'ar', child: Text('العربية')),
          PopupMenuItem(value: 'en', child: Text('English')),
        ],
      );
}
