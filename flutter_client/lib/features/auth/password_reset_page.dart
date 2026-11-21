import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'auth_repository.dart';

class PasswordResetPage extends StatefulWidget {
  const PasswordResetPage({super.key, required this.auth});

  final AuthRepository auth;

  @override
  State<PasswordResetPage> createState() => _PasswordResetPageState();
}

class _PasswordResetPageState extends State<PasswordResetPage> {
  final _formKey = GlobalKey<FormState>();
  final _company = TextEditingController();
  final _email = TextEditingController();
  final _token = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _codeRequested = false;
  bool _waiting = false;
  String? _message;
  String? _error;

  @override
  void dispose() {
    for (final controller in [_company, _email, _token, _password, _confirm]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _waiting) return;
    setState(() {
      _waiting = true;
      _error = null;
      _message = null;
    });
    try {
      if (!_codeRequested) {
        await widget.auth.requestPasswordReset(
            companyCode: _company.text, email: _email.text);
        if (mounted) {
          setState(() {
            _codeRequested = true;
            _message = AppText.of(context,
                'If your account exists, a recovery code will be sent. Check your email. Codes expire in 30 minutes.');
          });
        }
      } else {
        await widget.auth.confirmPasswordReset(
            token: _token.text, newPassword: _password.text);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content:
              Text(AppText.of(context, 'Password updated. Sign in again.')),
        ));
        Navigator.of(context).pop();
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() =>
            _error = AppText.of(context, 'Request could not be completed.'));
      }
    } finally {
      if (mounted) setState(() => _waiting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(AppText.of(context, 'Reset password')),
            actions: const [LanguageSwitcher()]),
        body: SafeArea(
            child: Center(
                child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (!_codeRequested) ...[
                        Text(AppText.of(context,
                            'Enter your company code and account email.')),
                        const SizedBox(height: 16),
                        TextFormField(
                            controller: _company,
                            decoration: InputDecoration(
                                labelText: AppText.of(context, 'Company code')),
                            validator: (value) => value == null ||
                                    value.trim().length < 2
                                ? AppText.of(context, 'Enter the company code')
                                : null),
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _email,
                            keyboardType: TextInputType.emailAddress,
                            decoration: InputDecoration(
                                labelText: AppText.of(context, 'Email')),
                            validator: (value) =>
                                value == null || !value.contains('@')
                                    ? AppText.of(context, 'Enter a valid email')
                                    : null),
                      ] else ...[
                        TextFormField(
                            controller: _token,
                            decoration: InputDecoration(
                                labelText:
                                    AppText.of(context, 'Recovery code')),
                            validator: (value) => value == null ||
                                    value.trim().length < 32
                                ? AppText.of(
                                    context, 'Enter the complete recovery code')
                                : null),
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _password,
                            obscureText: true,
                            decoration: InputDecoration(
                                labelText: AppText.of(
                                    context, 'New password (12+ characters)')),
                            validator: (value) =>
                                value == null || value.length < 12
                                    ? AppText.of(
                                        context, 'Use at least 12 characters')
                                    : null),
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _confirm,
                            obscureText: true,
                            decoration: InputDecoration(
                                labelText: AppText.of(
                                    context, 'Confirm new password')),
                            validator: (value) => value != _password.text
                                ? AppText.of(context, 'Passwords do not match')
                                : null),
                      ],
                      if (_message != null)
                        Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(_message!)),
                      if (_error != null)
                        Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(_error!,
                                style: TextStyle(
                                    color:
                                        Theme.of(context).colorScheme.error))),
                      const SizedBox(height: 20),
                      FilledButton(
                          onPressed: _waiting ? null : _submit,
                          child: _waiting
                              ? const CircularProgressIndicator()
                              : Text(AppText.of(
                                  context,
                                  _codeRequested
                                      ? 'Set new password'
                                      : 'Request recovery code'))),
                    ],
                  ))),
        ))),
      );
}
