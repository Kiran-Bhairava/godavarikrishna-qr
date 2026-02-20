from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, extract
from typing import List, Optional
from datetime import datetime, timedelta
import qrcode
import io
import logging

from database import get_db
from auth import get_current_user
from models import User, QRCode, QRScan, Branch
from schemas import QRCodeCreate, QRCodeUpdate, QRCodeResponse, QRAnalytics, QRScanResponse
from config import settings
from datetime import datetime, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Query, Depends, HTTPException, status
from sqlalchemy import select, func, case, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/qr", tags=["QR Codes"])
logger = logging.getLogger(__name__)

# ============================================
# LIST ALL QR CODES (OPTIMIZED)
# ============================================
@router.get("", response_model=List[QRCodeResponse])
async def list_qr_codes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all QR codes with scan counts and branch name.
    OPTIMIZED: Single query with JOIN + GROUP BY.
    """
    try:
        # Build base query
        query = (
            select(
                QRCode,
                func.coalesce(func.count(QRScan.id), 0).label("scan_count"),
                Branch.name.label("branch_name")
            )
            .join(Branch, Branch.id == QRCode.branch_id)
            .outerjoin(QRScan, QRCode.id == QRScan.qr_code_id)
        )
        
        # âœ… Super admins see ALL QR codes, regular users see only their own
        if not current_user.is_super_admin:
            query = query.where(QRCode.created_by == current_user.id)
        
        # Apply ordering and pagination
        query = (
            query.group_by(QRCode.id, Branch.name)
            .order_by(QRCode.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(query)

        rows = result.all()
        response_list = []

        for qr, scan_count, branch_name in rows:
            qr_dict = {
                "id": qr.id,
                "code": qr.code,
                "name": branch_name,  # ✅ Using branch name as QR name
                "target_url": qr.target_url,
                "branch_id": qr.branch_id,
                "is_active": qr.is_active,
                "created_at": qr.created_at,
                "updated_at": qr.updated_at,
                "created_by": qr.created_by,
                "scan_count": scan_count
            }
            response_list.append(qr_dict)

        logger.info(f"Listed {len(response_list)} QR codes for user {current_user.id}")
        return response_list

    except Exception as e:
        logger.error(f"Error listing QR codes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch QR codes")


# ============================================
# CREATE QR CODE
# ============================================
@router.post("", response_model=QRCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_qr_code(
    qr_data: QRCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new QR code.
    """
    try:
        # Check if code already exists
        result = await db.execute(
            select(QRCode).where(QRCode.code == qr_data.code)
        )
        existing_qr = result.scalar_one_or_none()
        
        if existing_qr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"QR code with code '{qr_data.code}' already exists"
            )
        
        # Create new QR code
        new_qr = QRCode(
            code=qr_data.code,
            target_url=qr_data.target_url,
            branch_id=qr_data.branch_id,
            created_by=current_user.id,
            is_active=True
        )
        
        db.add(new_qr)
        await db.commit()
        await db.refresh(new_qr)
        
        logger.info(f"Created QR code: {qr_data.code} by user {current_user.id}")
        
        # Set scan_count as attribute for response model
        new_qr.scan_count = 0
        
        return new_qr
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating QR code: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create QR code")


# ============================================
# GET SINGLE QR CODE (OPTIMIZED)
# ============================================
@router.get("/{qr_id}", response_model=QRCodeResponse)
async def get_qr_code(
    qr_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single QR code by ID with scan count and branch name.
    OPTIMIZED: Single query with JOIN + GROUP BY.
    """
    try:
        result = await db.execute(
            select(
                QRCode,
                func.coalesce(func.count(QRScan.id), 0).label("scan_count"),
            )
            .join(Branch, Branch.id == QRCode.branch_id)
            .outerjoin(QRScan, QRCode.id == QRScan.qr_code_id)
            .where(QRCode.id == qr_id)
            .group_by(QRCode.id, Branch.name)
        )

        row = result.one_or_none()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )

        qr_code, scan_count = row
        
        # âœ… Permission check: super admins can view all, regular users only their own
        if not current_user.is_super_admin and qr_code.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view QR codes you created"
            )

        return {
            "id": qr_code.id,
            "code": qr_code.code,
            "target_url": qr_code.target_url,
            "branch_id": qr_code.branch_id,
            "is_active": qr_code.is_active,
            "created_at": qr_code.created_at,
            "updated_at": qr_code.updated_at,
            "created_by": qr_code.created_by,
            "scan_count": scan_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching QR code {qr_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch QR code")


# ============================================
# UPDATE QR CODE
# ============================================
@router.put("/{qr_id}", response_model=QRCodeResponse)
async def update_qr_code(
    qr_id: int,
    qr_update: QRCodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a QR code's target URL or active status.
    """
    try:
        result = await db.execute(
            select(QRCode).where(QRCode.id == qr_id)
        )
        qr_code = result.scalar_one_or_none()
        
        if not qr_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )
        
        # âœ… Permission check: super admins can edit all, regular users only their own
        if not current_user.is_super_admin and qr_code.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only modify QR codes you created"
            )
        
        # Update fields
        if qr_update.target_url is not None:
            qr_code.target_url = qr_update.target_url
        
        if qr_update.is_active is not None:
            qr_code.is_active = qr_update.is_active
        
        qr_code.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(qr_code)
        
        # Get scan count
        scan_count_result = await db.execute(
            select(func.count(QRScan.id)).where(QRScan.qr_code_id == qr_code.id)
        )
        scan_count = scan_count_result.scalar()
        
        # Set scan_count as attribute for response model
        qr_code.scan_count = scan_count
        
        logger.info(f"Updated QR code {qr_id} by user {current_user.id}")
        
        return qr_code
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating QR code {qr_id}: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update QR code")


# ============================================
# DELETE QR CODE
# ============================================
@router.delete("/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qr_code(
    qr_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a QR code (also deletes all associated scans due to cascade).
    """
    try:
        result = await db.execute(
            select(QRCode).where(QRCode.id == qr_id)
        )
        qr_code = result.scalar_one_or_none()
        
        if not qr_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )
        
        # âœ… Permission check: super admins can delete all, regular users only their own
        if not current_user.is_super_admin and qr_code.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete QR codes you created"
            )
        
        await db.delete(qr_code)
        await db.commit()
        
        logger.info(f"Deleted QR code {qr_id} by user {current_user.id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting QR code {qr_id}: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete QR code")


# ============================================
# GET QR CODE IMAGE (PNG)
# ============================================
@router.get("/{qr_id}/image")
async def get_qr_image(
    qr_id: int,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate QR code image (view or download).
    Downloaded file will use Branch name as filename.
    """
    try:
        # Fetch QR code + Branch name
        result = await db.execute(
            select(QRCode, Branch.name)
            .join(Branch, Branch.id == QRCode.branch_id)
            .where(QRCode.id == qr_id)
        )

        row = result.one_or_none()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )

        qr_code, branch_name = row
        
        # âœ… Permission check: super admins can download all, regular users only their own
        if not current_user.is_super_admin and qr_code.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only download QR codes you created"
            )

        # Build redirect URL
        redirect_url = f"{settings.BASE_URL}/r/{qr_code.code}"

        # Generate QR image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        qr.add_data(redirect_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        headers = {
            # 🔥 CRITICAL: Allow frontend JS to read filename header
            "Access-Control-Expose-Headers": "Content-Disposition"
        }

        # If download requested, use branch name as filename
        if download:
            safe_branch_name = "".join(
                c for c in branch_name if c.isalnum() or c in (" ", "-", "_")
            ).rstrip().replace(" ", "_")

            if not safe_branch_name:
                safe_branch_name = f"qr_{qr_code.id}"

            headers["Content-Disposition"] = f'attachment; filename="{safe_branch_name}.png"'

        return Response(
            content=buffer.getvalue(),
            media_type="image/png",
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating QR image {qr_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate QR image")


@router.get("/{qr_id}/analytics", response_model=QRAnalytics)
async def get_qr_analytics(
    qr_id: int,
    time_range: Optional[str] = Query(
        "30days",
        regex="^(today|7days|30days|90days|year|all)$"
    ),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    timezone: str = Query("Asia/Kolkata"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),  # Increased default to 50
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get QR analytics with LOCAL TIMEZONE support and paginated scans.
    Now returns ALL scans matching filters with proper pagination.
    """

    try:
        # Validate timezone
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid timezone")

        # Verify QR ownership
        result = await db.execute(
            select(QRCode).where(
                QRCode.id == qr_id
            )
        )
        qr_code = result.scalar_one_or_none()

        if not qr_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR code not found"
            )

        # LOCAL NOW → convert to UTC for DB queries
        local_now = datetime.now(tz)
        utc_now = local_now.astimezone(ZoneInfo("UTC"))

        # Resolve date range (LOCAL TIME)
        if start_date and end_date:
            local_start = datetime.combine(start_date, time.min, tzinfo=tz)
            local_end = datetime.combine(end_date, time.max, tzinfo=tz)
        else:
            if time_range == "today":
                local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_range == "7days":
                local_start = local_now - timedelta(days=7)
            elif time_range == "30days":
                local_start = local_now - timedelta(days=30)
            elif time_range == "90days":
                local_start = local_now - timedelta(days=90)
            elif time_range == "year":
                local_start = local_now - timedelta(days=365)
            else:  # all
                local_start = None

            local_end = local_now

        # Convert LOCAL → UTC for DB filtering
        utc_start = local_start.astimezone(ZoneInfo("UTC")) if local_start else None
        utc_end = local_end.astimezone(ZoneInfo("UTC")) if local_end else None

        # Shared filters
        filters = [QRScan.qr_code_id == qr_id]

        if utc_start:
            filters.append(QRScan.scanned_at >= utc_start)
        if utc_end:
            filters.append(QRScan.scanned_at <= utc_end)

        # COUNTS
        local_today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        utc_today_start = local_today_start.astimezone(ZoneInfo("UTC"))

        counts_result = await db.execute(
            select(
                func.count(QRScan.id).label("total_scans"),
                func.sum(case((QRScan.scanned_at >= utc_today_start, 1), else_=0)).label("scans_today"),
                func.sum(case((QRScan.scanned_at >= utc_now - timedelta(days=7), 1), else_=0)).label("scans_week"),
                func.sum(case((QRScan.scanned_at >= utc_now - timedelta(days=30), 1), else_=0)).label("scans_month"),
            ).where(and_(*filters))
        )
        counts = counts_result.one()

        total_scans = counts.total_scans or 0
        scans_today = counts.scans_today or 0
        scans_this_week = counts.scans_week or 0
        scans_this_month = counts.scans_month or 0

        # DEVICE BREAKDOWN
        device_result = await db.execute(
            select(
                QRScan.device_type,
                func.count(QRScan.id).label("count")
            )
            .where(and_(*filters))
            .group_by(QRScan.device_type)
        )

        device_counts = {row.device_type: row.count for row in device_result.all()}

        mobile = device_counts.get("Mobile", 0)
        desktop = device_counts.get("Desktop", 0)
        tablet = device_counts.get("Tablet", 0)

        device_breakdown = {
            "mobile": mobile,
            "desktop": desktop,
            "tablet": tablet
        }

        mobile_percentage = round((mobile / total_scans * 100) if total_scans else 0, 1)

        # LOCATION
        city_result = await db.execute(
            select(
                QRScan.city,
                QRScan.country,
                func.count(QRScan.id).label("count")
            )
            .where(and_(*filters, QRScan.city.isnot(None)))
            .group_by(QRScan.city, QRScan.country)
            .order_by(func.count(QRScan.id).desc())
            .limit(5)
        )

        top_cities = [
            {"country": r.country, "city": r.city, "count": r.count}
            for r in city_result.all()
        ]

        country_result = await db.execute(
            select(
                QRScan.country,
                func.count(QRScan.id).label("count")
            )
            .where(and_(*filters, QRScan.country.isnot(None)))
            .group_by(QRScan.country)
            .order_by(func.count(QRScan.id).desc())
            .limit(5)
        )

        top_countries = [
            {"country": r.country, "city": "", "count": r.count}
            for r in country_result.all()
        ]

        # HOURLY BREAKDOWN (LOCAL HOURS)
        hourly_result = await db.execute(
            select(QRScan.scanned_at)
            .where(and_(*filters))
        )
        
        all_scans = hourly_result.scalars().all()
        
        hourly_counts = {}
        for scan_time in all_scans:
            local_time = scan_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            hour = local_time.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        hourly_breakdown = [
            {"hour": h, "count": hourly_counts.get(h, 0)} 
            for h in range(24)
        ]
        
        peak_hour = max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else None

        # PAGINATED SCANS - OPTIMIZED
        # Count total filtered scans
        filtered_count_result = await db.execute(
            select(func.count(QRScan.id)).where(and_(*filters))
        )
        filtered_total = filtered_count_result.scalar() or 0
        
        # Calculate pagination
        offset = (page - 1) * page_size
        total_pages = (filtered_total + page_size - 1) // page_size if filtered_total > 0 else 1
        
        # Fetch paginated scans
        scans_result = await db.execute(
            select(QRScan)
            .where(and_(*filters))
            .order_by(QRScan.scanned_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        scans = scans_result.scalars().all()

        return {
            "qr_code_id": qr_id,
            "total_scans": total_scans,
            "scans_today": scans_today,
            "scans_this_week": scans_this_week,
            "scans_this_month": scans_this_month,
            "device_breakdown": device_breakdown,
            "mobile_percentage": mobile_percentage,
            "top_countries": top_countries,
            "top_cities": top_cities,
            "peak_hour": peak_hour,
            "hourly_breakdown": hourly_breakdown,
            "recent_scans": scans,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "filtered_scan_count": filtered_total,
            "new_vs_returning": {
                "new_users": 0,
                "returning_users": 0
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error for QR {qr_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate analytics")