import time
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, async_session_maker
from models import QRCode, QRScan
from utils import parse_device_info
from utils_session import is_new_user_atomic  # ✅ Atomic session deduplication — UNCHANGED

router = APIRouter(tags=["Public"])
logger = logging.getLogger(__name__)


# ============================================
# OLD is_new_user FUNCTION REMOVED
# ============================================
# The old function had race conditions.
# Now using is_new_user_atomic() from utils_session.py
# which uses database PRIMARY KEY constraint for 100% reliability.
# ============================================


# ============================================
# ✅ NEW: In-memory QR code cache
# ============================================
# QR configs rarely change, so we avoid hitting Postgres on every single
# scan just to resolve a static (code -> target_url/branch_id) mapping.
# TTL is intentionally short so deactivations/edits still propagate quickly.
# ============================================
_QR_CACHE_TTL_SECONDS = 30
_qr_cache: dict[str, tuple[int, str, bool, Optional[int], float]] = {}
# code -> (qr_id, target_url, is_active, branch_id, cached_at)


def invalidate_qr_cache(code: Optional[str] = None) -> None:
    """
    Call this from your QR create/update/delete endpoints (routes/qr.py)
    if you want changes to take effect immediately instead of waiting
    up to _QR_CACHE_TTL_SECONDS. Safe to call with no args to clear everything.
    """
    if code is None:
        _qr_cache.clear()
    else:
        _qr_cache.pop(code, None)


async def _get_qr_data(code: str, db: AsyncSession):
    cached = _qr_cache.get(code)
    if cached and (time.monotonic() - cached[4]) < _QR_CACHE_TTL_SECONDS:
        qr_id, target_url, is_active, branch_id, _ = cached
        return qr_id, target_url, is_active, branch_id

    result = await db.execute(
        select(QRCode.id, QRCode.target_url, QRCode.is_active, QRCode.branch_id)
        .where(QRCode.code == code)
    )
    row = result.one_or_none()
    if not row:
        return None

    qr_id, target_url, is_active, branch_id = row
    _qr_cache[code] = (qr_id, target_url, is_active, branch_id, time.monotonic())
    return qr_id, target_url, is_active, branch_id


# ============================================
# ✅ NEW: Background scan logging
# ============================================
# Runs AFTER the redirect response has already been sent to the user,
# so scan logging latency never affects redirect speed. Uses its own
# fresh DB session since the request-scoped session is closed by the
# time BackgroundTasks runs.
# ============================================
async def _log_scan_background(
    qr_id: int,
    branch_id: Optional[int],
    session_id: str,
    user_agent: str,
    ip_address: Optional[str],
):
    try:
        async with async_session_maker() as db:
            # ✅ ATOMIC check — unchanged logic, still the single source of
            # truth for new-vs-returning, still backed by the DB primary
            # key constraint on session_first_seen.
            is_new = await is_new_user_atomic(
                db,
                session_id,
                action_type="qr_scan",
                branch_id=branch_id,
                qr_code_id=qr_id,
            )

            device_info = parse_device_info(user_agent)

            scan = QRScan(
                qr_code_id=qr_id,
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
                user_agent=user_agent,
            )

            db.add(scan)
            await db.commit()

            logger.info(
                f"✅ Scan recorded for QR {qr_id} (Session: {session_id[:8]}..., new={is_new})"
            )
    except Exception as e:
        # Never let a logging failure surface to the user — the redirect
        # already happened. Just log it for visibility.
        logger.error(f"❌ Background scan log error: {e}", exc_info=True)


@router.get("/r/{code}")
async def redirect_qr(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    QR code redirect endpoint.

    ✅ OPTIMIZED: redirects immediately via a server-side 302 instead of
    serving an HTML page that waits on client-side JS + sendBeacon + a
    100ms artificial delay. Scan logging happens in the background after
    the response is sent, so the user is never waiting on a DB write.
    """
    try:
        qr_data = await _get_qr_data(code, db)

        if not qr_data:
            raise HTTPException(status_code=404, detail="QR code not found")

        qr_id, target_url, is_active, branch_id = qr_data

        if not is_active:
            raise HTTPException(status_code=410, detail="QR code deactivated")

        separator = "&" if "?" in target_url else "?"
        redirect_url = f"{target_url}{separator}branch={code}"

        # ✅ Session generated/reused exactly as before
        session_id = request.cookies.get("qr_session") or str(uuid.uuid4())

        user_agent = request.headers.get("user-agent", "")
        ip_address = request.client.host if request.client else None

        # ✅ Fire-and-forget scan logging — doesn't block the redirect
        background_tasks.add_task(
            _log_scan_background,
            qr_id,
            branch_id,
            session_id,
            user_agent,
            ip_address,
        )

        response = RedirectResponse(url=redirect_url, status_code=302)

        response.set_cookie(
            key="qr_session",
            value=session_id,
            max_age=60 * 60 * 24 * 365,
            httponly=False,
            samesite="None",
            secure=True,
            path="/",
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redirect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


# ============================================
# LEGACY: kept for backward compatibility
# ============================================
# The redirect page no longer calls this (scan logging is now handled
# server-side via BackgroundTasks in /r/{code} above). Left in place
# unchanged in case any other client still posts here directly.
# ============================================
@router.post("/api/scan-log")
async def log_scan(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Log QR code scan. (Legacy endpoint — see note above.)
    """
    try:
        data = await request.json()

        qr_code_id = data.get("qr_code_id")
        user_agent = data.get("user_agent", "")
        frontend_session = data.get("session_id", "")

        ip_address = request.client.host if request.client else None
        cookie_session = request.cookies.get("qr_session")

        if cookie_session:
            session_id = cookie_session
        elif frontend_session:
            session_id = frontend_session
        else:
            session_id = str(uuid.uuid4())
            logger.warning(f"No session for QR {qr_code_id}, created fallback")

        branch_id = None
        if qr_code_id is not None:
            branch_result = await db.execute(
                select(QRCode.branch_id).where(QRCode.id == qr_code_id)
            )
            branch_id = branch_result.scalar_one_or_none()

        device_info = parse_device_info(user_agent)

        is_new = await is_new_user_atomic(
            db,
            session_id,
            action_type="qr_scan",
            branch_id=branch_id,
            qr_code_id=qr_code_id,
        )

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
            user_agent=user_agent,
        )

        db.add(scan)
        await db.commit()
        await db.refresh(scan)

        logger.info(f"✅ Scan #{scan.id} recorded for QR {qr_code_id} (Session: {session_id[:8]}...)")

        return {
            "status": "success",
            "scan_id": scan.id,
            "is_new_user": is_new,
        }

    except Exception as e:
        logger.error(f"❌ Scan log error: {e}", exc_info=True)
        await db.rollback()
        return {"status": "error"}