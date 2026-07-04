import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const OfficeEnergyApp());
}

/// Root of the web app. The dashboard owns its own state internally,
/// so this widget is a thin shell that supplies the [MaterialApp] +
/// theming.
class OfficeEnergyApp extends StatelessWidget {
  const OfficeEnergyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Office Energy Monitor',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.dark,
      home: const DashboardScreen(),
    );
  }
}