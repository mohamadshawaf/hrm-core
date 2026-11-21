import '../../core/api_client.dart';
import '../auth/auth_repository.dart';
import 'employee.dart';

class EmployeeRepository {
  final ApiClient api;
  final UserSession session;

  const EmployeeRepository({required this.api, required this.session});

  Future<EmployeePageResult> list({String search = '', int offset = 0}) async {
    final accessToken = await session.validAccessToken(api);
    final response = await api.request('GET', 'employees',
        token: accessToken,
        query: {'search': search, 'limit': '25', 'offset': '$offset'});
    final values = response['items'] as List<dynamic>;
    final employees = values
        .map((item) => Employee.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
    return EmployeePageResult(
      items: employees,
      total: response['total'] as int,
    );
  }

  Future<Employee> create(EmployeeDraft draft) async {
    final accessToken = await session.validAccessToken(api);
    final response = await api.request('POST', 'employees',
        token: accessToken, body: draft.toJson());
    return Employee.fromJson(response);
  }

  Future<Employee> update(Employee employee, EmployeeDraft draft) async {
    final accessToken = await session.validAccessToken(api);
    final response = await api.request('PATCH', 'employees/${employee.id}',
        token: accessToken,
        body: {
          ...draft.toJson(includeCode: false),
          'expected_version': employee.version,
        });
    return Employee.fromJson(response);
  }

  Future<void> archive(Employee employee) async {
    final accessToken = await session.validAccessToken(api);
    await api.request('DELETE', 'employees/${employee.id}',
        token: accessToken,
        query: {'expected_version': employee.version.toString()});
  }
}

class EmployeePageResult {
  const EmployeePageResult({required this.items, required this.total});

  final List<Employee> items;
  final int total;
}
