import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/app_locale.dart';
import 'auth_repository.dart';

class SessionsPage extends StatefulWidget {
  const SessionsPage(
      {super.key,
      required this.api,
      required this.session,
      required this.onLogout});

  final ApiClient api;
  final UserSession session;
  final VoidCallback onLogout;

  @override
  State<SessionsPage> createState() => _SessionsPageState();
}

class _SessionsPageState extends State<SessionsPage> {
  List<Map<String, dynamic>> _items = [];
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final token = await widget.session.validAccessToken(widget.api);
      final response =
          await widget.api.request('GET', 'auth/sessions', token: token);
      if (mounted) {
        setState(() => _items = (response['items'] as List<dynamic>)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList());
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
            () => _error = AppText.of(context, 'Unable to load sessions.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke(String id, bool isCurrent) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final token = await widget.session.validAccessToken(widget.api);
      await widget.api.request('DELETE', 'auth/sessions/$id', token: token);
      if (!mounted) return;
      if (isCurrent) {
        Navigator.of(context).pop();
        widget.onLogout();
      } else {
        await _load();
      }
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
            () => _error = AppText.of(context, 'Could not revoke session.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revokeAll() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final token = await widget.session.validAccessToken(widget.api);
      await widget.api.request('POST', 'auth/logout-all', token: token);
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.onLogout();
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(
            () => _error = AppText.of(context, 'Could not revoke sessions.'));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(AppText.of(context, 'Signed-in devices')),
            actions: [
              const LanguageSwitcher(),
              IconButton(
                  onPressed: _busy ? null : _load,
                  icon: const Icon(Icons.refresh),
                  tooltip: AppText.of(context, 'Refresh')),
            ]),
        body: SafeArea(
            child: Center(
                child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Text(AppText.of(context,
                'Review sessions associated with your account. Revoking a session immediately invalidates its access and refresh tokens.')),
            const SizedBox(height: 12),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  child: Text(_error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error))),
            ..._items.map((item) => Card(
                    child: ListTile(
                  leading: const Icon(Icons.devices_outlined),
                  title: Text(item['device_label'] as String? ??
                      AppText.of(context, 'Unknown device')),
                  subtitle: Text(
                      '${item['is_current'] == true ? '${AppText.of(context, 'Current')} · ' : ''}'
                      '${AppText.of(context, item['is_active'] == true ? 'Active' : 'Expired or revoked')}'),
                  trailing: item['is_active'] == true
                      ? TextButton(
                          onPressed: _busy
                              ? null
                              : () => _revoke(item['id'] as String,
                                  item['is_current'] == true),
                          child: Text(AppText.of(context, 'Revoke')),
                        )
                      : null,
                ))),
            const SizedBox(height: 16),
            OutlinedButton.icon(
                onPressed: _busy ? null : _revokeAll,
                icon: const Icon(Icons.logout),
                label: Text(AppText.of(context, 'Sign out on every device'))),
          ]),
        ))),
      );
}
