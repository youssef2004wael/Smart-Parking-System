import 'package:flutter/foundation.dart';
import '../models/parking_slot.dart';
import '../models/parking_summary.dart';
import '../models/reservation.dart';
import '../repositories/parking_repository.dart';
import '../services/secure_storage_service.dart';

class ParkingProvider extends ChangeNotifier {
  ParkingProvider(this._parkingRepository) {
    loadSummary();
    loadSlots();
    _loadCancelledIds();
  }

  final ParkingRepository _parkingRepository;
  final Set<int> _locallyCancelledIds = {};

  ParkingSummary? _summary;
  bool _isSummaryLoading = false;
  List<ParkingSlot> _slots = <ParkingSlot>[];
  bool _isSlotsLoading = false;
  String _selectedFloor = '1';
  String? _selectedSlotId;
  bool _isReserving = false;
  String? _reservationError;
  List<Reservation> _reservations = [];
  bool _isReservationsLoading = false;

  ParkingSummary? get summary => _summary;
  bool get isSummaryLoading => _isSummaryLoading;
  List<ParkingSlot> get slots => _slots;
  bool get isSlotsLoading => _isSlotsLoading;
  String get selectedFloor => _selectedFloor;
  String? get selectedSlotId => _selectedSlotId;
  bool get isReserving => _isReserving;
  String? get reservationError => _reservationError;
  List<Reservation> get reservations => _reservations;
  bool get isReservationsLoading => _isReservationsLoading;

  bool isLocallyCancelled(int id) => _locallyCancelledIds.contains(id);

  Future<void> _loadCancelledIds() async {
    _locallyCancelledIds.addAll(await SecureStorageService().readCancelledIds());
  }

  void setFloor(String floor) {
    _selectedFloor = ((int.tryParse(floor) ?? 0) + 1).toString();
    _selectedSlotId = null;
    loadSlots();
    notifyListeners();
  }

  Future<void> loadSummary() async {
    _isSummaryLoading = true;
    notifyListeners();
    try {
      _summary = await _parkingRepository.fetchSummary();
    } catch (e) {
      if (kDebugMode) print('Summary Error: $e');
    } finally {
      _isSummaryLoading = false;
      notifyListeners();
    }
  }

  Future<void> loadSlots({String? status}) async {
    _isSlotsLoading = true;
    notifyListeners();
    try {
      _slots = await _parkingRepository.fetchSlots(status: status, floor: _selectedFloor);
    } catch (e) {
      if (kDebugMode) print('Slots Error: $e');
    } finally {
      _isSlotsLoading = false;
      notifyListeners();
    }
  }

  void selectSlot(String slotId) {
    _selectedSlotId = _selectedSlotId == slotId ? null : slotId;
    notifyListeners();
  }

  Future<Map<String, dynamic>?> reserveSlot({
    required int slotId,
    required String licensePlate,
    required DateTime startTime,
    required DateTime endTime,
  }) async {
    _isReserving = true;
    _reservationError = null;
    notifyListeners();
    try {
      final result = await _parkingRepository.reserveSlot(
        slotId: slotId, licensePlate: licensePlate,
        startTime: startTime, endTime: endTime,
      );
      await loadSlots();
      await loadReservations(); // Fetch new reservation immediately for Countdown
      return result;
    } catch (e) {
      _reservationError = e.toString();
      if (kDebugMode) print('Reserve Error: $e');
      return null;
    } finally {
      _isReserving = false;
      notifyListeners();
    }
  }

  Future<void> loadReservations() async {
    _isReservationsLoading = true;
    notifyListeners();
    try {
      // Load all reservations, let the UI decide how to display them
      _reservations = await _parkingRepository.fetchReservations();
    } catch (e) {
      if (kDebugMode) print('Reservations Error: $e');
    } finally {
      _isReservationsLoading = false;
      notifyListeners();
    }
  }

  Future<void> handleReservationExpired() async {
    if (kDebugMode) print('Forcing cleanup of expired reservations...');
    try {
      await _parkingRepository.cleanupExpired();
      if (kDebugMode) print('Backend cleanup done');
    } catch (e) {
      if (kDebugMode) print('Cleanup call failed: $e');
    }
    await loadReservations();
    await loadSlots();
    await loadSummary();
    if (kDebugMode) print('All data refreshed');
  }

  Future<bool> cancelReservation(int reservationId) async {
    try {
      final success = await _parkingRepository.cancelReservation(reservationId);
      if (success) {
        _locallyCancelledIds.add(reservationId);
        await SecureStorageService().addCancelledId(reservationId);
        notifyListeners(); 
        await loadSlots();
        await loadSummary();
      }
      return success;
    } catch (e) {
      if (kDebugMode) print('Cancel Error: $e');
      return false;
    }
  }

  Future<bool> extendReservation(int reservationId, int extendMinutes) async {
    try {
      final success = await _parkingRepository.extendReservation(reservationId, extendMinutes);
      if (success) {
        await loadReservations();
      }
      return success;
    } catch (e) {
      if (kDebugMode) print('Extend Error: $e');
      return false;
    }
  }
}
