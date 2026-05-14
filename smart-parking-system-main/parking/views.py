from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework import status

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Count
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal

from .serializers import VehicleEntrySerializer, VehicleExitSerializer, SlotDisplaySerializer, ReservationSerializer, VehicleTrackSerializer, SlotStatusUpdateSerializer
from .models import ParkingSlot, VehicleLog, Reservation,Camera
from .pathfinding import astar, get_road_cell_next_to_slot
from .permissions import IsCameraNode, IsOwnerOrAdmin
from .grid import GARAGE_GRID, SLOT_COORDINATES

import numpy as np
import logging
import json
import uuid
import math
import re

ENTRANCE = (0, 1)   # ENTER cell
SIMILAR_COLORS = {
    'black':  ['gray', 'blue', 'brown'],
    'silver': ['gray', 'white', 'blue'],
    'gray':   ['silver', 'black', 'blue'],
    'white':  ['silver', 'gray'],
    'blue':   ['black', 'gray', 'silver'],
    'brown':  ['beige', 'black'],
    'beige':  ['brown', 'white', 'yellow'],
    'yellow': ['beige', 'brown'],
    'red':    ['red'],
    'green':  ['green'],
}

class VehicleEntryAPIView(APIView):
    permission_classes = [IsCameraNode]
    
    def post(self, request, *args, **kwargs):
        serializer = VehicleEntrySerializer(data=request.data)
        
        if serializer.is_valid():
            v_data = serializer.validated_data
            plate = v_data['license_plate']
            
            # --- 1. التحقق من الدخول المزدوج (Double Entry Check) ---
            # إذا كانت السيارة مسجلة أنها بالداخل بالفعل، نحدث بياناتها ولا ننشئ سجلاً جديداً
            existing_log = VehicleLog.objects.filter(license_plate=plate, is_inside=True).first()
            if existing_log:
                return Response({
                    "status": "warning",
                    "message": "السيارة مسجلة بالداخل بالفعل (دخول مزدوج)",
                    "log_id": existing_log.id
                }, status=200)

            # --- 2. البحث عن حجز نشط (Reservation Check) ---
            now = timezone.now()
            reservation = Reservation.objects.filter(
                license_plate=plate,
                is_active=True,
                start_time__lte=now,
                end_time__gte=now
            ).select_related('slot').first()

            target_slot = None
            
            # استخدام Atomic Transaction لضمان سلامة البيانات عند تغيير حالة الـ Slot
            with transaction.atomic():
                if reservation:
                    target_slot = reservation.slot
                    identified_user = reservation.user.username
                else:
                    # --- 3. التعامل مع الزوار (Guest Allocation) ---
                    # اختيار أول مكان متاح (Available) وتخصيصه فوراً
                    target_slot = ParkingSlot.objects.filter(status='available').first()
                    identified_user = "Guest"

                # 4. تحديث حالة المكان المحجوز/المخصص
                if target_slot:
                    target_slot.status = 'occupied' # أو reserved مؤقتاً
                    target_slot.save()

                # 5. حفظ سجل الدخول
                vehicle_log = VehicleLog.objects.create(
                    license_plate=plate,
                    entry_image=v_data.get('entry_image'),
                    car_embedding=v_data.get('car_embedding'),
                    car_color=v_data.get('car_color', 'unknown'),
                    is_inside=True,
                    slot=target_slot,
                    last_camera_id=1
                )

            return Response({
                "status": "success",
                "log_id": vehicle_log.id,
                "identified_user": identified_user,
                "target_slot": target_slot.slot_number if target_slot else "No Slots Available",
                "message": "تم تسجيل الدخول وتخصيص مكان"
            }, status=201)
            
        return Response(serializer.errors, status=400)

class VehicleExitAPIView(APIView):
    """
    إغلاق سجل السيارة وحساب التكلفة عند بوابة الخروج.
    ملاحظة: الماشين هي المسؤولة عن تحديث حالة الـ Slot إلى available 
    عبر BulkSlotUpdateAPIView، لذا لن نقوم بتغيير حالة السلوت هنا يدوياً.
    """
    permission_classes = [IsCameraNode]

    def post(self, request):
        serializer = VehicleExitSerializer(data=request.data)
        if serializer.is_valid():
            plate = serializer.validated_data['license_plate']
            image = serializer.validated_data.get('exit_image')

            # البحث عن آخر سجل دخول للسيارة لم يغلق بعد
            # الفلتر بـ is_inside=True يضمن أننا نتعامل مع سيارة موجودة فعلياً
            log = VehicleLog.objects.filter(
                license_plate=plate, 
                is_inside=True
            ).select_related('slot').last()

            if not log:
                return Response({
                    "error": "Vehicle not found in garage or already exited"
                }, status=status.HTTP_404_NOT_FOUND)

            with transaction.atomic():
                now = timezone.now()
                log.exit_time = now
                log.exit_image = image
                log.is_inside = False  # إخراج السيارة من نظام التتبع فوراً
                
                # حساب الساعات بطريقة احترافية (أي جزء من الساعة = ساعة كاملة)
                duration = now - log.entry_time
                hours = math.ceil(duration.total_seconds() / 3600)
                if hours < 1: hours = 1
                
                # حساب التكلفة (25 جنيهاً للساعة)
                log.total_fee = Decimal(hours) * Decimal(25.00)
                log.is_paid = True 
                log.save()

                # --- خطوة إضافية احترافية ---
                # إنهاء أي حجز نشط لهذه اللوحة لضمان نظافة البيانات
                Reservation.objects.filter(
                    license_plate=plate, 
                    is_active=True
                ).update(is_active=False)

            return Response({
                "status": "success",
                "message": "Vehicle exit recorded successfully",
                "summary": {
                    "plate": plate,
                    "entry_time": log.entry_time.strftime('%Y-%m-%d %H:%M'),
                    "exit_time": log.exit_time.strftime('%Y-%m-%d %H:%M'),
                    "duration_hours": hours,
                    "total_fee": float(log.total_fee)
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BulkSlotUpdateAPIView(APIView):
    """
    تحديث جماعي لحالة الركنات من كاميرات الماشين ليرنينج.
    تطبق منطق الربط الذكي: الكاميرا تكسر الحجز لو وجدت سيارة، 
    وتحترم الحجز لو الركنة فارغة.
    """
    permission_classes = [IsCameraNode]

    def post(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({"error": "Expected a list of slots"}, status=400)

        updated_slots = []
        for item in data:
            slot_no = item.get('slot_id')
            is_occupied = item.get('is_occupied')

            if is_occupied:
                # 1. الماشين شافت عربية: حدث الحالة فوراً مهما كانت الحالة السابقة
                # هنا بنشيل الـ .exclude(status='reserved') لأن الواقع بيقول إن فيه عربية ركنت
                count = ParkingSlot.objects.filter(slot_number=slot_no).update(status='occupied')
            else:
                # 2. الماشين شافت الركنة فاضية: 
                # رجعها available "فقط" لو مكنتش محجوزة (reserved)
                # عشان لو حد حاجز لسه مجاش، الماشين ما تفتحهاش لحد تاني
                count = ParkingSlot.objects.filter(
                    slot_number=slot_no
                ).exclude(status='reserved').update(status='available')

            if count > 0:
                updated_slots.append(slot_no)

        return Response({
            "status": "success", 
            "updated_slots": updated_slots,
            "message": "Real-time sync completed with smart reservation protection."
        })

class ParkingStatusAPIView(APIView):
    """
    تم تغيير الصلاحية من IsAdminUser لـ IsAuthenticated
    ليتمكن المستخدم العادي من رؤية ملخص الجراج في التطبيق.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = ParkingSlot.objects.values('status').annotate(total=Count('status'))
        summary = {
            "total_slots": ParkingSlot.objects.count(),
            "available": 0, "occupied": 0, "reserved": 0
        }
        for item in stats:
            if item['status'] in summary:
                summary[item['status']] = item['total']
        return Response(summary)

class ParkingSlotListAPIView(ListAPIView):
    """
    عرض قائمة الركنات للمستخدمين مع تحرير تلقائي للحجوزات المنتهية.
    """
    permission_classes = [AllowAny]  # السماح للجميع برؤية قائمة الركنات
    serializer_class = SlotDisplaySerializer

    def get_queryset(self):
        # 1. تحديث الحجوزات المنتهية قبل عرض البيانات
        self._expire_old_reservations()

        # 2. جلب البيانات الأساسية
        queryset = ParkingSlot.objects.all().order_by('slot_number')

        # 3. الفلترة حسب الحالة (status) إذا وجدت
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # 4. الفلترة حسب الطابق (floor) - إضافة مطور الفلاتر
        floor_param = self.request.query_params.get("floor")
        if floor_param:
            try:
                queryset = queryset.filter(floor=int(floor_param))
            except ValueError:
                pass # لو المطور بعت قيمة غير رقمية ميعملش Crash

        return queryset

    def _expire_old_reservations(self):
        """تحرير الـ Slots المنتهية بكفاءة عالية"""
        now = timezone.now()
        print(f"--- DEBUG: Current Time is {now} ---")
        # نجيب كل الحجوزات اللي وقتها خلص ولسه active
        expired_res = Reservation.objects.filter(
            is_active=True,
            end_time__lt=now
        )

        if expired_res.exists():
            # تحديث حالة الـ Slots المرتبطة بالحجوزات دي (فقط لو كانت 'reserved')
            # بنستخدم الفلتر ده عشان لو السيارة ركنت فعلاً (occupied) ميرجعهاش available
            slot_ids = expired_res.values_list('slot_id', flat=True)
            ParkingSlot.objects.filter(
                id__in=slot_ids, 
                # status='reserved'
            ).update(status='available')

            # إغلاق الحجوزات دفعة واحدة
            expired_res.update(is_active=False)

class CreateReservationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReservationSerializer(data=request.data)
        if serializer.is_valid():
            slot = serializer.validated_data['slot']

            # ✅ شيك الأول لو في حجز منتهي على الـ Slot ده
            now = timezone.now()
            expired = Reservation.objects.filter(
                slot=slot, is_active=True, end_time__lt=now
            )
            if expired.exists():
                expired.update(is_active=False)
                slot.status = 'available'
                slot.save()

            if slot.status != 'available':
                return Response({"error": "Slot is not available"}, status=400)

            reservation = serializer.save(
                user=request.user,
                reservation_code=str(uuid.uuid4())[:8].upper()
            )
            slot.status = 'reserved'
            slot.save()
            return Response({
                "message": "Reservation successful",
                "code": reservation.reservation_code,
                "slot": slot.slot_number,
                "start_time": reservation.start_time.isoformat(),
                "end_time": reservation.end_time.isoformat(),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def navigation_view(request, slot_number: str):

    slot_number = slot_number.upper().strip()

    # ── 1. Validate slot exists ───────────────────────────────
    if slot_number not in SLOT_COORDINATES:
        return JsonResponse(
            {"error": f"Slot '{slot_number}' not found."},
            status=404
        )

    slot_row, slot_col = SLOT_COORDINATES[slot_number]

    # ── 2. Find the road cell next to this slot ───────────────
    road_stop = get_road_cell_next_to_slot(slot_row, slot_col)

    if road_stop is None:
        return JsonResponse(
            {"error": f"No accessible road cell next to '{slot_number}'."},
            status=500
        )

    # ── 3. Run A* on road cells only ─────────────────────────
    path = astar(ENTRANCE, road_stop)

    if not path:
        return JsonResponse(
            {"error": f"No path found to '{slot_number}'."},
            status=400
        )

    # ── 4. Return response ────────────────────────────────────
    return JsonResponse({
        "slot_number"  : slot_number,
        "entrance"     : {"row": ENTRANCE[0],   "col": ENTRANCE[1]},
        "road_stop"    : {"row": road_stop[0],  "col": road_stop[1]},
        "destination"  : {"row": slot_row,      "col": slot_col},
        "total_steps"  : len(path),
        "path"         : [
            {"row": r, "col": c} for r, c in path
        ],
    })

logger = logging.getLogger('tracking_logger')
class VehicleTrackingAPIView(APIView):
    """
    تتبع السيارة عبر الكاميرات الداخلية باستخدام مقارنة البصمات (Embeddings) في الذاكرة.
    بدون استخدام pgvector.
    """ 
    permission_classes = [IsCameraNode]

    def post(self, request, *args, **kwargs):
        # print("Incoming Data:", request.data)
        # ________
        incoming_data = request.data.copy()
        if 'car_embedding' in incoming_data:
            incoming_data['car_embedding'] = f"List of {len(incoming_data['car_embedding'])} elements"
        logger.debug(f"------ New Request ------\nPayload: {json.dumps(request.data, indent=2)}")
        # ________
        serializer = VehicleTrackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v_data = serializer.validated_data
        raw_camera_id = v_data['camera_id']  # القيمة: "CAM-06"
        # camera_id = v_data['camera_id']
        incoming_embedding = np.array(v_data['car_embedding'])
        color_hint = v_data.get('car_color')
        incoming_color = v_data.get('car_color', 'unknown').lower()

        extracted_id = re.findall(r'\d+', raw_camera_id)
        camera_numeric_id = int(extracted_id[0]) if extracted_id else None
        if camera_numeric_id is None:
            return Response({"error": "Invalid camera format"}, status=400)
        CAMERA_PATHS = {
            1: [1],          # بوابة الدخول
            2: [1],          # كاميرا 2 لازم تكون جاية من 1
            3: [2],          # كاميرا 3 لازم تكون جاية من 2
            4: [3, 2],       # كاميرا 4 لازم تكون جاية من 3
            5: [1, 2],       # 2,كاميرا 5 لازم تكون جاية من 1
            6: [5],          # كاميرا 6 لازم تكون جاية من 5
            7: [5, 6],          # كاميرا 7 لازم تكون جاية من 6
            8: [4, 7],       # كاميرا 8 (المخرج) ممكن تكون جاية من مسار 4 أو مسار 7
        }
        # تحديد الكاميرات السابقة المسموح بها بناءً على الخريطة
        allowed_previous_cameras = CAMERA_PATHS.get(camera_numeric_id, [])

        time_threshold = timezone.now() - timedelta(minutes=3)  

        # 1. فلترة ذكية لتقليل حجم البيانات المسحوبة (Optimization)
        queryset = VehicleLog.objects.filter(
            is_inside=True,
            status='moving',
            last_seen__gte=time_threshold,
            car_embedding__isnull=False,
            last_camera_id__in=allowed_previous_cameras
        )
        print(f"allowed_previous_cameras for camera {camera_numeric_id}: {allowed_previous_cameras}")

        # if color_hint and color_hint != 'unknown':
        #     queryset = queryset.filter(car_color=color_hint)

        logs = queryset.only('id', 'license_plate', 'car_embedding', 'car_color')
        # ________

        if not logs.exists():
            response_data = {
                "status": "debug",
                "message": "No active vehicles match the criteria"
            }
            logger.info(f"Response\nPre-Comparison Debug Info: {json.dumps(response_data, indent=2)}")
            return Response({"status": "unknown", "message": "No active vehicles match the criteria"}, status=404)

        # 2. عملية البحث عن أقرب تطابق باستخدام Cosine Similarity
        best_match = None
        max_combined_score = -1  # Cosine similarity range: [-1, 1], higher = more similar
        SIMILARITY_THRESHOLD = 0.80  # يجب أن يكون التشابه 80% أو أكثر

        # ✅ تطبيع البصمة الواردة مرة واحدة خارج الحلقة (Optimization)
        incoming_norm = np.linalg.norm(incoming_embedding)
        if incoming_norm == 0:
            return Response({"status": "error", "message": "Invalid embedding: zero vector"}, status=400)
        incoming_normalized = incoming_embedding / incoming_norm

        # 📊 قائمة لتخزين نتائج التشابه لكل سيارة
        similarity_results = []

        for log in logs:
            if log.car_embedding is None:
                continue  # تخطي السجلات اللي ما فيهاش بصمة (فاسدة) أو ما تم تحديثهاش بعد
            try:
                existing_embedding = np.array(log.car_embedding)

                # تطبيع البصمة المخزنة
                existing_norm = np.linalg.norm(existing_embedding)
                if existing_norm == 0:
                    continue  # تخطي البصمات الصفرية الفاسدة

                existing_normalized = existing_embedding / existing_norm

                # حساب Cosine Similarity = dot product of two normalized vectors
                cosine_sim = float(np.dot(incoming_normalized, existing_normalized))

                existing_color = (log.car_color or 'unknown').lower()
                color_score = 0
                if incoming_color == 'unknown' or existing_color == 'unknown':
                    color_score = 0.5  # محايد لو اللون مش معروف
                elif incoming_color == existing_color:
                    color_score = 1.0  # تطابق تام
                elif existing_color in SIMILAR_COLORS.get(incoming_color, []):
                    color_score = 0.6  # لون قريب (ممكن تعدل القيمة دي حسب التجربة)
                else:
                    color_score = 0.0  # لون مختلف تماماً    
                
                combined_score = (cosine_sim * 0.85) + (color_score * 0.15)

                similarity_results.append({
                    "license_plate": log.license_plate,
                    "combined_score": round(combined_score, 4),
                    "embedding_sim": round(cosine_sim, 4),
                    "color_match": existing_color,
                    "passed": combined_score >= SIMILARITY_THRESHOLD
                })

                if combined_score > max_combined_score:
                    max_combined_score = combined_score
                    best_match = log
            except Exception as e:
                # لو حصل أي مشكلة في تحويل نوع البيانات، كمل وموقعش السيرفر
                print(f"Error processing embedding for {log.license_plate}: {e}")
                continue
        # ترتيب النتائج تنازلياً حسب التشابه للعرض
        similarity_results.sort(key=lambda x: x["combined_score"], reverse=True)

        # 3. التحقق من عتبة الثقة (Thresholding)
        if best_match and max_combined_score >= SIMILARITY_THRESHOLD:
            camera = get_object_or_404(Camera, camera_id=raw_camera_id)
            tracking_msg = f"Vehicle {best_match.license_plate} tracked at {camera.zone_name}"
            best_match.last_camera = camera
            best_match.last_seen = timezone.now()
            assigned_slot = best_match.slot

            if assigned_slot:
                if assigned_slot.camera == camera:
                    best_match.status = 'parked'
                    assigned_slot.status = 'occupied'
                    assigned_slot.save()
                    tracking_msg = f"Vehicle reached its assigned slot area (monitored by {camera.camera_id}) and is now Parked."
                else:
                    tracking_msg = f"Vehicle tracking at {camera.zone_name}. Not at target slot yet."

            best_match.save(update_fields=['last_camera', 'last_seen', 'status'])

            # ________
            response_data = {
                "status": "success",
                "identified_plate": best_match.license_plate,
                "confidence_score": round(max_combined_score, 4),
                "color_score": round(color_score, 4),
                "current_zone": camera.zone_name,
                "message": f"Vehicle {best_match.license_plate} tracked at {camera.zone_name}",
                "tracking_msg": tracking_msg,
                # 📊 نتائج التشابه لكل المركبات المقارنة
                "all_similarity_scores": similarity_results
                }
            
            logger.info(f"Response Sent: {json.dumps(response_data, ensure_ascii=False)}")
            # ________
            return Response({
                "status": "Matched with High Confidence (>= 0.89) Omar's Algorithm",
                "identified_plate": best_match.license_plate,
                "embedding_score": round(cosine_sim, 4),
                "color_score": round(color_score, 4),
                "confidence_score": round(max_combined_score, 4),
                "current_zone": camera.zone_name,
                "message": f"Vehicle {best_match.license_plate} tracked at {camera.zone_name}",
                "tracking_msg": tracking_msg,
                "all_similarity_scores": similarity_results
            }, status=200)

        # 4. حالة الفشل في التعرف — نرجع النتائج حتى لو فشل التعرف
        #______
        response_data = {
            "status": "Not Identified",
            "message": "Vehicle detected but could not be identified with high confidence",
            "color_score": round(color_score, 4) if 'color_score' in locals() else None,
            "embedding_score": round(cosine_sim, 4) if 'cosine_sim' in locals() else None,
            "confidence_score": round(max_combined_score, 4) if 'max_combined_score' in locals() else None,
            "all_similarity_scores": similarity_results
        }
        logger.info(f"Response Sent: {json.dumps(response_data, ensure_ascii=False , indent=2)}")        
        #______


        return Response({
            "status": "Not Identified",
            "message": "Vehicle detected but could not be identified with high confidence",
            "Highest Confidence Score": round(max_combined_score, 4) if max_combined_score > -1 else None,
            "all_similarity_scores": similarity_results
        }, status=404)  

class UpdateEntryEmbeddingAPIView(APIView):
    """
    تحديث بصمة السيارة (Embedding) من المنظور الأمامي إلى المنظور العلوي
    بناءً على تتابع الكاميرات الزمني بعد الدخول مباشرة.
    """
    permission_classes = [IsCameraNode]
    # permission_classes = [all_all]

    def post(self, request, *args, **kwargs):
        # نستقبل الـ Embedding الجديد من الكاميرا العلوية (مثل CAM-02)
        new_embedding = request.data.get('car_embedding')
        camera_id = request.data.get('camera_id')

        if not new_embedding:
            return Response({"error": "No embedding provided"}, status=400)

        # 1. تحديد نافذة زمنية ضيقة جداً (آخر دقيقة مثلاً)
        # لأننا نبحث عن السيارة التي دخلت الآن وتمر تحت الكاميرا التالية
        time_limit = timezone.now() - timedelta(seconds=60)

        # 2. البحث عن آخر سيارة دخلت من بوابة الدخول (CAM-ENTRY) 
        # ولم يتم تحديث منظورها بعد (أو ما زالت في أول رحلتها)
        last_vehicle = VehicleLog.objects.filter(
            is_inside=True,
            status='moving',
            entry_time__gte=time_limit,
            # نفترض أن كاميرا الدخول ثابتة ومعروفة بـ CAM-ENTRY
            last_camera_id=1,
            car_embedding__isnull=True
        ).order_by('entry_time').first()



        if not last_vehicle:
            return Response({
                "status": "ignored",
                "message": "No recently entered vehicle found to update perspective"
            }, status=404)

        # 3. تحديث الـ Embedding بالمنظور الجديد
        # من الآن فصاعداً، الكاميرات العلوية ستتعرف عليها بسهولة
        last_vehicle.car_embedding = new_embedding
        
        # تحديث الكاميرا الحالية لـ CAM-02 مثلاً
        current_camera = Camera.objects.filter(camera_id=camera_id).first()
        if current_camera:
            last_vehicle.last_camera = current_camera
            
        last_vehicle.save(update_fields=['car_embedding', 'last_camera', 'last_seen'])

        return Response({
            "status": "success",
            "license_plate": last_vehicle.license_plate,
            "message": f"Embedding updated to top-view for vehicle {last_vehicle.license_plate}"
        }, status=200)

class UserCurrentLocationAPIView(APIView):

    """
    API مخصص لتطبيق فلاتر: يرجع مكان العربية الحالي بناءً على آخر كاميرا شافتها.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, plate_number):
        # البحث عن سجل السيارة اللي لسه جوه الجراج
        log = get_object_or_404(VehicleLog, license_plate=plate_number, is_inside=True)
        
        if not log.last_camera:
            return Response({
                "error": "Vehicle detected at entrance but not yet tracked by internal cameras."
            }, status=404)

        camera = log.last_camera
        
        return Response({
            "license_plate": log.license_plate,
            "current_position": {
                "row": camera.row,
                "col": camera.col,
                "zone": camera.zone_name
            },
            "last_seen": log.last_seen.strftime('%H:%M:%S')
        }, status=200)

class CancelReservationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(
                id=reservation_id, user=request.user
            )
        except Reservation.DoesNotExist:
            return Response({"error": "Reservation not found"}, status=404)

        if not reservation.is_active:
            return Response({"error": "Reservation is already cancelled"}, status=400)

        reservation.is_active = False
        reservation.save()

        slot = reservation.slot
        if slot.status == 'reserved':
            slot.status = 'available'
            slot.save()

        return Response({"message": "Reservation cancelled successfully"})

class ExtendReservationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reservation_id):
        try:
            reservation = Reservation.objects.get(
                id=reservation_id, user=request.user, is_active=True
            )
        except Reservation.DoesNotExist:
            return Response({"error": "Active reservation not found"}, status=404)

        now = timezone.now()
        if reservation.end_time < now:
            return Response({"error": "Reservation already expired"}, status=400)

        extend_minutes = request.data.get('extend_minutes', 30)
        try:
            extend_minutes = int(extend_minutes)
        except (ValueError, TypeError):
            return Response({"error": "Invalid extend_minutes"}, status=400)

        if extend_minutes < 1 or extend_minutes > 480:
            return Response({"error": "Extension must be between 1 and 480 minutes"}, status=400)

        from datetime import timedelta
        reservation.end_time += timedelta(minutes=extend_minutes)
        reservation.save()

        return Response({
            "message": f"Reservation extended by {extend_minutes} minutes",
            "new_end_time": reservation.end_time.isoformat(),
        })

class MyReservationsListAPIView(ListAPIView):
    """
    عرض حجوزات المستخدم (النشطة والسابقة) مع تحديث تلقائي للحالة.
    تُستخدم في واجهة Booking History و Countdown في تطبيق الموبايل.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ReservationSerializer

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()

        # 1. تحديث الحجوزات المنتهية تلقائياً (Housekeeping)
        # نبحث عن أي حجز نشط وقته انتهى
        expired_reservations = Reservation.objects.filter(
            user=user,
            is_active=True,
            end_time__lt=now
        )

        if expired_reservations.exists():
            # تحديث حالات الـ Slots المرتبطة لتصبح متاحة مرة أخرى
            slot_ids = expired_reservations.values_list('slot_id', flat=True)
            ParkingSlot.objects.filter(
                id__in=slot_ids, 
                status='reserved'
            ).update(status='available')
            
            # إنهاء حالة النشاط للحجوزات
            expired_reservations.update(is_active=False)

        # 2. جلب قائمة الحجوزات بأفضل أداء (Optimization)
        # نستخدم select_related لسحب بيانات الـ slot مع الحجز في query واحد
        # ونستخدم prefetch_related لو فيه بيانات تانية مرتبطة (مثل منطقة الباركينج)
        return Reservation.objects.filter(user=user)\
            .select_related('slot', 'slot__camera')\
            .order_by('-is_active', '-created_at')

    def list(self, request, *args, **kwargs):
        # لمسة إضافية: لو عايز تضيف بيانات في الـ header أو metadata
        response = super().list(request, *args, **kwargs)
        # مثال: إضافة إجمالي عدد الحجوزات النشطة في الرد
        active_count = Reservation.objects.filter(user=request.user, is_active=True).count()
        response.data = {
            "active_count": active_count,
            "results": response.data
        }
        return response
