# from fastapi import APIRouter, Request, Depends, Query
# from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, func, and_
# from pathlib import Path
# from typing import Optional
# import logging
# import uuid

# from database import get_db
# from models import SocialClick, QRCode, QRScan
# from utils import parse_device_info, get_location_from_ip
# from utils_session import is_new_user_atomic  # ✅ NEW: Atomic session deduplication

# router = APIRouter(tags=["Social Links"])
# logger = logging.getLogger(__name__)

# TEMPLATES_DIR = Path("templates/social")


# @router.get("/social-links", response_class=HTMLResponse)
# async def social_links_page(
#     request: Request,
#     branch: Optional[str] = Query(None, description="Branch identifier from QR code")
# ):
#     """Serve the social media links page"""
#     try:
#         html_path = TEMPLATES_DIR / "index.html"
        
#         if not html_path.exists():
#             return HTMLResponse(
#                 content="<h1>Social Links page not found</h1>",
#                 status_code=404
#             )
        
#         with open(html_path, 'r', encoding='utf-8') as f:
#             html_content = f.read()
        
#         # Inject branch parameter into the page
#         if branch:
#             html_content = html_content.replace(
#                 'const BRANCH_CODE = null;',
#                 f'const BRANCH_CODE = "{branch}";'
#             )
        
#         return HTMLResponse(content=html_content)
    
#     except Exception as e:
#         logger.error(f"Error loading social links page: {str(e)}", exc_info=True)
#         return HTMLResponse(
#             content=f"<h1>Error loading page: {str(e)}</h1>",
#             status_code=500
#         )



# # ============================================
# # OLD is_new_user FUNCTION REMOVED  
# # ============================================
# # Now using is_new_user_atomic() from utils_session.py
# # ============================================



# @router.post("/api/social-click")
# async def log_social_click(request: Request, db: AsyncSession = Depends(get_db)):
#     """Log social media platform click"""
#     try:
#         data = await request.json()

#         platform = data.get("platform", "unknown")
#         branch_code = data.get("branch_code")
#         frontend_session = data.get("session_id", "")
#         user_agent = request.headers.get("user-agent", "")
#         ip_address = request.client.host if request.client else None

#         # ✅ Session priority: cookie > frontend > new
#         cookie_session = request.cookies.get("qr_session")
        
#         if cookie_session:
#             session_id = cookie_session
#         elif frontend_session:
#             session_id = frontend_session
#         else:
#             session_id = str(uuid.uuid4())
#             logger.warning(f"No session found for social click {platform}, created new session")

#         # Resolve branch from QR code
#         branch_id = None
#         if branch_code:
#             result = await db.execute(select(QRCode.branch_id).where(QRCode.code == branch_code))
#             branch_id = result.scalar_one_or_none()

#         device_info = parse_device_info(user_agent)
#         location_data = await get_location_from_ip(ip_address)
        
#         # ✅ ATOMIC check: Use database constraint to prevent phantom users
#         is_new = await is_new_user_atomic(
#             db,
#             session_id,
#             action_type="social_click",
#             branch_id=branch_id
#         )

#         click = SocialClick(
#             platform=platform,
#             branch_id=branch_id,
#             device_type=device_info["device_type"],
#             browser=device_info["browser"],
#             os=device_info["os"],
#             ip_address=ip_address,
#             country=location_data.get("country") if location_data else None,
#             city=location_data.get("city") if location_data else None,
#             session_id=session_id,
#             is_new_user=is_new,
#             user_agent=user_agent
#         )

#         db.add(click)
#         await db.commit()

#         logger.info(f"✅ Social click recorded: {platform} (Session: {session_id[:8]}...)")
#         return {"status": "success", "is_new_user": is_new}

#     except Exception as e:
#         logger.error(f"Error logging social click: {e}", exc_info=True)
#         return {"status": "error"}


# @router.get("/api/social-analytics")
# async def get_social_analytics(
#     start_date: Optional[str] = None,
#     end_date: Optional[str] = None,
#     branch_id: Optional[int] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get social media analytics"""
#     try:
#         from datetime import datetime, timedelta

#         filters = []

#         if branch_id:
#             filters.append(SocialClick.branch_id == branch_id)

#         if start_date:
#             filters.append(SocialClick.clicked_at >= datetime.fromisoformat(start_date))

#         if end_date:
#             end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
#             filters.append(SocialClick.clicked_at <= end_dt)

#         query = select(
#             SocialClick.platform,
#             func.count(SocialClick.id).label('count')
#         ).group_by(SocialClick.platform).order_by(func.count(SocialClick.id).desc())

#         if filters:
#             query = query.where(and_(*filters))

#         result = await db.execute(query)
#         platform_stats = [{"platform": row.platform, "count": row.count} for row in result]

#         total_query = select(func.count(SocialClick.id))
#         if filters:
#             total_query = total_query.where(and_(*filters))

#         total_clicks = (await db.execute(total_query)).scalar() or 0

#         return {"total_clicks": total_clicks, "platforms": platform_stats, "branch_id": branch_id}

#     except Exception as e:
#         logger.error(f"Analytics error: {e}", exc_info=True)
#         return JSONResponse(status_code=500, content={"error": "Failed to get analytics"})


# @router.get("/social-links/styles.css")
# async def social_links_css():
#     css_path = TEMPLATES_DIR / "styles.css"
#     if not css_path.exists():
#         return HTMLResponse("", status_code=404)

#     return HTMLResponse(css_path.read_text(), media_type="text/css")


# @router.get("/social-links/{image_name}")
# async def social_links_images(image_name: str):
#     allowed = ['gk.png','facebook.png','instagram.png','youtube.png','threads.png','twitter.png','whatsapp.png']
#     if image_name not in allowed:
#         return HTMLResponse("Not found", status_code=404)

#     path = TEMPLATES_DIR / image_name
#     if not path.exists():
#         return HTMLResponse("Not found", status_code=404)

#     return FileResponse(path)


from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pathlib import Path
from typing import Optional
import logging
import uuid

from database import get_db
from models import SocialClick, QRCode, QRScan
from utils import parse_device_info
from utils_session import is_new_user_atomic  # ✅ NEW: Atomic session deduplication

router = APIRouter(tags=["Social Links"])
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path("templates/social")


@router.get("/social-links", response_class=HTMLResponse)
async def social_links_page(
    request: Request,
    branch: Optional[str] = Query(None, description="Branch identifier from QR code")
):
    """Serve the social media links page"""
    try:
        html_path = TEMPLATES_DIR / "index.html"
        
        if not html_path.exists():
            return HTMLResponse(
                content="<h1>Social Links page not found</h1>",
                status_code=404
            )
        
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Inject branch parameter into the page
        if branch:
            html_content = html_content.replace(
                'const BRANCH_CODE = null;',
                f'const BRANCH_CODE = "{branch}";'
            )
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.error(f"Error loading social links page: {str(e)}", exc_info=True)
        return HTMLResponse(
            content=f"<h1>Error loading page: {str(e)}</h1>",
            status_code=500
        )



# ============================================
# OLD is_new_user FUNCTION REMOVED  
# ============================================
# Now using is_new_user_atomic() from utils_session.py
# ============================================



@router.post("/api/social-click")
async def log_social_click(request: Request, db: AsyncSession = Depends(get_db)):
    """Log social media platform click"""
    try:
        data = await request.json()

        platform = data.get("platform", "unknown")
        branch_code = data.get("branch_code")
        frontend_session = data.get("session_id", "")
        user_agent = request.headers.get("user-agent", "")
        ip_address = request.client.host if request.client else None

        # ✅ Session priority: cookie > frontend > new
        cookie_session = request.cookies.get("qr_session")
        
        if cookie_session:
            session_id = cookie_session
        elif frontend_session:
            session_id = frontend_session
        else:
            session_id = str(uuid.uuid4())
            logger.warning(f"No session found for social click {platform}, created new session")

        # Resolve branch from QR code
        branch_id = None
        if branch_code:
            result = await db.execute(select(QRCode.branch_id).where(QRCode.code == branch_code))
            branch_id = result.scalar_one_or_none()

        device_info = parse_device_info(user_agent)

        # ✅ ATOMIC check: Use database constraint to prevent phantom users
        is_new = await is_new_user_atomic(
            db,
            session_id,
            action_type="social_click",
            branch_id=branch_id
        )

        click = SocialClick(
            platform=platform,
            branch_id=branch_id,
            device_type=device_info["device_type"],
            browser=device_info["browser"],
            os=device_info["os"],
            ip_address=ip_address,
            country=None,
            city=None,
            session_id=session_id,
            is_new_user=is_new,
            user_agent=user_agent
        )

        db.add(click)
        await db.commit()

        logger.info(f"✅ Social click recorded: {platform} (Session: {session_id[:8]}...)")
        return {"status": "success", "is_new_user": is_new}

    except Exception as e:
        logger.error(f"Error logging social click: {e}", exc_info=True)
        return {"status": "error"}


@router.get("/api/social-analytics")
async def get_social_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get social media analytics"""
    try:
        from datetime import datetime, timedelta

        filters = []

        if branch_id:
            filters.append(SocialClick.branch_id == branch_id)

        if start_date:
            filters.append(SocialClick.clicked_at >= datetime.fromisoformat(start_date))

        if end_date:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            filters.append(SocialClick.clicked_at <= end_dt)

        query = select(
            SocialClick.platform,
            func.count(SocialClick.id).label('count')
        ).group_by(SocialClick.platform).order_by(func.count(SocialClick.id).desc())

        if filters:
            query = query.where(and_(*filters))

        result = await db.execute(query)
        platform_stats = [{"platform": row.platform, "count": row.count} for row in result]

        total_query = select(func.count(SocialClick.id))
        if filters:
            total_query = total_query.where(and_(*filters))

        total_clicks = (await db.execute(total_query)).scalar() or 0

        return {"total_clicks": total_clicks, "platforms": platform_stats, "branch_id": branch_id}

    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to get analytics"})


@router.get("/social-links/styles.css")
async def social_links_css():
    css_path = TEMPLATES_DIR / "styles.css"
    if not css_path.exists():
        return HTMLResponse("", status_code=404)

    return HTMLResponse(css_path.read_text(), media_type="text/css")


@router.get("/social-links/{image_name}")
async def social_links_images(image_name: str):
    allowed = ['gk.png','facebook.png','instagram.png','youtube.png','threads.png','twitter.png','whatsapp.png']
    if image_name not in allowed:
        return HTMLResponse("Not found", status_code=404)

    path = TEMPLATES_DIR / image_name
    if not path.exists():
        return HTMLResponse("Not found", status_code=404)

    return FileResponse(path)