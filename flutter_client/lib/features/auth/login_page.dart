import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'auth_repository.dart';
import 'accept_invitation_page.dart';
import 'password_reset_page.dart';
import 'register_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({
    super.key,
    required this.auth,
    required this.onLoggedIn,
    required this.onPlatformRequested,
  });

  final AuthRepository auth;
  final ValueChanged<UserSession> onLoggedIn;
  final VoidCallback onPlatformRequested;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _organization = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _waiting = false;
  bool _obscure = true;
  String? _error;

  @override
  void dispose() {
    _organization.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _waiting) return;
    setState(() {
      _waiting = true;
      _error = null;
    });
    try {
      final session = await widget.auth.signIn(
        organizationCode: _organization.text,
        email: _email.text,
        password: _password.text,
      );
      if (!mounted) return;
      widget.onLoggedIn(session);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = AppText.of(context, 'Unexpected response. Try again.'));
    } finally {
      if (mounted) setState(() => _waiting = false);
    }
  }

  Widget _wideBanner(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.all(24),
      child: DecoratedBox(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: const LinearGradient(
            begin: Alignment.topRight,
            end: Alignment.bottomLeft,
            colors: [Color(0xFF12346B), Color(0xFF3268C5)],
          ),
        ),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(48),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.hub_outlined, color: Colors.white, size: 54),
                const SizedBox(height: 24),
                Text(AppText.of(context, 'Company workspace'),
                  style: theme.textTheme.headlineMedium?.copyWith(
                    color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                Text(AppText.of(context, 'Secure HR operations across your teams'),
                  style: theme.textTheme.titleLarge?.copyWith(color: Colors.white)),
                const SizedBox(height: 18),
                Text(AppText.of(context,
                    'Manage records, roles and devices from one workspace.'),
                  style: const TextStyle(color: Color(0xFFE3EBFF), height: 1.6)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) => SafeArea(
          child: Row(children: [
            if (constraints.maxWidth >= 960)
              Expanded(child: _wideBanner(context)),
          Expanded(child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 500),
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: Card(
                elevation: 2,
                clipBehavior: Clip.antiAlias,
                child: Padding(
                  padding: EdgeInsets.all(constraints.maxWidth < 380 ? 16 : 28),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Align(alignment: AlignmentDirectional.centerEnd,
                          child: LanguageSwitcher()),
                        Icon(Icons.groups_rounded, size: 48,
                            color: Theme.of(context).colorScheme.primary),
                        const SizedBox(height: 16),
                        Text('HRM Core',
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.headlineMedium),
                        const SizedBox(height: 4),
                        Text(AppText.of(context, 'Sign in to your organization'),
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodyMedium),
                        const SizedBox(height: 28),
                        TextFormField(
                          controller: _organization,
                          decoration: InputDecoration(labelText: AppText.of(context, 'Organization code')),
                          autofillHints: const [AutofillHints.organizationName],
                          textInputAction: TextInputAction.next,
                          validator: (value) => value == null || value.trim().length < 2
                              ? AppText.of(context, 'Enter your organization code') : null,
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _email,
                          decoration: InputDecoration(labelText: AppText.of(context, 'Email')),
                          keyboardType: TextInputType.emailAddress,
                          autofillHints: const [AutofillHints.email],
                          textInputAction: TextInputAction.next,
                          validator: (value) => value == null || !value.contains('@')
                              ? AppText.of(context, 'Enter a valid email') : null,
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _password,
                          decoration: InputDecoration(
                            labelText: AppText.of(context, 'Password'),
                            suffixIcon: IconButton(
                              tooltip: AppText.of(context,
                                  _obscure ? 'Show password' : 'Hide password'),
                              icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                              onPressed: () => setState(() => _obscure = !_obscure),
                            ),
                          ),
                          obscureText: _obscure,
                          autofillHints: const [AutofillHints.password],
                          onFieldSubmitted: (_) => _submit(),
                          validator: (value) => value == null || value.isEmpty
                              ? AppText.of(context, 'Enter your password') : null,
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 12),
                          Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                        ],
                        const SizedBox(height: 24),
                        FilledButton(
                          onPressed: _waiting ? null : _submit,
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 13),
                            child: _waiting
                                ? const SizedBox(width: 20, height: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2))
                                : Text(AppText.of(context, 'Sign in')),
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed: _waiting ? null : () => Navigator.of(context).push<void>(
                            MaterialPageRoute(builder: (_) =>
                              PasswordResetPage(auth: widget.auth)),
                          ),
                          child: Text(AppText.of(context, 'Forgot password?')),
                        ),
                        TextButton(
                          onPressed: _waiting ? null : () => Navigator.of(context).push<void>(
                            MaterialPageRoute(builder: (_) =>
                              AcceptInvitationPage(auth: widget.auth)),
                          ),
                          child: Text(AppText.of(context, 'Accept a company invitation')),
                        ),
                        TextButton(
                          onPressed: _waiting ? null : () async {
                            await Navigator.of(context).push<void>(
                              MaterialPageRoute(
                                builder: (_) => RegisterOrganizationPage(auth: widget.auth),
                              ),
                            );
                          },
                          child: Text(AppText.of(context, 'Create a company account')),
                        ),
                        TextButton(
                          onPressed: _waiting ? null : () async {
                            await Navigator.of(context).push<void>(
                              MaterialPageRoute(
                                builder: (_) => RegisterOrganizationPage(
                                  auth: widget.auth,
                                  startInVerification: true,
                                ),
                              ),
                            );
                          },
                          child: Text(AppText.of(context, 'Verify a pending company')),
                        ),
                        const Divider(height: 20),
                        TextButton.icon(
                          onPressed: _waiting ? null : widget.onPlatformRequested,
                          icon: const Icon(Icons.admin_panel_settings_outlined),
                          label: Text(AppText.of(context, 'Platform administration')),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        )),
      ])),
      ),
    );
  }
}
