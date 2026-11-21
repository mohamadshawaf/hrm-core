import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hrm_core_client/main.dart';

void main() {
  for (final width in [400.0, 1200.0]) {
    testWidgets('login screen renders at width $width without overflow', (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(width, 900);
      addTearDown(() {
        tester.view.resetDevicePixelRatio();
        tester.view.resetPhysicalSize();
      });
      await tester.pumpWidget(const HrmApp());
      expect(find.text('HRM Core'), findsOneWidget);
      expect(find.text('Sign in'), findsWidgets);
      expect(tester.takeException(), isNull);
    });
  }
}
