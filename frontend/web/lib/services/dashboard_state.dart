import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/device.dart';
import 'api_service.dart';
import 'realtime_service.dart';

class DashboardState extends ChangeNotifier {
  final ApiService api;
  final RealtimeService realtime;

  OverviewStats? overview;
  List<Device> devices = const [];
  List<Alert> alerts = const [];
  List<Activity> activities = const [];
  WsStatus connection = WsStatus.connecting;
  String? errorMessage;
  bool _initialized = false;

  DashboardState({required this.api, required this.realtime}) {
    realtime.status.listen((s) {
      connection = s;
      notifyListeners();
    });
    realtime.events.listen((event) {
      // Server pushes simulation_tick; reload lightweight data.
      if (event['type'] == 'simulation_tick' || event['type'] == 'device_update') {
        refreshAll();
      }
    });
  }

  Future<void> initialLoad() async {
    if (!_initialized) {
      realtime.connect();
      _initialized = true;
    }
    await refreshAll();
  }

  Future<void> refreshAll() async {
    try {
      final results = await Future.wait([
        api.fetchOverview(),
        api.fetchDevices(),
        api.fetchAlerts(),
        api.fetchActivities(limit: 15),
      ]);
      overview = results[0] as OverviewStats;
      devices = results[1] as List<Device>;
      alerts = results[2] as List<Alert>;
      activities = results[3] as List<Activity>;
      errorMessage = null;
    } catch (e) {
      errorMessage = e.toString();
    }
    notifyListeners();
  }

  Future<void> toggleDevice(Device device) async {
    final newStatus = device.isOn ? 'off' : 'on';
    try {
      await api.setDeviceStatus(device.id, newStatus);
      await refreshAll();
    } catch (e) {
      errorMessage = e.toString();
      notifyListeners();
    }
  }
}
  final List<void Function()> _listeners = [];
  void addListener(void Function() l) => _listeners.add(l);
  void removeListener(void Function() l) => _listeners.remove(l);
  void notifyListeners() {
    for (final l in List.of(_listeners)) {
      l();
    }
  }
}