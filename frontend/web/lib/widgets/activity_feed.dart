import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';

class ActivityFeed extends StatelessWidget {
  final List<Activity> activities;
  const ActivityFeed({super.key, required this.activities});

  @override
  Widget build(BuildContext context) {
    if (activities.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              const Icon(Icons.history, color: AppColors.textSecondary),
              const SizedBox(width: 12),
              Text(
                'No recent activity yet.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      );
    }
    final fmt = DateFormat('HH:mm');
    return Card(
      child: Column(
        children: [
          for (final a in activities.take(10))
            ListTile(
              dense: true,
              leading: Icon(
                a.action == 'turned_on' ? Icons.bolt : Icons.power_settings_new,
                color: a.action == 'turned_on'
                    ? AppColors.primary
                    : AppColors.textSecondary,
              ),
              title: Text(a.description),
              subtitle: Text(
                '${a.room} · ${fmt.format(a.createdAt.toLocal())}',
              ),
            ),
        ],
      ),
    );
  }
}