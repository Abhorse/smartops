import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartops/app.dart';

void main() {
  testWidgets('SmartOps app renders splash screen', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: SmartOpsApp()));
    await tester.pumpAndSettle();

    expect(find.text('SmartOps'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
  });
}
