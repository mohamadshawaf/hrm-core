import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'users_repository.dart';

class CompanyUsersPage extends StatefulWidget {
  const CompanyUsersPage(
      {super.key, required this.repository, required this.onLogout});

  final CompanyUsersRepository repository;
  final VoidCallback onLogout;

  @override
  State<CompanyUsersPage> createState() => _CompanyUsersPageState();
}

class _CompanyUsersPageState extends State<CompanyUsersPage> {
  List<CompanyUser> _users = [];
  List<CompanyInvitation> _invitations = [];
  int _offset = 0;
  int _total = 0;
  int _requestId = 0;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final requestId = ++_requestId;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.repository.list(offset: _offset);
      final invitations = await widget.repository.invitations();
      if (mounted && requestId == _requestId) {
        setState(() {
          _users = result.items;
          _invitations = invitations;
          _total = result.total;
        });
      }
    } on ApiException catch (error) {
      if (!mounted || requestId != _requestId) return;
      if (error.statusCode == 401) {
        Navigator.of(context).pop();
        widget.onLogout();
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (mounted && requestId == _requestId) {
        setState(() => _error = 'Could not load organization users.');
      }
    } finally {
      if (mounted && requestId == _requestId) setState(() => _loading = false);
    }
  }

  Future<void> _inviteUser() async {
    final formKey = GlobalKey<FormState>();
    final email = TextEditingController();
    String role = 'hr';
    final draft = await showDialog<_NewUser>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, updateDialog) => AlertDialog(
          title: Text(AppText.of(context, 'Invite a colleague')),
          content: SizedBox(
              width: 430,
              child: SingleChildScrollView(
                  child: Form(
                      key: formKey,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                              controller: email,
                              keyboardType: TextInputType.emailAddress,
                              decoration: InputDecoration(
                                  labelText: AppText.of(context, 'Email')),
                              validator: (value) => value == null ||
                                      !value.contains('@')
                                  ? AppText.of(context, 'Enter a valid email')
                                  : null),
                          const SizedBox(height: 12),
                          Text(AppText.of(context,
                              'We will email a one-time invitation. The invited person chooses their own password.')),
                          const SizedBox(height: 12),
                          DropdownButtonFormField<String>(
                            initialValue: role,
                            decoration: InputDecoration(
                                labelText: AppText.of(context, 'Role')),
                            items: [
                              DropdownMenuItem(
                                  value: 'hr',
                                  child:
                                      Text(AppText.of(context, 'HR manager'))),
                              DropdownMenuItem(
                                  value: 'viewer',
                                  child: Text(
                                      AppText.of(context, 'Read-only viewer'))),
                            ],
                            onChanged: (value) {
                              if (value != null) {
                                updateDialog(() => role = value);
                              }
                            },
                          ),
                        ],
                      )))),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: Text(AppText.of(context, 'Cancel'))),
            FilledButton(
                onPressed: () {
                  if (!formKey.currentState!.validate()) return;
                  Navigator.pop(dialogContext, _NewUser(email.text, role));
                },
                child: Text(AppText.of(context, 'Send invitation'))),
          ],
        ),
      ),
    );
    email.dispose();
    if (draft == null || !mounted) return;
    setState(() => _saving = true);
    try {
      await widget.repository.invite(email: draft.email, role: draft.role);
      if (mounted) {
        _offset = 0;
        await _refresh();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Invitation sent. Valid for 48 hours.')));
        }
      }
    } on ApiException catch (error) {
      if (mounted) _showError(error.message);
    } catch (_) {
      if (mounted) _showError('Could not send the invitation.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _editUser(CompanyUser user) async {
    String role = user.role;
    bool active = user.isActive;
    final draft = await showDialog<_EditedUser>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, updateDialog) => AlertDialog(
          title: Text(AppText.of(context, 'Update company user')),
          content: SizedBox(
              width: 430,
              child: SingleChildScrollView(
                  child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(user.email),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    initialValue: role,
                    decoration:
                        InputDecoration(labelText: AppText.of(context, 'Role')),
                    items: [
                      DropdownMenuItem(
                          value: 'hr',
                          child: Text(AppText.of(context, 'HR manager'))),
                      DropdownMenuItem(
                          value: 'viewer',
                          child: Text(AppText.of(context, 'Read-only viewer'))),
                    ],
                    onChanged: (value) {
                      if (value != null) updateDialog(() => role = value);
                    },
                  ),
                  SwitchListTile(
                      title: Text(AppText.of(context, 'Account active')),
                      value: active,
                      onChanged: (value) => updateDialog(() => active = value)),
                ],
              ))),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: Text(AppText.of(context, 'Cancel'))),
            FilledButton(
                onPressed: () =>
                    Navigator.pop(dialogContext, _EditedUser(role, active)),
                child: Text(AppText.of(context, 'Save changes'))),
          ],
        ),
      ),
    );
    if (draft == null || !mounted) return;
    setState(() => _saving = true);
    try {
      await widget.repository
          .update(user, role: draft.role, isActive: draft.isActive);
      if (mounted) await _refresh();
    } on ApiException catch (error) {
      if (mounted) _showError(error.message);
    } catch (_) {
      if (mounted) _showError('Could not update this account.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _showError(String message) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar:
            AppBar(title: Text(AppText.of(context, 'Company users')), actions: [
          const LanguageSwitcher(),
          IconButton(
              onPressed: _saving ? null : _refresh,
              icon: const Icon(Icons.refresh),
              tooltip: AppText.of(context, 'Refresh')),
        ]),
        floatingActionButton: _saving
            ? null
            : FloatingActionButton.extended(
                onPressed: _inviteUser,
                label: Text(AppText.of(context, 'Invite user')),
                icon: const Icon(Icons.person_add_alt_1)),
        body: SafeArea(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text(_error!))
                    : ListView(padding: const EdgeInsets.all(16), children: [
                        Text(AppText.of(context,
                            'The company owner account is protected. Invite HR managers or read-only viewers by email.')),
                        const SizedBox(height: 16),
                        ..._users.map((user) => Card(
                                child: ListTile(
                              leading: Icon(user.isActive
                                  ? Icons.person_outline
                                  : Icons.person_off_outlined),
                              title: Text(user.email),
                              subtitle: Text(
                                  '${user.role} · ${AppText.of(context, user.isActive ? 'Active' : 'Disabled')}'),
                              trailing: user.role == 'owner'
                                  ? const Icon(Icons.lock_outline)
                                  : IconButton(
                                      onPressed: _saving
                                          ? null
                                          : () => _editUser(user),
                                      icon: const Icon(Icons.edit_outlined),
                                      tooltip:
                                          AppText.of(context, 'Edit user')),
                            ))),
                        Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              Text(
                                  '${_total == 0 ? 0 : _offset + 1}–${_offset + _users.length} of $_total'),
                              IconButton(
                                tooltip: AppText.of(context, 'Previous page'),
                                onPressed: _saving || _offset == 0
                                    ? null
                                    : () {
                                        _offset -= 20;
                                        _refresh();
                                      },
                                icon: const Icon(Icons.chevron_left),
                              ),
                              IconButton(
                                tooltip: AppText.of(context, 'Next page'),
                                onPressed:
                                    _saving || _offset + _users.length >= _total
                                        ? null
                                        : () {
                                            _offset += 20;
                                            _refresh();
                                          },
                                icon: const Icon(Icons.chevron_right),
                              ),
                            ]),
                        const SizedBox(height: 20),
                        Text(AppText.of(context, 'Recent invitations'),
                            style: Theme.of(context).textTheme.titleLarge),
                        if (_invitations.isEmpty)
                          Padding(
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              child: Text(
                                  AppText.of(context, 'No invitations yet.'))),
                        ..._invitations.map((invite) => Card(
                                child: ListTile(
                              leading: Icon(invite.isPending
                                  ? Icons.mark_email_unread_outlined
                                  : Icons.mark_email_read_outlined),
                              title: Text(invite.email),
                              subtitle: Text(
                                  '${invite.role} · ${AppText.of(context, invite.acceptedAt != null ? 'Accepted' : invite.isPending ? 'Pending' : 'Expired or replaced')}'),
                            ))),
                      ])),
      );
}

class _NewUser {
  const _NewUser(this.email, this.role);
  final String email;
  final String role;
}

class _EditedUser {
  const _EditedUser(this.role, this.isActive);
  final String role;
  final bool isActive;
}
