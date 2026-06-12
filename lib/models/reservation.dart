class Reservation {
  final int id;
  final int slotId;
  final String reservationCode;
  final String slotNumber;
  final int floor;
  final String licensePlate;
  final DateTime startTime;
  final DateTime endTime;
  final bool isActive;
  final DateTime createdAt;

  Reservation({
    required this.id,
    this.slotId = 0,
    required this.reservationCode,
    required this.slotNumber,
    required this.floor,
    this.licensePlate = '',
    required this.startTime,
    required this.endTime,
    required this.isActive,
    required this.createdAt,
  });

  factory Reservation.fromJson(Map<String, dynamic> json) {
    // Handle floor being missing, String ("1") or int (1)
    int parseFloor(dynamic value) {
      if (value == null) return 1;
      if (value is int) return value;
      if (value is String) return int.tryParse(value) ?? 1;
      return 1;
    }

    // Handle created_at being missing (Backend removed it)
    DateTime parseCreatedAt(dynamic value) {
      if (value == null || value.toString().isEmpty) return DateTime.now();
      return DateTime.parse(value.toString()).toLocal();
    }

    DateTime startTime = DateTime.parse(json['start_time']).toLocal();
    DateTime endTime = DateTime.parse(json['end_time']).toLocal();

    // 🚀 Smart isActive logic: If backend doesn't provide it, we infer it from the time!
    bool isActive;
    if (json.containsKey('is_active')) {
      isActive = json['is_active'] ?? false;
    } else {
      // If end time is in the future, it's active. Otherwise, it's expired.
      isActive = DateTime.now().isBefore(endTime);
    }

    return Reservation(
      id: json['id'] ?? 0,
      slotId: json['slot'] ?? 0,
      reservationCode: json['reservation_code']?.toString() ?? '',
      slotNumber: json['slot_number'] ?? '',
      floor: parseFloor(json['floor']),
      licensePlate: json['license_plate']?.toString() ?? '',
      startTime: startTime,
      endTime: endTime,
      isActive: isActive,
      createdAt: parseCreatedAt(json['created_at']),
    );
  }

  bool get isExpired => DateTime.now().isAfter(endTime);

  Duration get remainingTime {
    final diff = endTime.difference(DateTime.now());
    return diff.isNegative ? Duration.zero : diff;
  }

  String get statusLabel {
    if (isActive && !isExpired) return 'Active';
    if (isActive && isExpired) return 'Expired';
    return 'Cancelled';
  }
}
