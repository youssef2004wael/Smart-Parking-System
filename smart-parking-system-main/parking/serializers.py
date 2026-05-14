from rest_framework import serializers
from .models import VehicleLog, ParkingSlot, Reservation

class VehicleEntrySerializer(serializers.ModelSerializer):
    # استقبال البصمة كقائمة أرقام (للقراءة فقط من جانب السيرفر)
    car_embedding = serializers.ListField(child=serializers.FloatField(), write_only=True ,required=False,  # Add this line
        allow_null=True)
    
    class Meta:
        model = VehicleLog
        fields = ['license_plate','entry_image', 'car_embedding', 'car_color']
        extra_kwargs = {
            'car_color': {'default': 'unknown', 'required': False}
        }

    def validate_license_plate(self, value):
        # تنظيف رقم اللوحة: حروف كبيرة وبدون مسافات
        return value.strip().upper().replace(" ", "")

class VehicleExitSerializer(serializers.Serializer):
    license_plate = serializers.CharField(max_length=20)
    exit_image = serializers.ImageField()

class SlotStatusUpdateSerializer(serializers.Serializer):
    # قائمة من أرقام الـ slots وحالتها الجديدة
    slot_id = serializers.CharField() 
    is_occupied = serializers.BooleanField() # True = مشغول، False = فاضي

class SlotDisplaySerializer(serializers.ModelSerializer):
    # إضافة حقل إضافي يخبر المستخدم إذا كان المكان متاحاً للحجز أم لا
    is_available_for_booking = serializers.SerializerMethodField()

    class Meta:
        model = ParkingSlot
        fields = ['id', 'slot_number', 'status', 'slot_type', 'is_available_for_booking']

    def get_is_available_for_booking(self, obj):
        return obj.status == 'available'

class ReservationSerializer(serializers.ModelSerializer):
    # رقم اللوحة مهم جداً لأن الأمن سيعتمد عليه
    license_plate = serializers.CharField()
    slot_number = serializers.CharField(source='slot.slot_number', read_only=True)

    class Meta:
        model = Reservation
        fields = ['id', 'slot', 'slot_number', 'license_plate', 'start_time', 'end_time', 'reservation_code']
        read_only_fields = ['reservation_code']

    def validate(self, data):
        # التأكد أن الـ Slot متاح فعلاً قبل الحجز
        if data['slot'].status != 'available':
            raise serializers.ValidationError("هذا المكان لم يعد متاحاً للحجز.")
        return data

class VehicleTrackSerializer(serializers.Serializer):
    car_embedding = serializers.ListField(child=serializers.FloatField(), write_only=True)
    camera_id = serializers.CharField()
    car_color = serializers.CharField(max_length=30, required=False, default='unknown')