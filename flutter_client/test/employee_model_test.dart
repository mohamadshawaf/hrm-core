import 'package:flutter_test/flutter_test.dart';
import 'package:hrm_core_client/features/employees/employee.dart';

void main() {
  test('maps API employee payload to typed domain object', () {
    final employee = Employee.fromJson({
      'id': 'example-id',
      'employee_code': 'EMP-100',
      'full_name': 'Example Developer',
      'job_title': 'Developer',
      'department': 'Engineering',
      'email': null,
      'phone': null,
      'hire_date': '2024-01-01',
      'status': 'active',
      'version': 2,
    });
    expect(employee.code, 'EMP-100');
    expect(employee.hireDate.year, 2024);
    expect(employee.version, 2);
  });

  test('draft serializes only supported fields', () {
    final draft = EmployeeDraft(
      code: 'EMP-200',
      fullName: 'Example Manager',
      jobTitle: 'Manager',
      department: 'Operations',
      hireDate: DateTime(2024, 3, 5),
      status: 'active',
    );
    expect(draft.toJson()['employee_code'], 'EMP-200');
    expect(draft.toJson(includeCode: false).containsKey('employee_code'), false);
    expect(draft.toJson()['hire_date'], '2024-03-05');
  });
}
