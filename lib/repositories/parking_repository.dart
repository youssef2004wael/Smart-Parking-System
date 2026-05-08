import 'package:dio/dio.dart';
import '../models/parking_slot.dart';
import '../models/parking_summary.dart';
import '../models/reservation.dart';
import '../services/api_client.dart';

class ParkingRepository {
  ParkingRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Future<ParkingSummary> fetchSummary() async {
    try {
      final Response<dynamic> response =
          await _apiClient.get<dynamic>('/status/summary/');
      if (response.statusCode == 200 && response.data is Map<String, dynamic>) {
        return ParkingSummary.fromJson(response.data as Map<String, dynamic>);
      }
      throw Exception('Failed to load summary (${response.statusCode})');
    } on DioException catch (e) {
      throw Exception(
          _extractErrorMessage(e, fallback: 'Failed to load parking summary'));
    }
  }

  Future<List<ParkingSlot>> fetchSlots({String? status, String? floor}) async {
    try {
      final Response<dynamic> response = await _apiClient.get<dynamic>(
        '/slots/',
        queryParameters: <String, dynamic>{
          if (status != null && status.isNotEmpty) 'status': status,
          if (floor != null && floor.isNotEmpty) 'floor': floor,
        },
      );
      if (response.statusCode == 200 && response.data is List<dynamic>) {
        final list = response.data as List<dynamic>;
        return list
            .whereType<Map<String, dynamic>>()
            .where((json) => json['slot_type'] != 'entry' && json['slot_type'] != 'exit')
            .map(ParkingSlot.fromJson)
            .toList();
      }
      throw Exception('Failed to load slots (${response.statusCode})');
    } on DioException catch (e) {
      throw Exception(
          _extractErrorMessage(e, fallback: 'Failed to load parking slots'));
    }
  }

  Future<Map<String, dynamic>> reserveSlot({
    required int slotId,
    required String licensePlate,
    required DateTime startTime,
    required DateTime endTime,
  }) async {
    try {
      final Response<dynamic> response = await _apiClient.post<dynamic>(
        '/reserve/',
        data: {
          'slot': slotId,
          'license_plate': licensePlate,
          'start_time': startTime.toIso8601String(),
          'end_time': endTime.toIso8601String(),
        },
      );
      if (response.statusCode == 201 && response.data is Map<String, dynamic>) {
        return response.data as Map<String, dynamic>;
      }
      throw Exception('Failed to reserve slot (${response.statusCode})');
    } on DioException catch (e) {
      throw Exception(
          _extractErrorMessage(e, fallback: 'Failed to reserve slot'));
    }
  }

  Future<List<Reservation>> fetchReservations() async {
    try {
      final Response<dynamic> response =
          await _apiClient.get<dynamic>('/my-reservations/');
      if (response.statusCode == 200 && response.data is List<dynamic>) {
        final list = response.data as List<dynamic>;
        return list
            .whereType<Map<String, dynamic>>()
            .where((json) => json['slot_type'] != 'entry' && json['slot_type'] != 'exit')
            .map(Reservation.fromJson)
            .toList();
      }
      throw Exception('Failed to load reservations (${response.statusCode})');
    } on DioException catch (e) {
      throw Exception(
          _extractErrorMessage(e, fallback: 'Failed to load reservations'));
    }
  }

  Future<bool> cancelReservation(int reservationId) async {
    try {
      final Response<dynamic> response = await _apiClient.post<dynamic>(
        '/reservations/$reservationId/cancel/',
      );
      return response.statusCode == 200;
    } on DioException {
      return false;
    }
  }

  Future<bool> extendReservation(int reservationId, int extendMinutes) async {
    try {
      final Response<dynamic> response = await _apiClient.post<dynamic>(
        '/reservations/$reservationId/extend/',
        data: {'extend_minutes': extendMinutes},
      );
      return response.statusCode == 200;
    } on DioException {
      return false;
    }
  }

  /// Force backend to cleanup expired reservations and free slots
  Future<bool> cleanupExpired() async {
    try {
      final Response<dynamic> response = await _apiClient.post<dynamic>(
        '/cleanup-expired/',
      );
      return response.statusCode == 200;
    } on DioException {
      return false;
    }
  }

  String _extractErrorMessage(DioException exception, {required String fallback}) {
    final response = exception.response;
    if (response?.data is Map<String, dynamic>) {
      final data = response!.data as Map<String, dynamic>;
      if (data['detail'] != null) return data['detail'].toString();
      if (data['error'] != null) return data['error'].toString();
    }
    return fallback;
  }
}
