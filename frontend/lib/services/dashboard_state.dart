import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/device.dart';
import 'api_service.dart';
import 'realtime_service.dart';

/// Single source of truth for the dashboard.
///
/// PART 7 responsibilities:
///   * Loads the initial state via REST (one-shot, on `start()`).
///   * Subscribes to the realtime channel and **merges** every event
///     in place — no full reloads on a single tick.
///   * Exposes a [ChangeNotifier] surface for the UI; widgets rebuild
///     via `ListenableBuilder`.
class DashboardState extends ChangeNotifier {
  DashboardState({required this.api, required this.realtime}) {
    _sub = realtime.events.listen(_onRealtimeEvent);
    _statusSub = realtime.status.listen((s) {
      _connection = s;
      _lastUpdate = DateTime.now();
      notifyListeners();
    });
  }

  final ApiService api;
  final RealtimeService realtime;

  StreamSubscription<Map<String, dynamic>>? _sub;
  StreamSubscription<WsStatus>? _statusSub;
  Timer? _refreshTimer;
  Timer? _ticker;

  bool _initialLoading = true;
  String? _errorMessage;
  OverviewStats? _overview;
  List<Device> _devices = const [];
  List<Alert> _alerts = const [];
  WsStatus _connection = WsStatus.connecting;
  DateTime? _lastUpdate;

  /// Broadcast stream of `total_power` (W) values from simulation ticks.
  /// Used by [LivePowerChart] to draw a rolling sparkline without
  /// coupling to the ChangeNotifier notification cadence.
  final StreamController<double> _samples =
      StreamController<double>.broadcast();
  Stream<double> get samples => _samples.stream;

  bool get initialLoading => _initialLoading;
  String? get errorMessage => _errorMessage;
  OverviewStats? get overview => _overview;
  List<Device> get devices => _devices;
  List<Alert> get alerts => _alerts;
  WsStatus get connection => _connection;
  DateTime? get lastUpdate => _lastUpdate;

  // Convenience derived getters.
  double get totalPower => _overview?.totalPower ?? 0.0;
  int get activeDevices => _overview?.activeDevices ?? 0;
  int get totalDevices => _overview?.totalDevices ?? _devices.length;

  /// Number of open / unacknowledged alerts — drives the counter and
  /// the active-alerts badge. Counted from the local alert list so the
  /// number matches the visible rows.
  int get activeAlerts =>
      _alerts.where((a) => !a.acknowledged && !a.isClosed).length;
  List<RoomSummary> get rooms => _overview?.rooms ?? const [];

  // ----------------------------------------------------------- lifecycle

  void start() {
    _refreshTimer ??= Timer.periodic(
      const Duration(seconds: 8),
      (_) => refreshAll(),
    );
    _ticker ??= Timer.periodic(const Duration(seconds: 1), (_) {
      // Light-weight tick to keep the "live clock / last updated" widget
      // fresh and pulse the Live Status indicator.
      if (_lastUpdate != null) notifyListeners();
    });
    initialLoad();
    realtime.connect();
  }

  Future<void> initialLoad() async {
    try {
      _initialLoading = true;
      _errorMessage = null;
      notifyListeners();
      await _load();
      _initialLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = e.toString();
      _initialLoading = false;
      notifyListeners();
    }
  }

  Future<void> refreshAll() async {
    try {
      _errorMessage = null;
      await _load();
      _lastUpdate = DateTime.now();
      notifyListeners();
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<void> _load() async {
    final results = await Future.wait<Object>([
      api.fetchOverview(),
      api.fetchAllDevices(),
      api.fetchAlerts(),
    ]);
    _overview = results[0] as OverviewStats;
    _devices = results[1] as List<Device>;
    _alerts = results[2] as List<Alert>;
  }

  Future<List<Device>> fetchAllDevices() async => api.fetchAllDevices();
  Future<List<Device>> fetchDevices({String? room}) =>
      api.fetchDevices(room: room);

  // --------------------------------------------------------------- writes

  Future<void> toggleDevice(Device device) async {
    final next = device.isOn ? 'off' : 'on';
    // Optimistic
    final before = _devices;
    _devices = _devices
        .map((d) => d.id == device.id ? _withStatus(d, next) : d)
        .toList();
    _overview = _recomputeOverview();
    notifyListeners();
    try {
      await api.setDeviceStatus(device.id, next);
      _lastUpdate = DateTime.now();
      notifyListeners();
    } catch (e) {
      _devices = before;
      _overview = _recomputeOverview();
      _errorMessage = 'Failed to toggle ${device.name}: $e';
      notifyListeners();
      rethrow;
    }
  }

  /// Toggle every device in a room to [status]. The UI calls this from
  /// the room card's ALL ON / ALL OFF buttons. The backend fans out
  /// `device_update` events for each affected device plus a single
  /// `room_power` event — the realtime subscribers below merge them
  /// back into this state without any extra REST calls.
  Future<void> setRoomStatus(String roomName, String status) async {
    final before = _devices;
    _devices = _devices
        .map((d) => d.room == roomName ? _withStatus(d, status) : d)
        .toList();
    _overview = _recomputeOverview();
    notifyListeners();
    try {
      final targets = _devices.where((d) => d.room == roomName).toList();
      for (final d in targets) {
        await api.setDeviceStatus(d.id, status);
      }
      _lastUpdate = DateTime.now();
      notifyListeners();
    } catch (e) {
      _devices = before;
      _overview = _recomputeOverview();
      _errorMessage = 'Failed to set $roomName: $e';
      notifyListeners();
      rethrow;
    }
  }

  Device _withStatus(Device d, String status) => Device(
        id: d.id,
        name: d.name,
        room: d.room,
        type: d.type,
        status: status,
        powerConsumption: d.powerConsumption,
        lastChanged: DateTime.now(),
      );

  /// Re-derive every aggregate field from the current device & alert
  /// lists. Called after every merge so the UI always reflects the
  /// ground truth the realtime stream has built up.
  OverviewStats _recomputeOverview() {
    int total = _devices.length;
    int active = _devices.where((d) => d.isOn).length;
    double power = _devices
        .where((d) => d.isOn)
        .fold(0.0, (s, d) => s + d.powerConsumption);

    final byRoom = <String, List<Device>>{};
    for (final d in _devices) {
      byRoom.putIfAbsent(d.room, () => <Device>[]).add(d);
    }
    final roomSummaries = byRoom.entries.map((e) {
      final roomActive = e.value.where((d) => d.isOn).length;
      final roomPower = e.value
          .where((d) => d.isOn)
          .fold(0.0, (s, d) => s + d.powerConsumption);
      return RoomSummary(
        room: e.key,
        totalDevices: e.value.length,
        activeDevices: roomActive,
        totalPower: roomPower,
      );
    }).toList()
      ..sort((a, b) => a.room.compareTo(b.room));

    return OverviewStats(
      totalDevices: total,
      activeDevices: active,
      totalPower: power,
      rooms: roomSummaries,
      activeAlerts: activeAlerts,
    );
  }

  // ------------------------------------------------------------ realtime

  void _onRealtimeEvent(Map<String, dynamic> payload) {
    final rawType = payload['type'] as String?;
    if (rawType == null) return;
    var dirty = false;
    switch (rawType) {
      case 'welcome':
        // Server greeting — no state change.
        break;
      case 'device_update':
        dirty = _applyDeviceUpdate(payload) || dirty;
        break;
      case 'room_power':
        dirty = _applyRoomPower(payload) || dirty;
        break;
      case 'simulation_tick':
        dirty = _applyTick(payload) || dirty;
        break;
      case 'alert_created':
        dirty = _applyAlertCreated(payload) || dirty;
        break;
      case 'alert_updated':
        dirty = _applyAlertUpdated(payload) || dirty;
        break;
      case 'alert_acknowledged':
        dirty = _applyAlertAcknowledged(payload) || dirty;
        break;
      case 'alert_resolved':
        dirty = _applyAlertResolved(payload) || dirty;
        break;
      case 'alert_dismissed':
        dirty = _applyAlertDismissed(payload) || dirty;
        break;
      case 'alert_escalated':
      case 'alert_reminder':
      case 'alert_summary':
        // These carry derived / reminder payloads. We deliberately do
        // NOT touch state from them — a stale escalation shouldn't
        // overwrite a freshly-acked alert. The next REST refresh (the
        // 8-second timer) will reconcile any drift.
        break;
      default:
        // Unknown event type — ignore silently for forward-compat.
        break;
    }

    if (dirty) {
      _overview = _recomputeOverview();
      _lastUpdate = DateTime.now();
      notifyListeners();
    } else {
      _lastUpdate = DateTime.now();
    }
  }

  /// Returns `true` if the in-memory state actually changed.
  bool _applyDeviceUpdate(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final id = data['id'];
    final newStatus = data['status'];
    if (id is! int || newStatus is! String) return false;
    if (_devices.isEmpty) return false;

    final lower = newStatus.toLowerCase();
    var changed = false;
    final updated = <Device>[];
    for (final d in _devices) {
      if (d.id == id && d.status != lower) {
        updated.add(_withStatus(d, lower));
        changed = true;
      } else {
        updated.add(d);
      }
    }
    if (!changed) return false;
    _devices = updated;
    return true;
  }

  /// Merge a per-room aggregate payload. The backend fans this out once
  /// per `all-on` / `all-off` bulk operation; we use it as authoritative
  /// for the room card so the power chart doesn't wait for every
  /// individual `device_update` to settle.
  bool _applyRoomPower(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final room = data['room'];
    if (room is! String || room.isEmpty) return false;
    final totalDevices = _asInt(data['total_devices']);
    final activeDevices = _asInt(data['active_devices']);
    final totalPower = _asDouble(data['total_power']);
    if (totalDevices == null || activeDevices == null || totalPower == null) {
      return false;
    }

    final incoming = RoomSummary(
      room: room,
      totalDevices: totalDevices,
      activeDevices: activeDevices,
      totalPower: totalPower,
    );

    final overview = _overview;
    if (overview == null) return false;
    final rooms = [...overview.rooms];
    var replaced = false;
    for (var i = 0; i < rooms.length; i++) {
      if (rooms[i].room == room) {
        if (_roomsEqual(rooms[i], incoming)) return false;
        rooms[i] = incoming;
        replaced = true;
        break;
      }
    }
    if (!replaced) {
      rooms.add(incoming);
      rooms.sort((a, b) => a.room.compareTo(b.room));
    }

    _overview = OverviewStats(
      totalDevices: overview.totalDevices,
      activeDevices: overview.activeDevices,
      totalPower: overview.totalPower,
      rooms: rooms,
      activeAlerts: activeAlerts,
    );
    return true;
  }

  bool _roomsEqual(RoomSummary a, RoomSummary b) =>
      a.room == b.room &&
      a.totalDevices == b.totalDevices &&
      a.activeDevices == b.activeDevices &&
      (a.totalPower - b.totalPower).abs() < 0.0001;

  bool _applyTick(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    var changed = false;
    final totalPower = _asDouble(data['total_power']);
    if (totalPower != null) {
      _samples.add(totalPower);
      final cur = _overview;
      if (cur != null && (cur.totalPower - totalPower).abs() > 0.0001) {
        _overview = OverviewStats(
          totalDevices: cur.totalDevices,
          activeDevices: cur.activeDevices,
          totalPower: totalPower,
          rooms: cur.rooms,
          activeAlerts: cur.activeAlerts,
        );
        changed = true;
      }
    }
    // Optionally update individual devices' power if provided.
    final devices = data['devices'];
    if (devices is List) {
      final updates = <int, double>{};
      for (final raw in devices) {
        if (raw is! Map) continue;
        final m = raw.cast<String, dynamic>();
        final id = _asInt(m['id']);
        final p = _asDouble(m['power_consumption']);
        if (id != null && p != null) updates[id] = p;
      }
      if (updates.isNotEmpty && _devices.isNotEmpty) {
        var deviceChanged = false;
        _devices = _devices.map((d) {
          if (updates.containsKey(d.id)) {
            if ((d.powerConsumption - updates[d.id]!).abs() > 0.0001) {
              deviceChanged = true;
              return Device(
                id: d.id,
                name: d.name,
                room: d.room,
                type: d.type,
                status: d.status,
                powerConsumption: updates[d.id]!,
                lastChanged: DateTime.now(),
              );
            }
          }
          return d;
        }).toList();
        if (deviceChanged) changed = true;
      }
    }
    return changed;
  }

  bool _applyAlertCreated(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    Alert incoming;
    try {
      incoming = Alert.fromJson(data);
    } catch (_) {
      return false;
    }
    // Replace if a stale copy already exists (server re-broadcast).
    final next = <Alert>[];
    var replaced = false;
    for (final a in _alerts) {
      if (a.id == incoming.id) {
        next.add(incoming);
        replaced = true;
      } else {
        next.add(a);
      }
    }
    if (!replaced) next.insert(0, incoming);
    if (_listEqualById(_alerts, next)) return false;
    _alerts = next;
    return true;
  }

  bool _applyAlertUpdated(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final id = _asInt(data['id']);
    if (id == null) return false;
    Alert? incoming;
    try {
      incoming = Alert.fromJson(data);
    } catch (_) {
      return false;
    }
    return _mergeAlertById(incoming);
  }

  bool _applyAlertAcknowledged(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final id = _asInt(data['id']);
    if (id == null) return false;
    final idx = _alerts.indexWhere((a) => a.id == id);
    if (idx < 0) return false;
    final current = _alerts[idx];
    if (current.acknowledged) return false;
    final ackBy = (data['acknowledged_by'] as String?) ??
        current.acknowledgedBy;
    final ackAt = _parseDate(data['acknowledged_at']) ??
        DateTime.now();
    final updated = current.copyWith(
      acknowledged: true,
      status: 'acknowledged',
      acknowledgedBy: ackBy,
      acknowledgedAt: ackAt,
    );
    final next = [..._alerts];
    next[idx] = updated;
    _alerts = next;
    return true;
  }

  bool _applyAlertResolved(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final id = _asInt(data['id']);
    if (id == null) return false;
    final idx = _alerts.indexWhere((a) => a.id == id);
    if (idx < 0) return false;
    final current = _alerts[idx];
    if (current.status == 'resolved') return false;
    final resolvedAt =
        _parseDate(data['resolved_at']) ?? DateTime.now();
    final updated = current.copyWith(
      status: 'resolved',
      resolvedAt: resolvedAt,
      acknowledged: true,
    );
    final next = [..._alerts];
    next[idx] = updated;
    _alerts = next;
    return true;
  }

  bool _applyAlertDismissed(Map<String, dynamic> payload) {
    final data = payload['data'];
    if (data is! Map<String, dynamic>) return false;
    final id = _asInt(data['id']);
    if (id == null) return false;
    final idx = _alerts.indexWhere((a) => a.id == id);
    if (idx < 0) return false;
    final current = _alerts[idx];
    if (current.dismissed) return false;
    final updated = current.copyWith(
      dismissed: true,
      status: 'dismissed',
    );
    final next = [..._alerts];
    next[idx] = updated;
    _alerts = next;
    return true;
  }

  bool _mergeAlertById(Alert incoming) {
    final idx = _alerts.indexWhere((a) => a.id == incoming.id);
    if (idx < 0) {
      _alerts = [incoming, ..._alerts];
      return true;
    }
    final existing = _alerts[idx];
    if (_alertEqual(existing, incoming)) return false;
    final next = [..._alerts];
    next[idx] = incoming;
    _alerts = next;
    return true;
  }

  bool _alertEqual(Alert a, Alert b) =>
      a.id == b.id &&
      a.status == b.status &&
      a.acknowledged == b.acknowledged &&
      a.dismissed == b.dismissed &&
      a.acknowledgedBy == b.acknowledgedBy &&
      a.message == b.message &&
      a.severity == b.severity;

  bool _listEqualById(List<Alert> a, List<Alert> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i].id != b[i].id) return false;
    }
    return true;
  }

  // ----------------------------------------------------------- helpers

  static int? _asInt(Object? v) {
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v);
    return null;
  }

  static double? _asDouble(Object? v) {
    if (v is double) return v;
    if (v is int) return v.toDouble();
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v);
    return null;
  }

  static DateTime? _parseDate(Object? v) {
    if (v is String && v.isNotEmpty) {
      try {
        return DateTime.parse(v);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _ticker?.cancel();
    _sub?.cancel();
    _statusSub?.cancel();
    _samples.close();
    super.dispose();
  }
}