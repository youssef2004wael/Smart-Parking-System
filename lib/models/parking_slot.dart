class ParkingSlot {
  final String slotId;
  final String slotNumber;
  final String status;
  final String slotType;
  final int floor;
  final bool isAvailableForBooking;

  ParkingSlot({
    required this.slotId,
    required this.slotNumber,
    required this.status,
    required this.slotType,
    required this.floor,
    this.isAvailableForBooking = true,
  });

  factory ParkingSlot.fromJson(Map<String, dynamic> json) {
    return ParkingSlot(
      slotId: json['id']?.toString() ?? '',
      slotNumber: json['slot_number']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
      slotType: json['slot_type']?.toString() ?? '',
      floor: (json['floor'] as num?)?.toInt() ?? 1, // Default 1 because server removed it
      isAvailableForBooking: json['is_available_for_booking'] ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': slotId,
      'slot_number': slotNumber,
      'status': status,
      'slot_type': slotType,
      'floor': floor,
    };
  }
}