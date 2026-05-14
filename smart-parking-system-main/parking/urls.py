from django.urls import path
from .views import navigation_view
from .views import VehicleExitAPIView
from .views import VehicleEntryAPIView
from .views import ParkingStatusAPIView
from .views import BulkSlotUpdateAPIView
from .views import VehicleTrackingAPIView
from .views import ParkingSlotListAPIView
from .views import ExtendReservationAPIView
from .views import CancelReservationAPIView
from .views import CreateReservationAPIView
from .views import UserCurrentLocationAPIView
from .views import UpdateEntryEmbeddingAPIView
from .views import MyReservationsListAPIView

urlpatterns = [

    path('api/entry/', VehicleEntryAPIView.as_view(), name='vehicle-entry'),
    path('api/exit/', VehicleExitAPIView.as_view(), name='vehicle-exit'),
    path('api/slots/update/', BulkSlotUpdateAPIView.as_view(), name='bulk-slot-update'),
    
    path('api/status/summary/', ParkingStatusAPIView.as_view(), name='parking-summary'),
    path('api/slots/', ParkingSlotListAPIView.as_view(), name='slot-list-mobile'),
    path('api/reserve/', CreateReservationAPIView.as_view(), name='create-reservation'),
    
    path('api/navigation/<str:slot_number>/', navigation_view),
    path('api/tracking/', VehicleTrackingAPIView.as_view(), name='vehicle-tracking'),
    path('api/my-car-location/<str:plate_number>/', UserCurrentLocationAPIView.as_view()),

    path('api/update-perspective/', UpdateEntryEmbeddingAPIView.as_view(), name='update_perspective'),

    path('api/reservations/<int:reservation_id>/cancel/', CancelReservationAPIView.as_view(), name='cancel-reservation'),
    path('api/reservations/<int:reservation_id>/extend/', ExtendReservationAPIView.as_view(), name='extend-reservation'),
    path('api/my-reservations/', MyReservationsListAPIView.as_view(), name='my-reservations'),
]