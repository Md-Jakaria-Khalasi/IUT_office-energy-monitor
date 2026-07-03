import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';

class AlertList extends StatelessWidget {
  final List<Alert> alerts;
  const AlertList({super.key, required this.alerts});

  Color _severityColor(String severity) {
    return switch (severity) {
      'critical' => AppColors.danger,
      'warning' => AppColors.warning,
      _ => AppColors.primary,
    };
  }

  @override
  Widget build(BuildContext context) {
    if (alerts.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              const Icon(Icons.check_circle, color: AppColors.success),
              const SizedBox(width: 12),
              Text(
                'No active alerts — system is healthy.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      );
    }

    final fmt = DateFormat('HH:mm:ss');
    return Card(
      child: Column(
        children: [
          for (final alert in alerts.take(8))
            ListTile(
              leading: CircleAvatar(
                backgroundColor: _severityColor(alert.severity).withOpacity(0.2),
                child: Icon(
                  Icons.warning_amber,
                  color: _severityColor(alert.severity),
                ),
              ),
              title: Text(alert.message),
              subtitle: Text(
                '${alert.room ?? "Office"} · ${fmt.format(alert.createdAt.toLocal())}',
              ),
            ),
        ],
      ),
    );
  }
}