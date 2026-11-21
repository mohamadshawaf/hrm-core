import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'platform_repository.dart';

class PlatformDashboardPage extends StatefulWidget {
  const PlatformDashboardPage(
      {super.key, required this.repository, required this.onLogout});

  final PlatformRepository repository;
  final VoidCallback onLogout;

  @override
  State<PlatformDashboardPage> createState() => _PlatformDashboardPageState();
}

class _PlatformDashboardPageState extends State<PlatformDashboardPage> {
  final _search = TextEditingController();
  int _tab = 0;
  int _offset = 0;
  bool _loading = true;
  bool _working = false;
  String? _error;
  Map<String, dynamic> _overview = {};
  Map<String, dynamic> _organizations = {'items': <dynamic>[], 'total': 0};
  List<Map<String, dynamic>> _plans = [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _refresh({bool showLoader = true}) async {
    if (showLoader) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final summary = await widget.repository.overview();
      final companies = await widget.repository.organizations(
        search: _search.text.trim(),
        limit: 10,
        offset: _offset,
      );
      final plans = await widget.repository.plans();
      if (!mounted) return;
      setState(() {
        _overview = summary;
        _organizations = companies;
        _plans = plans;
        _error = null;
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load the platform data.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_working) return;
    setState(() => _working = true);
    try {
      await action();
      await _refresh(showLoader: false);
    } on ApiException catch (exception) {
      if (mounted) _showError(exception.message);
    } catch (_) {
      if (mounted) _showError('The change could not be saved.');
    } finally {
      if (mounted) setState(() => _working = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _changeStatus(Map<String, dynamic> company) async {
    final suspended = company['status'] == 'suspended';
    final nextStatus = suspended ? 'active' : 'suspended';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(suspended ? 'Reactivate company?' : 'Suspend company?'),
        content: Text(suspended
            ? 'Restore access for ${company['name']}?'
            : 'Block access for ${company['name']} and invalidate its existing sessions?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: Text(suspended ? 'Reactivate' : 'Suspend')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    await _run(() => widget.repository
        .changeOrganizationStatus(company['id'] as String, nextStatus));
  }

  Future<void> _changeSubscription(Map<String, dynamic> company) async {
    if (_plans.isEmpty) return;
    var planId = company['plan_id'] as String? ?? _plans.first['id'] as String;
    var status = company['subscription_status'] as String? ?? 'trialing';
    final endEpoch = company['period_ends_at'] as int? ??
        DateTime.now().add(const Duration(days: 14)).millisecondsSinceEpoch ~/
            1000;
    var endDate = DateTime.fromMillisecondsSinceEpoch(endEpoch * 1000);
    final firstDate = DateTime(2023);
    final lastDate = DateTime(2100);
    if (endDate.isBefore(firstDate)) endDate = firstDate;
    if (endDate.isAfter(lastDate)) endDate = lastDate;
    final draft = await showDialog<_SubscriptionDraft>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Manage subscription'),
          content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(company['name'] as String),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<String>(
                    initialValue: planId,
                    decoration: const InputDecoration(labelText: 'Plan'),
                    isExpanded: true,
                    items: _plans
                        .map((plan) => DropdownMenuItem<String>(
                              value: plan['id'] as String,
                              child: Text(plan['name'] as String),
                            ))
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setDialogState(() => planId = value);
                    },
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    initialValue: status,
                    decoration:
                        const InputDecoration(labelText: 'Subscription status'),
                    items: ['trialing', 'active', 'past_due', 'canceled']
                        .map((value) =>
                            DropdownMenuItem(value: value, child: Text(value)))
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setDialogState(() => status = value);
                    },
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.event_outlined),
                    label: Text(
                        'Period ends: ${endDate.year}-${endDate.month}-${endDate.day}'),
                    onPressed: () async {
                      final selected = await showDatePicker(
                        context: dialogContext,
                        firstDate: firstDate,
                        lastDate: lastDate,
                        initialDate: endDate,
                      );
                      if (selected != null) {
                        setDialogState(() => endDate = selected);
                      }
                    },
                  ),
                  const SizedBox(height: 8),
                  const Text(
                      'Administrative status only. No payment is collected.'),
                ],
              )),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () => Navigator.pop(
                    dialogContext, _SubscriptionDraft(planId, status, endDate)),
                child: const Text('Save subscription')),
          ],
        ),
      ),
    );
    if (draft == null || !mounted) return;
    final chosenDay = draft.endDate;
    final periodEndsAt =
        DateTime(chosenDay.year, chosenDay.month, chosenDay.day, 23, 59, 59)
                .toUtc()
                .millisecondsSinceEpoch ~/
            1000;
    await _run(() => widget.repository.changeSubscription(
          organizationId: company['id'] as String,
          planId: draft.planId,
          status: draft.status,
          periodEndsAt: periodEndsAt,
          expectedVersion: company['subscription_version'] as int,
        ));
  }

  int? _parseHalalas(String raw) {
    final text = raw.trim();
    if (!RegExp(r'^\d+(\.\d{1,2})?$').hasMatch(text)) return null;
    final parts = text.split('.');
    final riyals = int.tryParse(parts[0]);
    if (riyals == null) return null;
    final halalas =
        parts.length == 1 ? 0 : int.parse(parts[1].padRight(2, '0'));
    return riyals * 100 + halalas;
  }

  Future<void> _createPlan() async {
    final formKey = GlobalKey<FormState>();
    final name = TextEditingController();
    final code = TextEditingController();
    final price = TextEditingController(text: '0.00');
    final limit = TextEditingController(text: '25');
    final draft = await showDialog<_PlanDraft>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Create subscription plan'),
        content: SizedBox(
            width: 430,
            child: SingleChildScrollView(
                child: Form(
              key: formKey,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextFormField(
                    controller: name,
                    decoration: const InputDecoration(labelText: 'Plan name'),
                    validator: (value) =>
                        value == null || value.trim().length < 2
                            ? 'Enter a plan name'
                            : null),
                const SizedBox(height: 12),
                TextFormField(
                    controller: code,
                    decoration:
                        const InputDecoration(labelText: 'Unique plan code'),
                    validator: (value) => RegExp(r'^[a-z0-9_-]{2,40}$')
                            .hasMatch(value?.trim().toLowerCase() ?? '')
                        ? null
                        : 'Use 2–40 letters, numbers, - or _'),
                const SizedBox(height: 12),
                TextFormField(
                    controller: price,
                    decoration:
                        const InputDecoration(labelText: 'Listed price (SAR)'),
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    validator: (value) => _parseHalalas(value ?? '') == null
                        ? 'Enter a valid SAR amount (up to 2 decimals)'
                        : null),
                const SizedBox(height: 12),
                TextFormField(
                    controller: limit,
                    decoration:
                        const InputDecoration(labelText: 'Employee capacity'),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      final n = int.tryParse(value ?? '');
                      return n == null || n < 1 || n > 1000000
                          ? 'Enter 1–1,000,000'
                          : null;
                    }),
              ]),
            ))),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () {
                if (!formKey.currentState!.validate()) return;
                Navigator.pop(
                    dialogContext,
                    _PlanDraft(name.text, code.text, _parseHalalas(price.text)!,
                        int.parse(limit.text)));
              },
              child: const Text('Create plan')),
        ],
      ),
    );
    name.dispose();
    code.dispose();
    price.dispose();
    limit.dispose();
    if (draft == null || !mounted) return;
    await _run(() => widget.repository.createPlan(
          code: draft.code,
          name: draft.name,
          priceHalalas: draft.priceHalalas,
          maxEmployees: draft.maxEmployees,
        ));
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 850;
    final sections = [
      NavigationDestination(
          icon: const Icon(Icons.dashboard_outlined),
          label: AppText.of(context, 'Overview')),
      NavigationDestination(
          icon: const Icon(Icons.apartment_outlined),
          label: AppText.of(context, 'Companies')),
      NavigationDestination(
          icon: const Icon(Icons.credit_card_outlined),
          label: AppText.of(context, 'Plans')),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('HRM Core · Platform'),
        actions: [
          const LanguageSwitcher(),
          IconButton(
              tooltip: AppText.of(context, 'Refresh'),
              onPressed: _working ? null : _refresh,
              icon: const Icon(Icons.refresh_outlined)),
          IconButton(
              tooltip: AppText.of(context, 'Sign out'),
              onPressed: widget.onLogout,
              icon: const Icon(Icons.logout)),
        ],
      ),
      body: wide
          ? Row(children: [
              NavigationRail(
                selectedIndex: _tab,
                labelType: NavigationRailLabelType.all,
                onDestinationSelected: (value) => setState(() => _tab = value),
                destinations: [
                  NavigationRailDestination(
                      icon: const Icon(Icons.dashboard_outlined),
                      label: Text(AppText.of(context, 'Overview'))),
                  NavigationRailDestination(
                      icon: const Icon(Icons.apartment_outlined),
                      label: Text(AppText.of(context, 'Companies'))),
                  NavigationRailDestination(
                      icon: const Icon(Icons.credit_card_outlined),
                      label: Text(AppText.of(context, 'Plans'))),
                ],
              ),
              const VerticalDivider(width: 1),
              Expanded(child: _body()),
            ])
          : _body(),
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              destinations: sections,
              selectedIndex: _tab,
              onDestinationSelected: (value) => setState(() => _tab = value),
            ),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
          child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_error!),
          const SizedBox(height: 12),
          FilledButton(
              onPressed: _refresh,
              child: Text(AppText.of(context, 'Try again'))),
        ]),
      ));
    }
    return switch (_tab) {
      0 => _overviewPage(),
      1 => _companiesPage(),
      _ => _plansPage(),
    };
  }

  Widget _overviewPage() =>
      ListView(padding: const EdgeInsets.all(20), children: [
        Text(AppText.of(context, 'Platform overview'),
            style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 18),
        Wrap(spacing: 12, runSpacing: 12, children: [
          _stat('Companies', _overview['organizations_total']),
          _stat('Active', _overview['organizations_active']),
          _stat('Pending verification', _overview['organizations_pending']),
          _stat('Suspended', _overview['organizations_suspended']),
          _stat('Employee records', _overview['employees_total']),
        ]),
        const SizedBox(height: 20),
        const Card(
            child: Padding(
                padding: EdgeInsets.all(20),
                child: Text(
                  'Subscription changes are administrative records only. '
                  'Billing, automated access enforcement and payment integrations are not active.',
                ))),
      ]);

  Widget _stat(String title, dynamic count) => SizedBox(
      width: 200,
      child: Card(
        elevation: 0,
        child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(AppText.of(context, title)),
                const SizedBox(height: 10),
                Text('${count ?? 0}',
                    style: Theme.of(context).textTheme.headlineMedium),
              ],
            )),
      ));

  Widget _companiesPage() {
    final items = (_organizations['items'] as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    final total = _organizations['total'] as int;
    return ListView(padding: const EdgeInsets.all(20), children: [
      Text(AppText.of(context, 'Company management'),
          style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 12),
      TextField(
        controller: _search,
        onSubmitted: (_) {
          _offset = 0;
          _refresh();
        },
        decoration: InputDecoration(
          labelText: AppText.of(context, 'Find a company by name or code'),
          prefixIcon: const Icon(Icons.search),
          suffixIcon: IconButton(
              tooltip: AppText.of(context, 'Search'),
              onPressed: () {
                _offset = 0;
                _refresh();
              },
              icon: const Icon(Icons.arrow_forward)),
        ),
      ),
      const SizedBox(height: 12),
      if (items.isEmpty)
        Padding(
            padding: const EdgeInsets.all(24),
            child:
                Text(AppText.of(context, 'No companies match this search.'))),
      ...items.map((company) => Card(
          elevation: 0,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(company['name'] as String,
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 6),
              Text('Code: ${company['code']} · Status: ${company['status']}'),
              Text('Employees: ${company['employees_count']} · '
                  'Plan: ${company['plan_name'] ?? 'None'} · '
                  'Subscription: ${company['subscription_status'] ?? 'None'}'),
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                OutlinedButton.icon(
                  onPressed: _working || company['status'] == 'pending_email'
                      ? null
                      : () => _changeStatus(company),
                  icon: Icon(company['status'] == 'suspended'
                      ? Icons.play_circle_outline
                      : Icons.pause_circle_outline),
                  label: Text(AppText.of(
                      context,
                      company['status'] == 'suspended'
                          ? 'Reactivate'
                          : 'Suspend')),
                ),
                OutlinedButton.icon(
                  onPressed: _working || company['subscription_version'] == null
                      ? null
                      : () => _changeSubscription(company),
                  icon: const Icon(Icons.tune),
                  label: Text(AppText.of(context, 'Manage plan')),
                ),
              ]),
            ]),
          ))),
      const SizedBox(height: 12),
      Row(mainAxisAlignment: MainAxisAlignment.end, children: [
        Text(
            '${total == 0 ? 0 : _offset + 1}–${(_offset + items.length)} of $total'),
        IconButton(
            tooltip: 'Previous page',
            onPressed: _offset == 0
                ? null
                : () {
                    _offset -= 10;
                    _refresh();
                  },
            icon: const Icon(Icons.chevron_left)),
        IconButton(
            tooltip: 'Next page',
            onPressed: _offset + items.length >= total
                ? null
                : () {
                    _offset += 10;
                    _refresh();
                  },
            icon: const Icon(Icons.chevron_right)),
      ]),
    ]);
  }

  Widget _plansPage() => ListView(padding: const EdgeInsets.all(20), children: [
        Row(children: [
          Expanded(
              child: Text(AppText.of(context, 'Subscription plans'),
                  style: Theme.of(context).textTheme.headlineMedium)),
          FilledButton.icon(
              onPressed: _working ? null : _createPlan,
              icon: const Icon(Icons.add),
              label: Text(AppText.of(context, 'New plan'))),
        ]),
        const SizedBox(height: 12),
        const Text(
            'Prices are descriptive metadata; no billing or charges occur.'),
        const SizedBox(height: 12),
        ..._plans.map((plan) => Card(
            elevation: 0,
            child: ListTile(
              title: Text(plan['name'] as String),
              subtitle: Text(
                  '${plan['code']} · Max employees: ${plan['max_employees']}'),
              trailing: Text(
                  '${((plan['price_halalas'] as int) / 100).toStringAsFixed(2)} SAR'),
            ))),
      ]);
}

class _SubscriptionDraft {
  const _SubscriptionDraft(this.planId, this.status, this.endDate);
  final String planId;
  final String status;
  final DateTime endDate;
}

class _PlanDraft {
  const _PlanDraft(this.name, this.code, this.priceHalalas, this.maxEmployees);
  final String name;
  final String code;
  final int priceHalalas;
  final int maxEmployees;
}
