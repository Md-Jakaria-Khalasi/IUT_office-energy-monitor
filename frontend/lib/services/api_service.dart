import 'dart:async';

import 'package:http/http.dart' as http;
import 'dart:convert';

import '../models/device.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);
  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiService {
  final String baseUrl;
  final http.Client _client;

  ApiService({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  Uri _u(String path) => Uri.parse('$baseUrl/api/v1$path');

  Map<String, dynamic> _decode(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    throw ApiException(res.statusCode, res.body);
  }

  List<dynamic> _decodeList(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return jsonDecode(res.body) as List<dynamic>;
    }
    throw ApiException(res.statusCode, res.body);
  }

  Future<OverviewStats> fetchOverview() async {
    final res = await _client.get(_u('/rooms/overview'));
    return OverviewStats.fromJson(_decode(res));
  }

  Future<List<RoomSummary>> fetchRooms() async {
    final res = await _client.get(_u('/rooms'));
    return _decodeList(res)
        .map((e) => RoomSummary.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Device>> fetchDevices({String? room}) async {
    final path = room == null ? '/devices' : '/devices?room=$room';
    final res = await _client.get(_u(path));
    return _decodeList(res)
        .map((e) => Device.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Device>> fetchAllDevices() async => fetchDevices();

  Future<Device> setDeviceStatus(int id, String status) async {
    final res = await _client.patch(
      _u('/devices/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'status': status}),
    );
    return Device.fromJson(_decode(res));
  }

  Future<List<Alert>> fetchAlerts() async {
    final res = await _client.get(_u('/alerts'));
    return _decodeList(res)
        .map((e) => Alert.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<Activity>> fetchActivities({String? room, int limit = 20}) async {
    final qs = room == null
        ? '?limit=$limit'
        : '?limit=$limit&room=${Uri.encodeQueryComponent(room)}';
    final res = await _client.get(_u('/activities$qs'));
    return _decodeList(res)
        .map((e) => Activity.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}