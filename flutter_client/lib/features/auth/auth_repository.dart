import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';

class UserSession {
  String accessToken;
  String refreshToken;
  DateTime _accessExpiresAt;
  final String role;
  final String organizationId;
  Future<void>? _refreshing;

  UserSession({
    required this.accessToken,
    required this.refreshToken,
    required DateTime accessExpiresAt,
    required this.role,
    required this.organizationId,
  }) : _accessExpiresAt = accessExpiresAt;

  Future<String> validAccessToken(ApiClient api) async {
    if (DateTime.now().isAfter(
      _accessExpiresAt.subtract(const Duration(seconds: 45)),
    )) {
      _refreshing ??= _rotate(api);
      try {
        await _refreshing;
      } finally {
        _refreshing = null;
      }
    }
    return accessToken;
  }

  Future<void> _rotate(ApiClient api) async {
    final response = await api.request('POST', 'auth/refresh', body: {
      'refresh_token': refreshToken,
    });
    accessToken = response['access_token'] as String;
    refreshToken = response['refresh_token'] as String;
    _accessExpiresAt = DateTime.now().add(
      Duration(seconds: response['expires_in'] as int),
    );
  }

  void clearSecrets() {
    accessToken = '';
    refreshToken = '';
  }

  bool get canEditEmployees => role == 'owner' || role == 'hr';
  bool get canManageUsers => role == 'owner';
}

class AuthRepository {
  const AuthRepository(this._api);

  final ApiClient _api;

  Future<void> registerOrganization({
    required String organizationCode,
    required String organizationName,
    required String ownerEmail,
    required String password,
  }) async {
    await _api.request('POST', 'organizations/register', body: {
      'organization_code': organizationCode.trim().toLowerCase(),
      'organization_name': organizationName.trim(),
      'owner_email': ownerEmail.trim().toLowerCase(),
      'password': password,
    });
  }

  Future<void> verifyOrganizationEmail(String token) async {
    await _api.request('POST', 'organizations/verify-email', body: {
      'token': token.trim(),
    });
  }

  Future<void> resendVerification({
    required String organizationCode,
    required String ownerEmail,
  }) async {
    await _api.request('POST', 'organizations/resend-verification', body: {
      'organization_code': organizationCode.trim().toLowerCase(),
      'owner_email': ownerEmail.trim().toLowerCase(),
    });
  }

  Future<UserSession> signIn({
    required String organizationCode,
    required String email,
    required String password,
  }) async {
    final tokenResult = await _api.request('POST', 'auth/token', body: {
      'organization_code': organizationCode.trim().toLowerCase(),
      'email': email.trim().toLowerCase(),
      'password': password,
      'device_label': kIsWeb ? 'Flutter Web' : 'Flutter ${defaultTargetPlatform.name}',
    });
    final accessToken = tokenResult['access_token'] as String;
    final user = await _api.request('GET', 'auth/me', token: accessToken);
    return UserSession(
      accessToken: accessToken,
      refreshToken: tokenResult['refresh_token'] as String,
      accessExpiresAt: DateTime.now().add(
        Duration(seconds: tokenResult['expires_in'] as int),
      ),
      role: user['role'] as String,
      organizationId: user['organization_id'] as String,
    );
  }

  Future<void> signOut(UserSession session) async {
    try {
      final accessToken = await session.validAccessToken(_api);
      await _api.request('POST', 'auth/logout', token: accessToken);
    } finally {
      session.clearSecrets();
    }
  }

  Future<void> acceptInvitation({required String token,
    required String password}) async {
    await _api.request('POST', 'organization/invitations/accept', body: {
      'token': token.trim(), 'password': password,
    });
  }

  Future<void> requestPasswordReset({required String companyCode,
    required String email}) async {
    await _api.request('POST', 'auth/password-resets/request', body: {
      'organization_code': companyCode.trim().toLowerCase(),
      'email': email.trim().toLowerCase(),
    });
  }

  Future<void> confirmPasswordReset({required String token,
    required String newPassword}) async {
    await _api.request('POST', 'auth/password-resets/confirm', body: {
      'token': token.trim(), 'new_password': newPassword,
    });
  }
}
