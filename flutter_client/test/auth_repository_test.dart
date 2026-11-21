import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:hrm_core_client/core/api_client.dart';
import 'package:hrm_core_client/features/auth/auth_repository.dart';

void main() {
  test('login returns tenant identity and signing out revokes server session', () async {
    final requests = <String>[];
    final client = MockClient((request) async {
      requests.add(request.url.path);
      if (request.url.path.endsWith('/auth/token')) {
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['organization_code'], 'alpha');
        expect(body['email'], 'owner@alpha.test');
        return http.Response(jsonEncode({
          'access_token': 'access', 'refresh_token': 'refresh',
          'expires_in': 900,
        }), 200);
      }
      if (request.url.path.endsWith('/auth/me')) {
        expect(request.headers['Authorization'], 'Bearer access');
        return http.Response(jsonEncode({
          'id': 'user-1', 'organization_id': 'org-1', 'role': 'owner',
        }), 200);
      }
      if (request.url.path.endsWith('/auth/logout')) {
        expect(request.headers['Authorization'], 'Bearer access');
        return http.Response('', 204);
      }
      return http.Response('not found', 404);
    });
    final api = ApiClient(baseUrl: 'https://hrm.example.test', httpClient: client);
    final auth = AuthRepository(api);
    final session = await auth.signIn(
      organizationCode: 'ALPHA', email: 'OWNER@ALPHA.TEST', password: 'secret',
    );
    expect(session.canManageUsers, isTrue);
    expect(session.organizationId, 'org-1');
    await auth.signOut(session);
    expect(session.accessToken, isEmpty);
    expect(session.refreshToken, isEmpty);
    expect(requests, [
      '/api/v1/auth/token', '/api/v1/auth/me', '/api/v1/auth/logout',
    ]);
    api.close();
  });

  test('expired access token is refreshed once with a rotating token', () async {
    var refreshRequests = 0;
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh')) {
        refreshRequests++;
        expect(jsonDecode(request.body)['refresh_token'], 'old-refresh');
        return http.Response(jsonEncode({
          'access_token': 'new-access', 'refresh_token': 'new-refresh',
          'expires_in': 900,
        }), 200);
      }
      return http.Response('not found', 404);
    });
    final api = ApiClient(baseUrl: 'https://hrm.example.test', httpClient: client);
    final session = UserSession(
      accessToken: 'old-access', refreshToken: 'old-refresh',
      accessExpiresAt: DateTime.now().subtract(const Duration(seconds: 1)),
      role: 'hr', organizationId: 'org-1',
    );
    final results = await Future.wait([
      session.validAccessToken(api), session.validAccessToken(api),
    ]);
    expect(results, ['new-access', 'new-access']);
    expect(session.refreshToken, 'new-refresh');
    expect(refreshRequests, 1);
    api.close();
  });
}
