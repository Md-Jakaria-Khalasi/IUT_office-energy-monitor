class Device {
  final int id;
  final String name;
  final String room;
  final String type;
  final String status;
  final double powerConsumption;
  final DateTime lastChanged;

  const Device({
    required this.id,
    required this.name,
    required this.room,
    required this.type,
    required this.status,
    required this.powerConsumption,
    required this.lastChanged,
  });

  bool get isOn => status == 'on';

  factory Device.fromJson(Map<String, dynamic> json) {
    return Device(
      id: json['id'] as int,
      name: json['name'] as String,
      room: json['room'] as String,
      type: json['type'] as String,
      status: json['status'] as String,
      powerConsumption: (json['power_consumption'] as num).toDouble(),
      lastChanged: DateTime.parse(json['last_changed'] as String),
    );
  }
}

class RoomSummary {
  final String room;
  final int totalDevices;
  final int activeDevices;
  final double totalPower;

  const RoomSummary({
    required this.room,
    required this.totalDevices,
    required this.activeDevices,
    required this.totalPower,
  });

  factory RoomSummary.fromJson(Map<String, dynamic> json) {
    return RoomSummary(
      room: json['room'] as String,
      totalDevices: json['total_devices'] as int,
      activeDevices: json['active_devices'] as int,
      totalPower: (json['total_power'] as num).toDouble(),
    );
  }
}

class OverviewStats {
  final int totalDevices;
  final int activeDevices;
  final double totalPower;
  final List<RoomSummary> rooms;
  final int activeAlerts;

  const OverviewStats({
    required this.totalDevices,
    required this.activeDevices,
    required this.totalPower,
    required this.rooms,
    required this.activeAlerts,
  });

  factory OverviewStats.fromJson(Map<String, dynamic> json) {
    final rooms = (json['rooms'] as List<dynamic>)
        .map((r) => RoomSummary.fromJson(r as Map<String, dynamic>))
        .toList();
    return OverviewStats(
      totalDevices: json['total_devices'] as int,
      activeDevices: json['active_devices'] as int,
      totalPower: (json['total_power'] as num).toDouble(),
      rooms: rooms,
      activeAlerts: json['active_alerts'] as int,
    );
  }
}

class Alert {
  final int id;
  final String severity;

  /// Logical status as defined by the backend constants
  /// (`active` / `acknowledged` / `resolved` / `dismissed`). Older
  /// REST payloads don't include this; we default to `active`.
  final String status;

  final String message;
  final String? room;
  final DateTime createdAt;
  final bool acknowledged;
  final String? acknowledgedBy;
  final DateTime? acknowledgedAt;
  final DateTime? resolvedAt;
  final bool dismissed;

  const Alert({
    required this.id,
    required this.severity,
    required this.message,
    required this.room,
    required this.createdAt,
    required this.acknowledged,
    this.status = 'active',
    this.acknowledgedBy,
    this.acknowledgedAt,
    this.resolvedAt,
    this.dismissed = false,
  });

  /// Tolerant decoder — works with both the REST `/alerts` payload and
  /// the realtime WebSocket frames. Missing optional fields fall back to
  /// safe defaults so an old payload never crashes the merge.
  factory Alert.fromJson(Map<String, dynamic> json) {
    DateTime? parseOptDate(Object? v) {
      if (v == null) return null;
      if (v is String && v.isNotEmpty) {
        try {
          return DateTime.parse(v);
        } catch (_) {
          return null;
        }
      }
      return null;
    }

    final severity = (json['severity'] as String?) ?? 'info';
    final createdAt = parseOptDate(json['created_at']) ?? DateTime.now();
    final acknowledged = (json['acknowledged'] as bool?) ?? false;
    final acknowledgedBy = json['acknowledged_by'] as String?;
    final acknowledgedAt = parseOptDate(json['acknowledged_at']);
    final resolvedAt = parseOptDate(json['resolved_at']);
    final dismissed = (json['dismissed'] as bool?) ?? false;
    final status = (json['status'] as String?) ??
        (resolvedAt != null
            ? 'resolved'
            : acknowledged
                ? 'acknowledged'
                : dismissed
                    ? 'dismissed'
                    : 'active');

    return Alert(
      id: json['id'] as int,
      severity: severity,
      status: status,
      message: (json['message'] as String?) ?? '',
      room: json['room'] as String?,
      createdAt: createdAt,
      acknowledged: acknowledged,
      acknowledgedBy: acknowledgedBy,
      acknowledgedAt: acknowledgedAt,
      resolvedAt: resolvedAt,
      dismissed: dismissed,
    );
  }

  /// Immutable update — every realtime merge creates a new instance so
  /// `ListenableBuilder` widgets reliably rebuild.
  Alert copyWith({
    int? id,
    String? severity,
    String? status,
    String? message,
    String? room,
    DateTime? createdAt,
    bool? acknowledged,
    String? acknowledgedBy,
    DateTime? acknowledgedAt,
    DateTime? resolvedAt,
    bool? dismissed,
  }) {
    return Alert(
      id: id ?? this.id,
      severity: severity ?? this.severity,
      status: status ?? this.status,
      message: message ?? this.message,
      room: room ?? this.room,
      createdAt: createdAt ?? this.createdAt,
      acknowledged: acknowledged ?? this.acknowledged,
      acknowledgedBy: acknowledgedBy ?? this.acknowledgedBy,
      acknowledgedAt: acknowledgedAt ?? this.acknowledgedAt,
      resolvedAt: resolvedAt ?? this.resolvedAt,
      dismissed: dismissed ?? this.dismissed,
    );
  }

  /// `true` when the alert is no longer "active" in the UI sense — i.e.
  /// it's been resolved or dismissed. The ActiveAlertsCard and the
  /// overview counter both consult this to decide whether to drop it.
  bool get isClosed => status == 'resolved' || dismissed;
}

class Activity {
  final int id;
  final String deviceName;
  final String room;
  final String action;
  final String description;
  final DateTime createdAt;

  const Activity({
    required this.id,
    required this.deviceName,
    required this.room,
    required this.action,
    required this.description,
    required this.createdAt,
  });

  factory Activity.fromJson(Map<String, dynamic> json) {
    return Activity(
      id: json['id'] as int,
      deviceName: json['device_name'] as String,
      room: json['room'] as String,
      action: json['action'] as String,
      description: json['description'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}