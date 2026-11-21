import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/api_client.dart';
import 'core/app_locale.dart';
import 'features/auth/auth_repository.dart';
import 'features/auth/login_page.dart';
import 'features/employees/employees_page.dart';
import 'features/employees/employee_repository.dart';
import 'features/platform/platform_login_page.dart';
import 'features/platform/platform_dashboard_page.dart';
import 'features/platform/platform_repository.dart';
import 'features/organization/users_repository.dart';

const String _configuredApiUrl = String.fromEnvironment(
  'HRM_API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

void main() => runApp(const HrmApp());

class HrmApp extends StatefulWidget {
  const HrmApp({super.key});

  @override
  State<HrmApp> createState() => _HrmAppState();
}

class _HrmAppState extends State<HrmApp> {
  late final ApiClient _api = ApiClient(baseUrl: _configuredApiUrl);
  UserSession? _session;
  PlatformSession? _platformSession;
  bool _platformLogin = false;
  Locale? _preferredLocale;

  void _signOut() {
    final existing = _session;
    if (existing == null) return;
    setState(() => _session = null);
    AuthRepository(_api).signOut(existing).catchError((Object _) {
      // Local logout is guaranteed even when the server cannot be reached.
    });
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'HRM Core',
      debugShowCheckedModeBanner: false,
      locale: _preferredLocale,
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (context, child) => AppLanguageActions(
        setLocale: (locale) => setState(() => _preferredLocale = locale),
        child: child ?? const SizedBox.shrink(),
      ),
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2853A5)),
        scaffoldBackgroundColor: const Color(0xFFF7F9FC),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        ),
      ),
      home: _platformSession != null
          ? PlatformDashboardPage(
              repository: PlatformRepository(_api, _platformSession!),
              onLogout: () => setState(() {
                _platformSession = null;
                _platformLogin = false;
              }),
            )
          : _platformLogin
              ? PlatformLoginPage(
                  repository: PlatformAuthRepository(_api),
                  onLoggedIn: (session) => setState(() => _platformSession = session),
                  onBack: () => setState(() => _platformLogin = false),
                )
              : _session == null
                  ? LoginPage(
                      auth: AuthRepository(_api),
                      onLoggedIn: (session) => setState(() => _session = session),
                      onPlatformRequested: () => setState(() => _platformLogin = true),
                    )
                  : EmployeesPage(
                      repository: EmployeeRepository(api: _api, session: _session!),
                      usersRepository: CompanyUsersRepository(api: _api, session: _session!),
                      session: _session!,
                      onLogout: _signOut,
                    ),
    );
  }
}
