# ML
## Enter API

http://127.0.0.1:8000/api/entry/

POST Request
multipart/form-data

	`license_plate` -> String
	`entry_image` -> File (Image)
	`car_embedding` -> Array/List
	`car_color` -> String (Optional)
	`camera_id` -> Integer

Response

{

    `"status": "success",`
    `"log_id": 45,`
    `"identified_user": "Omar Ahmed",`
    `"target_slot": "A1",`
    `"entry_time": "2026-03-19T14:30:00Z",`
    `"message": "تم تسجيل الدخول وتخصيص مكان بنجاح"`
}

# Track API

http://127.0.0.1:8000/api/track/

POST Request
application/json

	`car_embedding` -> Array
	`camera_id` -> String / Integer
	`car_color` -> String

Response

{

    "status": "success",
    "identified_plate": "ABC 123",
    "confidence_score": 0.145,
    "current_zone": "Zone B - Ground Floor",
    "message": "Vehicle ABC 123 tracked at Zone B"
}
# Exit API

http://127.0.0.1:8000/api/exit/

POST Request
multipart/form-data

	`license_plate` -> String
	`exit_image` -> File (Image)

Response

{

    "status": "success",
    "message": "Vehicle exit recorded successfully",
    "summary": {
        "plate": "ABC 123",
        "entry_time": "2026-03-19T10:00:00Z",
        "exit_time": "2026-03-19T14:30:00Z",
        "duration_hours": 5,
        "total_fee": 125.00
    }
}
___

#### Slots Update API (Bulk)

[http://127.0.0.1:8000/api/slots/update/](https://www.google.com/search?q=http://127.0.0.1:8000/api/slots/update/) 
POST Request 
**application/json**
```
[
    {
        "slot_id": "A1",
        "is_occupied": true
    },
    {
        "slot_id": "A2",
        "is_occupied": false
    }
]
```

**Response**
```
{
    "status": "success",
    "updated_slots": ["A1", "A2"],
    "message": "Successfully updated 2 slots"
}
```

---

# Flutter User
#### Parking Summary API

http://127.0.0.1:8000/api/status/summary/
GET Request
Response
```
{
    "total_slots": 100,
    "available": 65,
    "occupied": 25,
    "reserved": 10
}
```


#### Mobile Slots List API
http://127.0.0.1:8000/api/slots/ 
http://127.0.0.1:8000/api/slots/?status=available
http://127.0.0.1:8000/api/slots/?status=occupied
http://127.0.0.1:8000/api/slots/?status=reserved
GET Request
Response
```
[
    {
        "slot_id": "A1",
        "slot_number": "A1",
        "status": "available",
        "slot_type": "standard",
        "floor": 1
    },
    {
        "slot_id": "A2",
        "slot_number": "A2",
        "status": "occupied",
        "slot_type": "disabled",
        "floor": 1
    }
]
```






#### User Registration API

[http://127.0.0.1:8000/api/auth/register/](http://127.0.0.1:8000/api/auth/register/) 
**POST Request** 

Request Body
```
{
    "username": "Omarahmed",
    "password": "Omar@ahmed",
    "password_confirm": "Omar@ahmed",
    "email": "Omarahmed@gmail.com",
    "first_name": "Omar",
    "last_name": "Ahmed"
}
```

**Response (201 Created)**
JSON
```
{
    "user": {
        "id": 4,
        "username": "Omarahmed",
        "email": "Omarahmed@gmail.com",
        "first_name": "Omar",
        "last_name": "Ahmed"
    },
    "message": "تم إنشاء الحساب بنجاح. يمكنك الآن تسجيل الدخول."
}
```

___
#### User Login API (JWT)
[http://127.0.0.1:8000/api/auth/login/](https://www.google.com/search?q=http://127.0.0.1:8000/api/auth/login/) 
**POST Request** 

Request Body
```
{
    "username": "Omarahmed",
    "password": "Omar@ahmed"
}
```

**Response (200 OK)**
JSON
```
{
    "refresh": "TOKEN_HERE...",
    "access": "TOKEN_HERE..."
}
```

#### Token Refresh API
POST Request
**Request Body:**
JSON
```
{
    "refresh": "PASTE_YOUR_REFRESH_TOKEN_HERE"
}
```

**Response (200 OK):**
JSON
```
{
    "access": "NEW_ACCESS_TOKEN_HERE"
}
```


GET

http://127.0.0.1:8000/api/my-car-location/ABC/

**Response (200 OK):**
JSON

```
{
    "license_plate": "ABC",
    "current_position": {
        "row": 0,
        "col": 0,
        "zone": "A"
    },
    "last_seen": "17:01:11"
}
```
>>>>>>> 432bf37 (Final clean backend upload)
