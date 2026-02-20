"""
Session deduplication utility

Add this to a new file: utils_session.py
OR add it to your existing utils.py

This is the CORE of the phantom user solution.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


async def is_new_user_atomic(
    db: AsyncSession, 
    session_id: str, 
    action_type: str,
    branch_id: int = None,
    qr_code_id: int = None
) -> bool:
    """
    Atomically determine if this is a new user by trying to insert into session_first_seen.
    
    This function uses the database PRIMARY KEY constraint to guarantee uniqueness.
    It's IMPOSSIBLE to have a race condition because the database itself enforces
    that only ONE record can exist per session_id.
    
    Flow:
        1. Try to INSERT session into session_first_seen table
        2. If INSERT succeeds → This is a NEW user (first time seeing this session)
        3. If INSERT fails → This is a RETURNING user (session already exists)
    
    Args:
        db: Database session
        session_id: Unique session identifier from cookie
        action_type: 'qr_scan' or 'social_click'
        branch_id: Optional branch ID for tracking
        qr_code_id: Optional QR code ID for tracking
    
    Returns:
        bool: True if NEW user (first action), False if RETURNING user
    
    Examples:
        >>> # User scans QR code (first action)
        >>> is_new = await is_new_user_atomic(db, "abc123", "qr_scan", qr_code_id=5)
        >>> print(is_new)  # True
        
        >>> # Same user clicks social link 100ms later
        >>> is_new = await is_new_user_atomic(db, "abc123", "social_click")
        >>> print(is_new)  # False (session already exists)
        
        >>> # Even if 100 requests come simultaneously with same session_id
        >>> # Database guarantees ONLY ONE will return True, rest return False
    """
    try:
        # Build INSERT query with ON CONFLICT to handle race conditions gracefully
        query = text("""
            INSERT INTO session_first_seen 
                (session_id, first_action_type, first_branch_id, first_qr_code_id)
            VALUES 
                (:session_id, :action_type, :branch_id, :qr_code_id)
            ON CONFLICT (session_id) DO NOTHING
            RETURNING session_id
        """)
        
        result = await db.execute(
            query,
            {
                "session_id": session_id,
                "action_type": action_type,
                "branch_id": branch_id,
                "qr_code_id": qr_code_id
            }
        )
        
        # Commit immediately to release the lock
        await db.commit()
        
        # If RETURNING gave us back a session_id, the INSERT succeeded
        inserted = result.scalar_one_or_none()
        
        if inserted:
            logger.info(f"✅ NEW user detected: session={session_id[:8]}..., action={action_type}")
            return True
        else:
            logger.info(f"🔄 RETURNING user detected: session={session_id[:8]}..., action={action_type}")
            return False
            
    except IntegrityError as e:
        # This should rarely happen with ON CONFLICT DO NOTHING, but just in case
        logger.debug(f"Session {session_id[:8]}... already exists (IntegrityError): {e}")
        await db.rollback()
        return False
        
    except Exception as e:
        # Any other error - log it and mark as returning user (safe default)
        logger.error(f"Error checking session {session_id[:8]}...: {e}", exc_info=True)
        await db.rollback()
        return False


async def get_session_first_action(db: AsyncSession, session_id: str) -> dict:
    """
    Get information about when we first saw this session.
    
    Useful for analytics or debugging.
    
    Returns:
        dict with keys: session_id, first_seen_at, first_action_type, first_branch_id, first_qr_code_id
        or None if session not found
    """
    try:
        query = text("""
            SELECT 
                session_id, 
                first_seen_at, 
                first_action_type, 
                first_branch_id, 
                first_qr_code_id,
                created_at
            FROM session_first_seen
            WHERE session_id = :session_id
        """)
        
        result = await db.execute(query, {"session_id": session_id})
        row = result.one_or_none()
        
        if row:
            return {
                "session_id": row.session_id,
                "first_seen_at": row.first_seen_at,
                "first_action_type": row.first_action_type,
                "first_branch_id": row.first_branch_id,
                "first_qr_code_id": row.first_qr_code_id,
                "created_at": row.created_at
            }
        return None
        
    except Exception as e:
        logger.error(f"Error fetching session info: {e}")
        return None


async def cleanup_old_sessions(db: AsyncSession, days_old: int = 90):
    """
    Optional: Clean up old session records to keep table size manageable.
    
    Run this periodically (e.g., weekly cron job) to delete sessions older than X days.
    
    Args:
        db: Database session
        days_old: Delete sessions older than this many days (default 90)
    
    Returns:
        int: Number of deleted records
    """
    try:
        query = text("""
            DELETE FROM session_first_seen
            WHERE created_at < NOW() - INTERVAL ':days days'
            RETURNING session_id
        """)
        
        result = await db.execute(query, {"days": days_old})
        await db.commit()
        
        deleted_count = len(result.all())
        logger.info(f"🧹 Cleaned up {deleted_count} old sessions (older than {days_old} days)")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {e}")
        await db.rollback()
        return 0