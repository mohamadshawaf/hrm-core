import '../../core/api_client.dart';

class PlatformSession {
  final String accessToken;
  final String role;

  const PlatformSession({required this.accessToken, required this.role});
}

class PlatformAuthRepository {
  const PlatformAuthRepository(this._api);

  final ApiClient _api;

  Future<PlatformSession> signIn({required String email, required String password}) async {
    final result = await _api.request('POST', 'platform/auth/token', body: {
      'email': email.trim().toLowerCase(),
      'password': password,
    });
    final accessToken = result['access_token'] as String;
    final identity = await _api.request('GET', 'platform/auth/me', token: accessToken);
    return PlatformSession(accessToken: accessToken, role: identity['role'] as String);
  }
}

class PlatformRepository {
  const PlatformRepository(this._api, this.session);

  final ApiClient _api;
  final PlatformSession session;

  Future<Map<String, dynamic>> overview() =>
      _api.request('GET', 'platform/overview', token: session.accessToken);

  Future<Map<String, dynamic>> organizations({
    String search = '', int limit = 20, int offset = 0,
  }) => _api.request('GET', 'platform/organizations', token: session.accessToken,
      query: {'search': search, 'limit': '$limit', 'offset': '$offset'});

  Future<List<Map<String, dynamic>>> plans() async {
    final response = await _api.request('GET', 'platform/plans', token: session.accessToken);
    return (response['items'] as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<void> changeOrganizationStatus(String id, String status) async {
    await _api.request('PATCH', 'platform/organizations/$id/status',
        token: session.accessToken, body: {'status': status});
  }

  Future<void> changeSubscription({
    required String organizationId,
    required String planId,
    required String status,
    required int periodEndsAt,
    required int expectedVersion,
  }) async {
    await _api.request('PATCH', 'platform/organizations/$organizationId/subscription',
        token: session.accessToken, body: {
          'plan_id': planId,
          'status': status,
          'period_ends_at': periodEndsAt,
          'expected_version': expectedVersion,
        });
  }

  Future<void> createPlan({
    required String code,
    required String name,
    required int priceHalalas,
    required int maxEmployees,
  }) async {
    await _api.request('POST', 'platform/plans', token: session.accessToken, body: {
      'code': code.trim().toLowerCase(), 'name': name.trim(),
      'price_halalas': priceHalalas,
      'max_employees': maxEmployees,
    });
  }
}
