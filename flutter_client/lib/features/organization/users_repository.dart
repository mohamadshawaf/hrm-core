import '../../core/api_client.dart';
import '../auth/auth_repository.dart';

class CompanyUser {
  const CompanyUser({required this.id, required this.email, required this.role,
    required this.isActive, required this.version});

  final String id;
  final String email;
  final String role;
  final bool isActive;
  final int version;

  factory CompanyUser.fromJson(Map<String, dynamic> json) => CompanyUser(
    id: json['id'] as String,
    email: json['email'] as String,
    role: json['role'] as String,
    isActive: json['is_active'] as bool,
    version: json['version'] as int,
  );
}

class CompanyUsersRepository {
  const CompanyUsersRepository({required this.api, required this.session});

  final ApiClient api;
  final UserSession session;

  Future<CompanyUsersPageResult> list({int limit = 20, int offset = 0}) async {
    final token = await session.validAccessToken(api);
    final response = await api.request('GET', 'organization/users',
        token: token,
        query: {'limit': '$limit', 'offset': '$offset'});
    final items = (response['items'] as List<dynamic>)
        .map((item) => CompanyUser.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
    return CompanyUsersPageResult(items: items, total: response['total'] as int);
  }

  Future<void> invite({required String email, required String role}) async {
    final token = await session.validAccessToken(api);
    await api.request('POST', 'organization/invitations', token: token,
        body: {'email': email.trim().toLowerCase(), 'role': role});
  }

  Future<List<CompanyInvitation>> invitations() async {
    final token = await session.validAccessToken(api);
    final response = await api.request('GET', 'organization/invitations', token: token);
    return (response['items'] as List<dynamic>).map((raw) =>
        CompanyInvitation.fromJson(Map<String, dynamic>.from(raw as Map))).toList();
  }

  Future<void> update(CompanyUser user, {required String role,
      required bool isActive}) async {
    final token = await session.validAccessToken(api);
    await api.request('PATCH', 'organization/users/${user.id}',
        token: token, body: {
          'expected_version': user.version,
          'role': role, 'is_active': isActive,
        });
  }
}

class CompanyInvitation {
  const CompanyInvitation({required this.email, required this.role,
    required this.expiresAt, required this.acceptedAt, required this.revokedAt});

  final String email;
  final String role;
  final int expiresAt;
  final int? acceptedAt;
  final int? revokedAt;

  bool get isPending => acceptedAt == null && revokedAt == null &&
    DateTime.now().millisecondsSinceEpoch ~/ 1000 < expiresAt;

  factory CompanyInvitation.fromJson(Map<String, dynamic> json) => CompanyInvitation(
    email: json['email'] as String,
    role: json['role'] as String,
    expiresAt: json['expires_at'] as int,
    acceptedAt: json['accepted_at'] as int?,
    revokedAt: json['revoked_at'] as int?,
  );
}

class CompanyUsersPageResult {
  const CompanyUsersPageResult({required this.items, required this.total});
  final List<CompanyUser> items;
  final int total;
}
