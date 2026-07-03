import 'dart:async';

import 'package:flutter/material.dart';

import '../models/device.dart';
import '../services/api_service.dart';
import '../services/dashboard_state.dart';
import '../services/realtime_service.dart';
import '../theme/app_theme.dart';
import '../widgets/activity_feed.dart';
import '../widgets/alert_list.dart';
import '../widgets/connection_indicator.dart';
import '../widgets/device_tile.dart';
import '../widgets/live_power_chart.dart';
import '../widgets/room_card.dart';
import '../widgets/stat_card.dart';

class DashboardConfig {
  final String apiBaseUrl;
  final String wsUrl;
  const DashboardConfig({required this.apiBaseUrl, required this.wsUrl});

  factory DashboardConfig.fromWindow() {
    // Allow overrides via window for local dev.
    final base = const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8000',
    );
    final ws = const String.fromEnvironment(
      'WS_URL',
      defaultValue: 'ws://localhost:8000/ws',
    );
    return DashboardConfig(apiBaseUrl: base, wsUrl: ws);
  }
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late final DashboardConfig _config;
  late final ApiService _api;
  late final RealtimeService _realtime;
  late final DashboardState _state;
  final StreamController<double> _powerSamples = StreamController<double>.broadcast();
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _config = DashboardConfig.fromWindow();
    _api = ApiService(baseUrl: _config.apiBaseUrl);
    _realtime = RealtimeService(wsUrl: _config.wsUrl);
    _state = DashboardState(api: _api, realtime: _realtime);
    _state.addListener(_onStateChanged);

    _refreshTimer = Timer.periodic(const Duration(seconds: 8), (_) => _state.refreshAll());

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _state.initialLoad();
    });
  }

  void _onStateChanged() {
    final total = _state.overview?.totalPower;
    if (total != null) {
      _powerSamples.add(total);
    }
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _state.removeListener(_onStateChanged);
    _powerSamples.close();
    _realtime.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.bolt, color: AppColors.primary),
            SizedBox(width: 8),
            Text('Office Energy Monitor'),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: ConnectionIndicator(status: _state.connection),
          ),
          IconButton(
            tooltip: 'Refresh',
            onPressed: _state.refreshAll,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: AnimatedBuilder(
        animation: _state,
        builder: (context, _) {
          if (_state.errorMessage != null && _state.overview == null) {
            return _ErrorState(
              message: _state.errorMessage!,
              onRetry: _state.refreshAll,
            );
          }
          return RefreshIndicator(
            onRefresh: _state.refreshAll,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth > 900;
                return ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    _OverviewGrid(
                      overview: _state.overview,
                      wide: wide,
                    ),
                    const SizedBox(height: 20),
                    LivePowerChart(samples: _powerSamples.stream),
                    const SizedBox(height: 20),
                    Text(
                      'Rooms',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    _RoomsGrid(rooms: _state.overview?.rooms ?? const []),
                    const SizedBox(height: 20),
                    Text(
                      'Live Devices',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    _DevicesGrid(
                      devices: _state.devices,
                      onToggle: (d) => _state.toggleDevice(d),
                    ),
                    const SizedBox(height: 20),
                    _BottomGrid(
                      alerts: _state.alerts,
                      activities: _state.activities,
                    ),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _OverviewGrid extends StatelessWidget {
  final OverviewStats? overview;
  final bool wide;
  const _OverviewGrid({required this.overview, required this.wide});
  @override
  Widget build(BuildContext context) {
    final stats = overview;
    final totalDevices = stats?.totalDevices ?? 0;
    final active = stats?.activeDevices ?? 0;
    final power = stats?.totalPower ?? 0.0;
    final alerts = stats?.activeAlerts ?? 0;

    final cards = [
      StatCard(
        icon: Icons.devices_other,
        label: 'Active / Total Devices',
        value: '$active / $totalDevices',
        color: AppColors.primary,
      ),
      StatCard(
        icon: Icons.flash_on,
        label: 'Live Power Draw',
        value: '${power.toStringAsFixed(0)} W',
        subtitle: 'Updated in real-time',
        color: AppColors.accent,
      ),
      StatCard(
        icon: Icons.warning_amber,
        label: 'Active Alerts',
        value: '$alerts',
        color: alerts == 0 ? AppColors.success : AppColors.warning,
      ),
      StatCard(
        icon: Icons.meeting_room,
        label: 'Rooms monitored',
        value: '${stats?.rooms.length ?? 3}',
        color: AppColors.primary,
      ),
    ];

    if (wide) {
      return Row(
        children: [
          for (final card in cards)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(right: 12),
                child: card,
              ),
            ),
        ],
      );
    }
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: cards,
    );
  }
}

class _RoomsGrid extends StatelessWidget {
  final List<RoomSummary> rooms;
  const _RoomsGrid({required this.rooms});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 900 ? 3 : (c.maxWidth > 600 ? 2 : 1);
        return GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: cols,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 1.5,
          children: rooms.map((r) => RoomCard(room: r)).toList(),
        );
      },
    );
  }
}

class _DevicesGrid extends StatelessWidget {
  final List<Device> devices;
  final ValueChanged<Device> onToggle;
  const _DevicesGrid({required this.devices, required this.onToggle});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1100 ? 3 : (c.maxWidth > 700 ? 2 : 1);
        return GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: cols,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 3.0,
          children: devices
              .map((d) => DeviceTile(device: d, onToggle: (_) => onToggle(d)))
              .toList(),
        );
      },
    );
  }
}

class _BottomGrid extends StatelessWidget {
  final List<Alert> alerts;
  final List<Activity> activities;
  const _BottomGrid({required this.alerts, required this.activities});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final wide = c.maxWidth > 900;
        final alertCard = AlertList(alerts: alerts);
        final activityCard = ActivityFeed(activities: activities);
        if (wide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: alertCard),
              const SizedBox(width: 16),
              Expanded(child: activityCard),
            ],
          );
        }
        return Column(children: [alertCard, const SizedBox(height: 16), activityCard]);
      },
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: AppColors.danger),
            const SizedBox(height: 12),
            Text(
              'Unable to load dashboard data',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}