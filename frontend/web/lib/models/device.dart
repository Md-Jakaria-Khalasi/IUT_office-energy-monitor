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
  final String message;
  final String? room;
  final DateTime createdAt;
  final bool acknowledged;

  const Alert({
    required this.id,
    required this.severity,
    required this.message,
    required this.room,
    required this.createdAt,
    required this.acknowledged,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] as int,
      severity: json['severity'] as String,
      message: json['message'] as String,
      room: json['room'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      acknowledged: json['acknowledged'] as bool,
    );
  }
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