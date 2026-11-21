import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'auth_repository.dart';

/// Self-service onboarding. Company access remains blocked until the
/// one-time email token is successfully verified by the backend.
class RegisterOrganizationPage extends StatefulWidget {
  const RegisterOrganizationPage({
    super.key,
    required this.auth,
    this.startInVerification = false,
  });

  final AuthRepository auth;
  final bool startInVerification;

  @override
  State<RegisterOrganizationPage> createState() =>
      _RegisterOrganizationPageState();
}

class _RegisterOrganizationPageState extends State<RegisterOrganizationPage> {
  final _registrationKey = GlobalKey<FormState>();
  final _verifyKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _code = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _token = TextEditingController();
  bool _registered = false;
  bool _finished = false;
  bool _busy = false;
  bool _showPassword = false;
  String? _error;
  String? _notice;

  @override
  void initState() {
    super.initState();
    _registered = widget.startInVerification;
  }

  @override
  void dispose() {
    _name.dispose();
    _code.dispose();
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    if (_busy || !_registrationKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.auth.registerOrganization(
        organizationCode: _code.text,
        organizationName: _name.text,
        ownerEmail: _email.text,
        password: _password.text,
      );
      if (!mounted) return;
      _password.clear();
      _confirm.clear();
      setState(() => _registered = true);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error =
            AppText.of(context, 'Could not complete registration. Try again.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verify() async {
    if (_busy || !_verifyKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.auth.verifyOrganizationEmail(_token.text);
      if (!mounted) return;
      _token.clear();
      setState(() => _finished = true);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() =>
            _error = AppText.of(context, 'Verification failed. Try again.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resend() async {
    if (_busy) return;
    if (!RegExp(r'^[a-z0-9_-]{2,40}$')
            .hasMatch(_code.text.trim().toLowerCase()) ||
        !_email.text.contains('@')) {
      setState(() => _error = AppText.of(
          context, 'Enter a valid organization code and email first.'));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    try {
      await widget.auth.resendVerification(
        organizationCode: _code.text,
        ownerEmail: _email.text,
      );
      if (!mounted) return;
      setState(() => _notice = AppText.of(context,
          'If eligible, a new code will arrive. Wait at least 60 seconds between requests.'));
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error =
            AppText.of(context, 'Could not request a new code. Try again.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
          title: Text(AppText.of(context, 'Company registration')),
          actions: const [LanguageSwitcher()]),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Card(
                elevation: 0,
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                          _finished
                              ? Icons.verified_outlined
                              : Icons.business_rounded,
                          size: 48,
                          color: scheme.primary),
                      const SizedBox(height: 12),
                      Text(
                          AppText.of(
                              context,
                              _finished
                                  ? 'Your organization is active'
                                  : _registered
                                      ? widget.startInVerification
                                          ? 'Verify a pending company'
                                          : 'Verify your email'
                                      : 'Set up your organization'),
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 8),
                      Text(
                          _finished
                              ? AppText.of(context,
                                  'Sign in with your organization code, email and password.')
                              : _registered
                                  ? widget.startInVerification
                                      ? AppText.of(context,
                                          'Enter your company details and the code from your email.')
                                      : AppText.emailVerificationPrompt(
                                          context, _email.text.trim())
                                  : AppText.of(context,
                                      'Create a dedicated workspace for your company.'),
                          textAlign: TextAlign.center),
                      const SizedBox(height: 24),
                      if (_finished)
                        FilledButton.icon(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.login),
                          label: Text(AppText.of(context, 'Go to sign in')),
                        )
                      else if (_registered)
                        Form(
                          key: _verifyKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              if (widget.startInVerification) ...[
                                TextFormField(
                                  controller: _code,
                                  decoration: InputDecoration(
                                      labelText: AppText.of(
                                          context, 'Organization code')),
                                  validator: (value) =>
                                      RegExp(r'^[a-z0-9_-]{2,40}$').hasMatch(
                                              value?.trim().toLowerCase() ?? '')
                                          ? null
                                          : AppText.of(context,
                                              'Enter your organization code'),
                                ),
                                const SizedBox(height: 12),
                                TextFormField(
                                  controller: _email,
                                  keyboardType: TextInputType.emailAddress,
                                  decoration: InputDecoration(
                                      labelText:
                                          AppText.of(context, 'Owner email')),
                                  validator: (value) =>
                                      value == null || !value.contains('@')
                                          ? AppText.of(
                                              context, 'Enter the owner email')
                                          : null,
                                ),
                                const SizedBox(height: 12),
                              ],
                              TextFormField(
                                controller: _token,
                                autocorrect: false,
                                enableSuggestions: false,
                                decoration: InputDecoration(
                                    labelText: AppText.of(
                                        context, 'Email verification code')),
                                validator: (value) => value == null ||
                                        value.trim().length < 32
                                    ? AppText.of(context,
                                        'Enter the full code from your email')
                                    : null,
                              ),
                              const SizedBox(height: 18),
                              FilledButton(
                                onPressed: _busy ? null : _verify,
                                child: _busy
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2))
                                    : Text(AppText.of(
                                        context, 'Verify email and activate')),
                              ),
                              TextButton(
                                onPressed: _busy ? null : _resend,
                                child: Text(AppText.of(
                                    context, 'Resend verification code')),
                              ),
                            ],
                          ),
                        )
                      else
                        Form(
                          key: _registrationKey,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              TextFormField(
                                controller: _name,
                                decoration: InputDecoration(
                                    labelText:
                                        AppText.of(context, 'Company name')),
                                textInputAction: TextInputAction.next,
                                validator: (value) =>
                                    value == null || value.trim().length < 2
                                        ? AppText.of(
                                            context, 'Enter a company name')
                                        : null,
                              ),
                              const SizedBox(height: 12),
                              TextFormField(
                                controller: _code,
                                autocorrect: false,
                                decoration: InputDecoration(
                                  labelText:
                                      AppText.of(context, 'Organization code'),
                                  helperText: AppText.of(context,
                                      '2–40 lowercase letters, numbers, - or _'),
                                ),
                                textInputAction: TextInputAction.next,
                                validator: (value) =>
                                    RegExp(r'^[a-z0-9_-]{2,40}$').hasMatch(
                                            value?.trim().toLowerCase() ?? '')
                                        ? null
                                        : AppText.of(context,
                                            'Choose a valid organization code'),
                              ),
                              const SizedBox(height: 12),
                              TextFormField(
                                controller: _email,
                                decoration: InputDecoration(
                                    labelText:
                                        AppText.of(context, 'Owner email')),
                                keyboardType: TextInputType.emailAddress,
                                autofillHints: const [AutofillHints.email],
                                textInputAction: TextInputAction.next,
                                validator: (value) => value == null ||
                                        !value.contains('@')
                                    ? AppText.of(
                                        context, 'Enter a valid email address')
                                    : null,
                              ),
                              const SizedBox(height: 12),
                              TextFormField(
                                controller: _password,
                                obscureText: !_showPassword,
                                autofillHints: const [
                                  AutofillHints.newPassword
                                ],
                                decoration: InputDecoration(
                                  labelText: AppText.of(context,
                                      'Password (at least 12 characters)'),
                                  suffixIcon: IconButton(
                                    tooltip: AppText.of(
                                        context,
                                        _showPassword
                                            ? 'Hide password'
                                            : 'Show password'),
                                    icon: Icon(_showPassword
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined),
                                    onPressed: () => setState(
                                        () => _showPassword = !_showPassword),
                                  ),
                                ),
                                textInputAction: TextInputAction.next,
                                validator: (value) => value == null ||
                                        value.length < 12
                                    ? AppText.of(
                                        context, 'Use at least 12 characters')
                                    : null,
                              ),
                              const SizedBox(height: 12),
                              TextFormField(
                                controller: _confirm,
                                obscureText: !_showPassword,
                                decoration: InputDecoration(
                                    labelText: AppText.of(
                                        context, 'Confirm password')),
                                onFieldSubmitted: (_) => _register(),
                                validator: (value) => value != _password.text
                                    ? AppText.of(
                                        context, 'Passwords do not match')
                                    : null,
                              ),
                              const SizedBox(height: 18),
                              FilledButton(
                                onPressed: _busy ? null : _register,
                                child: _busy
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2))
                                    : Text(AppText.of(
                                        context, 'Create company account')),
                              ),
                            ],
                          ),
                        ),
                      if (_error != null) ...[
                        const SizedBox(height: 14),
                        Text(_error!,
                            textAlign: TextAlign.center,
                            style: TextStyle(color: scheme.error)),
                      ],
                      if (_notice != null) ...[
                        const SizedBox(height: 14),
                        Text(_notice!, textAlign: TextAlign.center),
                      ],
                      if (!_finished) ...[
                        const SizedBox(height: 12),
                        TextButton(
                          onPressed:
                              _busy ? null : () => Navigator.of(context).pop(),
                          child: Text(AppText.of(context, 'Back to sign in')),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
