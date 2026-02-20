# from fastapi import APIRouter, Depends, HTTPException, Request
# from fastapi.responses import HTMLResponse
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# import logging
# import uuid

# from database import get_db
# from models import QRCode, QRScan, SocialClick
# from utils import parse_device_info, get_location_from_ip, get_location_from_gps
# from utils_session import is_new_user_atomic  # ✅ NEW: Atomic session deduplication
# from config import settings

# router = APIRouter(tags=["Public"])
# logger = logging.getLogger(__name__)



# # ============================================
# # OLD is_new_user FUNCTION REMOVED
# # ============================================
# # The old function had race conditions.
# # Now using is_new_user_atomic() from utils_session.py
# # which uses database PRIMARY KEY constraint for 100% reliability.
# # ============================================



# @router.get("/r/{code}")
# async def redirect_qr(code: str, request: Request, db: AsyncSession = Depends(get_db)):
#     """
#     QR code redirect endpoint.
#     Session is generated server-side and injected to prevent phantom users.
#     """
#     try:
#         result = await db.execute(
#             select(QRCode.id, QRCode.target_url, QRCode.is_active, QRCode.code)
#             .where(QRCode.code == code)
#         )
#         qr_data = result.one_or_none()

#         if not qr_data:
#             raise HTTPException(status_code=404, detail="QR code not found")

#         qr_id, target_url, is_active, qr_code = qr_data

#         if not is_active:
#             raise HTTPException(status_code=410, detail="QR code deactivated")

#         separator = "&" if "?" in target_url else "?"
#         redirect_url = f"{target_url}{separator}branch={qr_code}"

#         # ✅ Generate session BEFORE HTML (fixes phantom users)
#         session_id = request.cookies.get("qr_session") or str(uuid.uuid4())

#         # ✅ HTML with guaranteed scan logging
#         html_content = f"""<!DOCTYPE html>
# <html>
# <head>
# <meta name="viewport" content="width=device-width, initial-scale=1.0">
# <title>Redirecting...</title>
# </head>
# <body>
# <script>
# const QR_ID = {qr_id};
# const TARGET_URL = "{redirect_url}";
# const API = "{settings.BASE_URL}";
# const SESSION_ID = "{session_id}";

# let scanLogged = false;

# function sendLog(lat, lon, accuracy, isUpdate) {{
#     // Prevent duplicate logs (only allow one initial + optional GPS update)
#     if (!isUpdate && scanLogged) return;
    
#     const payload = {{
#         qr_code_id: QR_ID,
#         latitude: lat,
#         longitude: lon,
#         accuracy: accuracy,
#         user_agent: navigator.userAgent,
#         session_id: SESSION_ID,
#         is_gps_update: isUpdate || false
#     }};

#     // Use sendBeacon for guaranteed delivery
#     const sent = navigator.sendBeacon(
#         `${{API}}/api/scan-log`,
#         new Blob([JSON.stringify(payload)], {{ type: 'application/json' }})
#     );
    
#     if (!sent) {{
#         // Fallback to fetch with keepalive
#         fetch(`${{API}}/api/scan-log`, {{
#             method: "POST",
#             headers: {{ "Content-Type": "application/json" }},
#             body: JSON.stringify(payload),
#             keepalive: true
#         }}).catch(() => {{}});
#     }}
    
#     if (!isUpdate) scanLogged = true;
# }}

# // ✅ ALWAYS log immediately (guarantees scan is recorded)
# sendLog(null, null, null, false);

# // ✅ Try to get GPS and update (optional, non-blocking)
# if (navigator.geolocation) {{
#     navigator.geolocation.getCurrentPosition(
#         pos => {{
#             // Update existing scan with GPS data
#             sendLog(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, true);
#         }},
#         () => {{}}, // GPS failed, but initial scan already logged
#         {{ timeout: 2000, enableHighAccuracy: false }}
#     );
# }}

# // ✅ Small delay to ensure sendBeacon fires (Safari/iOS fix)
# setTimeout(() => {{
#     window.location.replace(TARGET_URL);
# }}, 100);
# </script>
# </body>
# </html>"""

#         response = HTMLResponse(content=html_content)

#         # Set persistent cookie
#         response.set_cookie(
#             key="qr_session",
#             value=session_id,
#             max_age=60 * 60 * 24 * 365,
#             httponly=False,
#             samesite="None",
#             secure=True,
#             path="/"
#         )

#         return response

#     except Exception as e:
#         logger.error(f"Redirect error: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal error")


# @router.post("/api/scan-log")
# async def log_scan(request: Request, db: AsyncSession = Depends(get_db)):
#     """
#     Log QR code scan.
#     Handles both initial scan and GPS updates.
#     """
#     try:
#         data = await request.json()

#         qr_code_id = data.get("qr_code_id")
#         latitude = data.get("latitude")
#         longitude = data.get("longitude")
#         accuracy = data.get("accuracy")
#         user_agent = data.get("user_agent", "")
#         frontend_session = data.get("session_id", "")
#         is_gps_update = data.get("is_gps_update", False)

#         ip_address = request.client.host if request.client else None
#         cookie_session = request.cookies.get("qr_session")

#         # Session priority: frontend > cookie > new
#         if frontend_session:
#             session_id = frontend_session
#         elif cookie_session:
#             session_id = cookie_session
#         else:
#             session_id = str(uuid.uuid4())
#             logger.warning(f"No session for QR {qr_code_id}, created fallback")

#         # ✅ If this is a GPS update, try to update existing scan
#         if is_gps_update and latitude and longitude:
#             # Find most recent scan from this session for this QR
#             from datetime import datetime, timedelta
#             time_threshold = datetime.utcnow() - timedelta(minutes=5)
            
#             result = await db.execute(
#                 select(QRScan)
#                 .where(
#                     QRScan.qr_code_id == qr_code_id,
#                     QRScan.session_id == session_id,
#                     QRScan.scanned_at >= time_threshold,
#                     QRScan.latitude.is_(None)  # Only update if no GPS data yet
#                 )
#                 .order_by(QRScan.scanned_at.desc())
#                 .limit(1)
#             )
#             existing_scan = result.scalar_one_or_none()
            
#             if existing_scan:
#                 # Update existing scan with GPS data
#                 location_data = await get_location_from_gps(latitude, longitude)
                
#                 existing_scan.latitude = latitude
#                 existing_scan.longitude = longitude
#                 existing_scan.country = location_data.get("country") if location_data else existing_scan.country
#                 existing_scan.city = location_data.get("city") if location_data else existing_scan.city
#                 existing_scan.region = location_data.get("region") if location_data else existing_scan.region
                
#                 await db.commit()
                
#                 logger.info(f"✅ Updated scan #{existing_scan.id} with GPS data")
#                 return {"status": "updated", "scan_id": existing_scan.id}

#         # ✅ Create new scan record
#         device_info = parse_device_info(user_agent)
        
#         # ✅ ATOMIC check: Use database constraint to prevent phantom users
#         # This call will ALWAYS return the correct value, even with race conditions
#         is_new = await is_new_user_atomic(
#             db, 
#             session_id, 
#             action_type="qr_scan",
#             qr_code_id=qr_code_id
#         )

#         # Get location data
#         if latitude and longitude:
#             location_data = await get_location_from_gps(latitude, longitude)
#         else:
#             location_data = await get_location_from_ip(ip_address)

#         scan = QRScan(
#             qr_code_id=qr_code_id,
#             device_type=device_info["device_type"],
#             device_name=device_info["device_name"],
#             browser=device_info["browser"],
#             os=device_info["os"],
#             ip_address=ip_address,
#             country=location_data.get("country") if location_data else None,
#             city=location_data.get("city") if location_data else None,
#             region=location_data.get("region") if location_data else None,
#             session_id=session_id,
#             is_new_user=is_new,
#             user_agent=user_agent
#         )

#         db.add(scan)
#         await db.commit()
#         await db.refresh(scan)

#         logger.info(f"✅ Scan #{scan.id} recorded for QR {qr_code_id} (Session: {session_id[:8]}...)")
        
#         return {
#             "status": "success",
#             "scan_id": scan.id,
#             "is_new_user": is_new
#         }

#     except Exception as e:
#         logger.error(f"❌ Scan log error: {e}", exc_info=True)
#         await db.rollback()
#         return {"status": "error"}

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import uuid

from database import get_db
from models import QRCode, QRScan, SocialClick
from utils import parse_device_info
from utils_session import is_new_user_atomic  # ✅ NEW: Atomic session deduplication
from config import settings

router = APIRouter(tags=["Public"])
logger = logging.getLogger(__name__)



# ============================================
# OLD is_new_user FUNCTION REMOVED
# ============================================
# The old function had race conditions.
# Now using is_new_user_atomic() from utils_session.py
# which uses database PRIMARY KEY constraint for 100% reliability.
# ============================================



@router.get("/r/{code}")
async def redirect_qr(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    QR code redirect endpoint.
    Session is generated server-side and injected to prevent phantom users.
    """
    try:
        result = await db.execute(
            select(QRCode.id, QRCode.target_url, QRCode.is_active, QRCode.code)
            .where(QRCode.code == code)
        )
        qr_data = result.one_or_none()

        if not qr_data:
            raise HTTPException(status_code=404, detail="QR code not found")

        qr_id, target_url, is_active, qr_code = qr_data

        if not is_active:
            raise HTTPException(status_code=410, detail="QR code deactivated")

        separator = "&" if "?" in target_url else "?"
        redirect_url = f"{target_url}{separator}branch={qr_code}"

        # ✅ Generate session BEFORE HTML (fixes phantom users)
        session_id = request.cookies.get("qr_session") or str(uuid.uuid4())

        # ✅ HTML with guaranteed scan logging
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Redirecting...</title>
</head>
<body>
<script>
const QR_ID = {qr_id};
const TARGET_URL = "{redirect_url}";
const API = "{settings.BASE_URL}";
const SESSION_ID = "{session_id}";

let scanLogged = false;

function sendLog(lat, lon, accuracy, isUpdate) {{
    // Prevent duplicate logs (only allow one initial + optional GPS update)
    if (!isUpdate && scanLogged) return;
    
    const payload = {{
        qr_code_id: QR_ID,
        latitude: lat,
        longitude: lon,
        accuracy: accuracy,
        user_agent: navigator.userAgent,
        session_id: SESSION_ID,
        is_gps_update: isUpdate || false
    }};

    // Use sendBeacon for guaranteed delivery
    const sent = navigator.sendBeacon(
        `${{API}}/api/scan-log`,
        new Blob([JSON.stringify(payload)], {{ type: 'application/json' }})
    );
    
    if (!sent) {{
        // Fallback to fetch with keepalive
        fetch(`${{API}}/api/scan-log`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(payload),
            keepalive: true
        }}).catch(() => {{}});
    }}
    
    if (!isUpdate) scanLogged = true;
}}

// ✅ ALWAYS log immediately (guarantees scan is recorded)
sendLog(null, null, null, false);

// ✅ Try to get GPS and update (optional, non-blocking)
if (navigator.geolocation) {{
    navigator.geolocation.getCurrentPosition(
        pos => {{
            // Update existing scan with GPS data
            sendLog(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, true);
        }},
        () => {{}}, // GPS failed, but initial scan already logged
        {{ timeout: 2000, enableHighAccuracy: false }}
    );
}}

// ✅ Small delay to ensure sendBeacon fires (Safari/iOS fix)
setTimeout(() => {{
    window.location.replace(TARGET_URL);
}}, 100);
</script>
</body>
</html>"""

        response = HTMLResponse(content=html_content)

        # Set persistent cookie
        response.set_cookie(
            key="qr_session",
            value=session_id,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="None",
            secure=True,
            path="/"
        )

        return response

    except Exception as e:
        logger.error(f"Redirect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/api/scan-log")
async def log_scan(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Log QR code scan.
    Handles both initial scan and GPS updates.
    """
    try:
        data = await request.json()

        qr_code_id = data.get("qr_code_id")
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        accuracy = data.get("accuracy")
        user_agent = data.get("user_agent", "")
        frontend_session = data.get("session_id", "")
        is_gps_update = data.get("is_gps_update", False)

        ip_address = request.client.host if request.client else None
        cookie_session = request.cookies.get("qr_session")

        # Session priority: frontend > cookie > new
        if frontend_session:
            session_id = frontend_session
        elif cookie_session:
            session_id = cookie_session
        else:
            session_id = str(uuid.uuid4())
            logger.warning(f"No session for QR {qr_code_id}, created fallback")

        # ✅ If this is a GPS update, try to update existing scan
        if is_gps_update and latitude and longitude:
            # Find most recent scan from this session for this QR
            from datetime import datetime, timedelta
            time_threshold = datetime.utcnow() - timedelta(minutes=5)
            
            result = await db.execute(
                select(QRScan)
                .where(
                    QRScan.qr_code_id == qr_code_id,
                    QRScan.session_id == session_id,
                    QRScan.scanned_at >= time_threshold,
                    QRScan.latitude.is_(None)  # Only update if no GPS data yet
                )
                .order_by(QRScan.scanned_at.desc())
                .limit(1)
            )
            existing_scan = result.scalar_one_or_none()
            
            if existing_scan:
                # Update existing scan with GPS coordinates only
                existing_scan.latitude = latitude
                existing_scan.longitude = longitude
                
                await db.commit()
                
                logger.info(f"✅ Updated scan #{existing_scan.id} with GPS data")
                return {"status": "updated", "scan_id": existing_scan.id}

        # ✅ Create new scan record
        device_info = parse_device_info(user_agent)
        
        # ✅ ATOMIC check: Use database constraint to prevent phantom users
        # This call will ALWAYS return the correct value, even with race conditions
        is_new = await is_new_user_atomic(
            db, 
            session_id, 
            action_type="qr_scan",
            qr_code_id=qr_code_id
        )

        # Get location data
        # Location lookup removed - not needed

        scan = QRScan(
            qr_code_id=qr_code_id,
            device_type=device_info["device_type"],
            device_name=device_info["device_name"],
            browser=device_info["browser"],
            os=device_info["os"],
            ip_address=ip_address,
            country=None,
            city=None,
            region=None,
            session_id=session_id,
            is_new_user=is_new,
            user_agent=user_agent
        )

        db.add(scan)
        await db.commit()
        await db.refresh(scan)

        logger.info(f"✅ Scan #{scan.id} recorded for QR {qr_code_id} (Session: {session_id[:8]}...)")
        
        return {
            "status": "success",
            "scan_id": scan.id,
            "is_new_user": is_new
        }

    except Exception as e:
        logger.error(f"❌ Scan log error: {e}", exc_info=True)
        await db.rollback()
        return {"status": "error"}