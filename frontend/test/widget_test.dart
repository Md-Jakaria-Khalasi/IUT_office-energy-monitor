// Smoke tests for the Office Energy Monitor dashboard.
//
// These verify that the theme + a static, network-free widget mount
// correctly. The live `OfficeEnergyApp` opens a WebSocket on init, which
// Flutter's fake_async test clock cannot drain; testing the network-bound
// surface is out of scope here (see backend/tests/ for API/WebSocket
// coverage). This suite only guards against widget-tree / theme breakage.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:office_energy_monitor/main.dart';
import 'package:office_energy_monitor/theme/app_theme.dart';
import 'package:office_energy_monitor/widgets/stat_card.dart';

void main() {
  testWidgets('AppTheme.dark provides a Material 3 dark palette',
      (tester) async {
    final theme = AppTheme.dark();
    expect(theme.brightness, Brightness.dark);
    expect(theme.useMaterial3, isTrue);
  });

  testWidgets('StatCard renders label, value, and icon', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark(),
        home: const Scaffold(
          body: StatCard(
            icon: Icons.flash_on,
            label: 'Live Power',
            value: 245,
            accent: Color(0xFF22E1FF),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Live Power'), findsOneWidget);
    expect(find.text('245'), findsOneWidget);
    expect(find.byIcon(Icons.flash_on), findsOneWidget);
  });

  test('OfficeEnergyApp symbol resolves (class export check)', () {
    // Lightweight regression: compile-time check that the public entry
    // point still exists. The full app tree is not mounted here because
    // it opens a WebSocket on init, which fake_async cannot settle.
    expect(OfficeEnergyApp, isNotNull);
  });
}

