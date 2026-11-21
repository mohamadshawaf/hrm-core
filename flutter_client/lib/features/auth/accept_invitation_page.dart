import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'auth_repository.dart';

class AcceptInvitationPage extends StatefulWidget {
  const AcceptInvitationPage({super.key, required this.auth});

  final AuthRepository auth;

  @override
  State<AcceptInvitationPage> createState() => _AcceptInvitationPageState();
}

class _AcceptInvitationPageState extends State<AcceptInvitationPage> {
  final _form = GlobalKey<FormState>();
  final _token = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _token.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _accept() async {
    if (!_form.currentState!.validate() || _submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.auth
          .acceptInvitation(token: _token.text, password: _password.text);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(AppText.of(
            context, 'Account activated. Sign in with your company code.')),
      ));
      Navigator.of(context).pop();
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() =>
            _error = AppText.of(context, 'Could not accept the invitation.'));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(AppText.of(context, 'Accept company invitation')),
            actions: const [LanguageSwitcher()]),
        body: SafeArea(
            child: Center(
                child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Form(
                  key: _form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(AppText.of(context,
                          'Enter the one-time code delivered by your company. Invitations expire after 48 hours.')),
                      const SizedBox(height: 20),
                      TextFormField(
                          controller: _token,
                          decoration: InputDecoration(
                              labelText:
                                  AppText.of(context, 'Invitation code')),
                          validator: (value) => value == null ||
                                  value.trim().length < 32
                              ? AppText.of(
                                  context, 'Enter the complete invitation code')
                              : null),
                      const SizedBox(height: 12),
                      TextFormField(
                          controller: _password,
                          obscureText: true,
                          decoration: InputDecoration(
                              labelText: AppText.of(
                                  context, 'Create password (12+ characters)')),
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
                              labelText:
                                  AppText.of(context, 'Confirm password')),
                          validator: (value) => value != _password.text
                              ? AppText.of(context, 'Passwords do not match')
                              : null),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(_error!,
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.error)),
                      ],
                      const SizedBox(height: 22),
                      FilledButton(
                          onPressed: _submitting ? null : _accept,
                          child: _submitting
                              ? const CircularProgressIndicator()
                              : Text(
                                  AppText.of(context, 'Activate my account'))),
                    ],
                  ))),
        ))),
      );
}
