import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import '../auth/auth_repository.dart';
import '../auth/sessions_page.dart';
import 'employee.dart';
import 'employee_editor_dialog.dart';
import 'employee_repository.dart';
import '../organization/company_users_page.dart';
import '../organization/users_repository.dart';

class EmployeesPage extends StatefulWidget {
  const EmployeesPage({
    super.key,
    required this.repository,
    required this.usersRepository,
    required this.session,
    required this.onLogout,
  });

  final EmployeeRepository repository;
  final CompanyUsersRepository usersRepository;
  final UserSession session;
  final VoidCallback onLogout;

  @override
  State<EmployeesPage> createState() => _EmployeesPageState();
}

class _EmployeesPageState extends State<EmployeesPage> {
  final _search = TextEditingController();
  Timer? _debounce;
  List<Employee> _employees = const [];
  String? _error;
  int _total = 0;
  int _requestId = 0;
  bool _loading = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  @override
  void dispose() {
    _requestId++;
    _search.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _load({required bool reset}) async {
    if (_loading && !reset) return;
    final requestId = ++_requestId;
    final offset = reset ? 0 : _employees.length;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.repository.list(
        search: _search.text.trim(),
        offset: offset,
      );
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _employees = reset ? result.items : [..._employees, ...result.items];
        _total = result.total;
      });
    } on ApiException catch (error) {
      if (!mounted || requestId != _requestId) return;
      if (error.statusCode == 401) {
        widget.onLogout();
        return;
      }
      setState(() => _error = error.message);
    } catch (_) {
      if (mounted && requestId == _requestId) {
        setState(() => _error = AppText.of(context, 'Unable to load employees.'));
      }
    } finally {
      if (mounted && requestId == _requestId) {
        setState(() => _loading = false);
      }
    }
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => _load(reset: true));
  }

  void _showError(Object error) {
    if (!mounted) return;
    if (error is ApiException && error.statusCode == 401) {
      widget.onLogout();
      return;
    }
    final message = error is ApiException
        ? error.message : AppText.of(context, 'Request failed. Please retry.');
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _edit([Employee? existing]) async {
    if (_saving) return;
    final draft = await showDialog<EmployeeDraft>(
      context: context,
      builder: (context) => EmployeeEditorDialog(initial: existing),
    );
    if (draft == null || !mounted) return;
    setState(() => _saving = true);
    try {
      if (existing == null) {
        await widget.repository.create(draft);
      } else {
        await widget.repository.update(existing, draft);
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppText.of(context,
            existing == null ? 'Employee added.' : 'Employee updated.'))),
      );
      await _load(reset: true);
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _archive(Employee employee) async {
    if (_saving) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(AppText.of(context, 'Archive employee?')),
        content: Text(AppText.archivePrompt(context, employee.fullName)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: Text(AppText.of(context, 'Cancel'))),
          FilledButton(onPressed: () => Navigator.pop(context, true),
              child: Text(AppText.of(context, 'Archive'))),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() => _saving = true);
    try {
      await widget.repository.archive(employee);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppText.of(context, 'Employee archived.'))),
      );
      await _load(reset: true);
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _employeeTile(Employee employee) {
    final editable = widget.session.canEditEmployees;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            CircleAvatar(child: Text(employee.fullName.trim().isEmpty
                ? '?' : employee.fullName.trim().characters.first.toUpperCase())),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(employee.fullName,
                      style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text('${employee.jobTitle}  •  ${employee.department}',
                      maxLines: 2, overflow: TextOverflow.ellipsis),
                  Text(employee.code, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (MediaQuery.sizeOf(context).width > 540)
              Chip(label: Text(AppText.of(context,
                  employee.status == 'active' ? 'Active' : 'Inactive'))),
            if (editable) ...[
              if (MediaQuery.sizeOf(context).width < 600)
                PopupMenuButton<String>(
                  tooltip: AppText.of(context, 'More actions'),
                  enabled: !_saving,
                  onSelected: (value) => value == 'edit'
                      ? _edit(employee) : _archive(employee),
                  itemBuilder: (context) => [
                    PopupMenuItem(value: 'edit', child: Text(AppText.of(context, 'Edit'))),
                    PopupMenuItem(value: 'archive',
                        child: Text(AppText.of(context, 'Archive'))),
                  ],
                )
              else ...[
              IconButton(
                tooltip: '${AppText.of(context, 'Edit')} ${employee.fullName}',
                onPressed: _saving ? null : () => _edit(employee),
                icon: const Icon(Icons.edit_outlined),
              ),
              IconButton(
                tooltip: '${AppText.of(context, 'Archive')} ${employee.fullName}',
                onPressed: _saving ? null : () => _archive(employee),
                icon: const Icon(Icons.archive_outlined),
              ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < 700;
    return Scaffold(
      appBar: AppBar(
        title: Text(AppText.of(context, 'Employee Management')),
        actions: [
          const LanguageSwitcher(),
          if (compact)
            PopupMenuButton<String>(
              tooltip: AppText.of(context, 'More actions'),
              onSelected: (value) {
                switch (value) {
                  case 'users':
                    _openCompanyUsers();
                    return;
                  case 'sessions':
                    _openSessions();
                    return;
                  case 'refresh':
                    _load(reset: true);
                    return;
                  case 'logout':
                    widget.onLogout();
                    return;
                }
              },
              itemBuilder: (context) => [
                if (widget.session.canManageUsers)
                  PopupMenuItem(value: 'users',
                      child: Text(AppText.of(context, 'Company users'))),
                PopupMenuItem(value: 'sessions',
                    child: Text(AppText.of(context, 'Signed-in devices'))),
                PopupMenuItem(value: 'refresh',
                    child: Text(AppText.of(context, 'Refresh'))),
                PopupMenuItem(value: 'logout',
                    child: Text(AppText.of(context, 'Sign out'))),
              ],
            )
          else ...[
          if (widget.session.canManageUsers)
            IconButton(
              tooltip: AppText.of(context, 'Company users'),
              icon: const Icon(Icons.manage_accounts_outlined),
              onPressed: _openCompanyUsers,
            ),
          IconButton(
            tooltip: AppText.of(context, 'Signed-in devices'),
            icon: const Icon(Icons.devices_outlined),
            onPressed: _openSessions,
          ),
          IconButton(
            tooltip: AppText.of(context, 'Refresh'),
            onPressed: () => _load(reset: true),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: AppText.of(context, 'Sign out'),
            onPressed: widget.onLogout,
            icon: const Icon(Icons.logout),
          ),
          ],
        ],
      ),
      floatingActionButton: widget.session.canEditEmployees
          ? FloatingActionButton.extended(
              onPressed: _saving ? null : () => _edit(),
              icon: const Icon(Icons.person_add_alt_1),
              label: Text(AppText.of(context, 'Add Employee')),
            )
          : null,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 960),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextField(
                    controller: _search,
                    onChanged: _onSearchChanged,
                    decoration: InputDecoration(
                      labelText: AppText.of(context, 'Search by name or employee code'),
                      prefixIcon: const Icon(Icons.search),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(AppText.employeesCount(context, _employees.length, _total),
                      style: Theme.of(context).textTheme.bodySmall),
                  if (_loading) const LinearProgressIndicator(),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    TextButton(onPressed: () => _load(reset: true),
                      child: Text(AppText.of(context, 'Retry'))),
                  ],
                  const SizedBox(height: 8),
                  Expanded(
                    child: _employees.isEmpty && !_loading
                        ? Center(child: Text(AppText.of(context, 'No matching employees.')))
                        : ListView.builder(
                            padding: const EdgeInsets.only(bottom: 95),
                            itemCount: _employees.length + (_employees.length < _total ? 1 : 0),
                            itemBuilder: (context, index) {
                              if (index == _employees.length) {
                                return Center(
                                  child: TextButton(
                                    onPressed: _loading ? null : () => _load(reset: false),
                                    child: Text(AppText.of(context, 'Load more')),
                                  ),
                                );
                              }
                              return _employeeTile(_employees[index]);
                            },
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _openCompanyUsers() {
    Navigator.of(context).push<void>(MaterialPageRoute(
      builder: (_) => CompanyUsersPage(
        repository: widget.usersRepository, onLogout: widget.onLogout,
      ),
    ));
  }

  void _openSessions() {
    Navigator.of(context).push<void>(MaterialPageRoute(
      builder: (_) => SessionsPage(
        api: widget.repository.api, session: widget.session,
        onLogout: widget.onLogout,
      ),
    ));
  }
}
