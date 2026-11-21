import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({required String baseUrl, http.Client? httpClient})
      : _client = httpClient ?? http.Client(),
        _baseUri = Uri.parse(baseUrl) {
    if (_baseUri.host.isEmpty ||
        (_baseUri.scheme != 'https' &&
            !(kDebugMode && _baseUri.scheme == 'http'))) {
      throw ArgumentError('A valid HTTPS API address is required outside debug mode.');
    }
  }

  final http.Client _client;
  final Uri _baseUri;

  Future<Map<String, dynamic>> request(
    String method,
    String endpoint, {
    String? token,
    Map<String, String>? query,
    Map<String, dynamic>? body,
  }) async {
    final uri = _baseUri.replace(
      path: '/api/v1/$endpoint',
      queryParameters: query,
    );
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null) headers['Content-Type'] = 'application/json';
    if (token != null) headers['Authorization'] = 'Bearer $token';

    late final http.Response response;
    try {
      final payload = body == null ? null : jsonEncode(body);
      final pending = switch (method) {
        'GET' => _client.get(uri, headers: headers),
        'POST' => _client.post(uri, headers: headers, body: payload),
        'PATCH' => _client.patch(uri, headers: headers, body: payload),
        'DELETE' => _client.delete(uri, headers: headers),
        _ => throw ArgumentError('Unsupported request method'),
      };
      response = await pending.timeout(const Duration(seconds: 12));
    } catch (_) {
      throw const ApiException(0, 'Could not connect to the server.');
    }

    if (response.statusCode == 204) return <String, dynamic>{};
    final dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (_) {
      throw const ApiException(0, 'Invalid server response.');
    }
    if (response.statusCode >= 400) {
      final detail = decoded is Map ? decoded['detail'] : null;
      final message = detail is String ? detail : 'Request was rejected.';
      throw ApiException(response.statusCode, message);
    }
    if (decoded is! Map<String, dynamic>) {
      throw const ApiException(0, 'Invalid server response.');
    }
    return decoded;
  }

  void close() => _client.close();
}
