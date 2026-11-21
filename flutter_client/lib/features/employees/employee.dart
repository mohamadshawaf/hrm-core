class Employee {
  final String id;
  final String code;
  final String fullName;
  final String jobTitle;
  final String department;
  final String? email;
  final String? phone;
  final DateTime hireDate;
  final String status;
  final int version;

  const Employee({
    required this.id,
    required this.code,
    required this.fullName,
    required this.jobTitle,
    required this.department,
    required this.email,
    required this.phone,
    required this.hireDate,
    required this.status,
    required this.version,
  });

  factory Employee.fromJson(Map<String, dynamic> json) => Employee(
        id: json['id'] as String,
        code: json['employee_code'] as String,
        fullName: json['full_name'] as String,
        jobTitle: json['job_title'] as String,
        department: json['department'] as String,
        email: json['email'] as String?,
        phone: json['phone'] as String?,
        hireDate: DateTime.parse(json['hire_date'] as String),
        status: json['status'] as String,
        version: json['version'] as int,
      );
}

class EmployeeDraft {
  final String code;
  final String fullName;
  final String jobTitle;
  final String department;
  final String? email;
  final String? phone;
  final DateTime hireDate;
  final String status;

  const EmployeeDraft({
    required this.code,
    required this.fullName,
    required this.jobTitle,
    required this.department,
    this.email,
    this.phone,
    required this.hireDate,
    required this.status,
  });

  Map<String, dynamic> toJson({bool includeCode = true}) => {
        if (includeCode) 'employee_code': code,
        'full_name': fullName.trim(),
        'job_title': jobTitle.trim(),
        'department': department.trim(),
        'email': email?.trim().isEmpty == true ? null : email?.trim(),
        'phone': phone?.trim().isEmpty == true ? null : phone?.trim(),
        'hire_date': hireDate.toIso8601String().split('T').first,
        'status': status,
      };
}
