import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hrm_core_client/main.dart';

void main() {
  for (final width in [320.0, 400.0, 1024.0, 1440.0]) {
    testWidgets('switches to Arabic RTL and remains scrollable at $width',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(width, 900);
      addTearDown(() {
        tester.view.resetDevicePixelRatio();
        tester.view.resetPhysicalSize();
      });
      await tester.pumpWidget(const HrmApp());
      await tester.tap(find.byIcon(Icons.language_outlined));
      await tester.pumpAndSettle();
      await tester.tap(find.text('العربية').last);
      await tester.pumpAndSettle();

      expect(find.text('تسجيل الدخول'), findsOneWidget);
      expect(find.text('رمز الشركة'), findsOneWidget);
      final element = tester.element(find.text('تسجيل الدخول'));
      expect(Directionality.of(element), TextDirection.rtl);
      expect(tester.takeException(), isNull);

      await tester.tap(find.byIcon(Icons.language_outlined));
      await tester.pumpAndSettle();
      await tester.tap(find.text('English').last);
      await tester.pumpAndSettle();
      expect(find.text('Sign in'), findsOneWidget);
      expect(Directionality.of(tester.element(find.text('Sign in'))),
          TextDirection.ltr);
      expect(tester.takeException(), isNull);
    });
  }
}
