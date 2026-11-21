import 'package:flutter/material.dart';

import '../../core/app_locale.dart';
import 'employee.dart';

/// Collects validated form input; persistence is performed by the repository.
class EmployeeEditorDialog extends StatefulWidget {
  const EmployeeEditorDialog({super.key, this.initial});

  final Employee? initial;

  @override
  State<EmployeeEditorDialog> createState() => _EmployeeEditorDialogState();
}

class _EmployeeEditorDialogState extends State<EmployeeEditorDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _code;
  late final TextEditingController _name;
  late final TextEditingController _job;
  late final TextEditingController _department;
  late final TextEditingController _email;
  late final TextEditingController _phone;
  late DateTime _hireDate;
  late String _status;

  @override
  void initState() {
    super.initState();
    _code = TextEditingController(text: widget.initial?.code);
    _name = TextEditingController(text: widget.initial?.fullName);
    _job = TextEditingController(text: widget.initial?.jobTitle);
    _department = TextEditingController(text: widget.initial?.department);
    _email = TextEditingController(text: widget.initial?.email);
    _phone = TextEditingController(text: widget.initial?.phone);
    _hireDate = widget.initial?.hireDate ?? DateTime.now();
    _status = widget.initial?.status ?? 'active';
  }

  @override
  void dispose() {
    for (final controller in [
      _code,
      _name,
      _job,
      _department,
      _email,
      _phone
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  String? _required(String? value) {
    if (value == null || value.trim().length < 2) {
      return AppText.of(context, 'Enter at least 2 characters');
    }
    return null;
  }

  Future<void> _selectDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _hireDate,
      firstDate: DateTime(1990),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) setState(() => _hireDate = selected);
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.of(context).pop(EmployeeDraft(
      code: _code.text.trim(),
      fullName: _name.text.trim(),
      jobTitle: _job.text.trim(),
      department: _department.text.trim(),
      email: _email.text.trim(),
      phone: _phone.text.trim(),
      hireDate: _hireDate,
      status: _status,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final isEditing = widget.initial != null;
    final title =
        AppText.of(context, isEditing ? 'Edit employee' : 'Add employee');
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 540),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(22),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _code,
                  enabled: !isEditing,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Employee code')),
                  validator: (value) => value == null ||
                          !RegExp(r'^[A-Za-z0-9_-]{2,30}$')
                              .hasMatch(value.trim())
                      ? AppText.of(context,
                          'Use 2-30 letters, numbers, underscores or hyphens')
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _name,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Full name')),
                  textCapitalization: TextCapitalization.words,
                  validator: _required,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _job,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Job title')),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _department,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Department')),
                  validator: _required,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Email (optional)')),
                  validator: (value) => value != null &&
                          value.trim().isNotEmpty &&
                          !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                              .hasMatch(value.trim())
                      ? AppText.of(context, 'Enter a valid email')
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _phone,
                  keyboardType: TextInputType.phone,
                  decoration: InputDecoration(
                      labelText: AppText.of(context, 'Phone (optional)')),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  icon: const Icon(Icons.calendar_month_outlined),
                  label: Text(AppText.hireDate(
                      context, _hireDate.toIso8601String().split('T').first)),
                  onPressed: _selectDate,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _status,
                  decoration:
                      InputDecoration(labelText: AppText.of(context, 'Status')),
                  items: [
                    DropdownMenuItem(
                        value: 'active',
                        child: Text(AppText.of(context, 'Active'))),
                    DropdownMenuItem(
                        value: 'inactive',
                        child: Text(AppText.of(context, 'Inactive'))),
                  ],
                  onChanged: (value) =>
                      setState(() => _status = value ?? 'active'),
                ),
                const SizedBox(height: 18),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: Text(AppText.of(context, 'Cancel')),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                        onPressed: _submit,
                        child: Text(
                            AppText.of(context, isEditing ? 'Save' : 'Add'))),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
