import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'platform_repository.dart';

class PlatformLoginPage extends StatefulWidget {
  const PlatformLoginPage({super.key, required this.repository,
    required this.onLoggedIn, required this.onBack});

  final PlatformAuthRepository repository;
  final ValueChanged<PlatformSession> onLoggedIn;
  final VoidCallback onBack;

  @override
  State<PlatformLoginPage> createState() => _PlatformLoginPageState();
}

class _PlatformLoginPageState extends State<PlatformLoginPage> {
  final _key = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _waiting = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_waiting || !_key.currentState!.validate()) return;
    setState(() { _waiting = true; _error = null; });
    try {
      final session = await widget.repository.signIn(
        email: _email.text, password: _password.text,
      );
      if (mounted) widget.onLoggedIn(session);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = AppText.of(context, 'Unable to sign in. Try again.'));
    } finally {
      if (mounted) setState(() => _waiting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(AppText.of(context, 'Platform administration')),
        actions: const [LanguageSwitcher()]),
      body: SafeArea(child: Center(child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: SingleChildScrollView(padding: const EdgeInsets.all(20),
          child: Card(elevation: 0, child: Padding(
            padding: const EdgeInsets.all(24),
            child: Form(key: _key, child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.admin_panel_settings_rounded, size: 52,
                    color: Theme.of(context).colorScheme.primary),
                const SizedBox(height: 12),
                Text(AppText.of(context, 'Platform owner sign in'), textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(AppText.of(context, 'This account is separate from company accounts.'),
                    textAlign: TextAlign.center),
                const SizedBox(height: 20),
                TextFormField(controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: InputDecoration(labelText: AppText.of(context, 'Platform owner email')),
                    validator: (value) => value == null || !value.contains('@')
                        ? AppText.of(context, 'Enter a valid email') : null),
                const SizedBox(height: 12),
                TextFormField(controller: _password, obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    onFieldSubmitted: (_) => _submit(),
                    decoration: InputDecoration(labelText: AppText.of(context, 'Password')),
                    validator: (value) => value == null || value.isEmpty
                        ? AppText.of(context, 'Enter your password') : null),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 20),
                FilledButton(onPressed: _waiting ? null : _submit,
                    child: _waiting ? const SizedBox(width: 20, height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                        : Text(AppText.of(context, 'Sign in as platform owner'))),
                TextButton(onPressed: _waiting ? null : widget.onBack,
                    child: Text(AppText.of(context, 'Back to company sign in'))),
              ],
            )),
          )),
        ),
      ))),
    );
  }
}
