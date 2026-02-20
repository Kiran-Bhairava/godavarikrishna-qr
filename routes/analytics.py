from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List, Optional
from datetime import datetime, timedelta

from database import get_db
from auth import get_current_user
from models import User, Region, Cluster, Branch, QRCode, QRScan, SocialClick
from schemas import (
    RegionAnalytics, ClusterAnalytics, BranchAnalytics,
    NewVsReturning, SocialAnalytics
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def require_super_admin(current_user: User):
    """Helper to check if user is super admin"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admin can view analytics"
        )


async def calculate_new_vs_returning(
    db: AsyncSession,
    qr_base_query=None,
    social_base_query=None
) -> NewVsReturning:
    """Calculate new vs returning users for QR scans and social clicks"""
    
    # Default queries if none provided
    if qr_base_query is None:
        qr_base_query = select(QRScan)
    
    if social_base_query is None:
        social_base_query = select(SocialClick)
    
    # QR Scans - apply the base query and count
    qr_new_query = qr_base_query.where(QRScan.is_new_user == True)
    qr_returning_query = qr_base_query.where(QRScan.is_new_user == False)
    
    # Convert to count queries
    qr_new_count_query = select(func.count()).select_from(qr_new_query.subquery())
    qr_returning_count_query = select(func.count()).select_from(qr_returning_query.subquery())
    
    qr_new = (await db.execute(qr_new_count_query)).scalar() or 0
    qr_returning = (await db.execute(qr_returning_count_query)).scalar() or 0
    
    # Social Clicks - apply the base query and count
    social_new_query = social_base_query.where(SocialClick.is_new_user == True)
    social_returning_query = social_base_query.where(SocialClick.is_new_user == False)
    
    # Convert to count queries
    social_new_count_query = select(func.count()).select_from(social_new_query.subquery())
    social_returning_count_query = select(func.count()).select_from(social_returning_query.subquery())
    
    social_new = (await db.execute(social_new_count_query)).scalar() or 0
    social_returning = (await db.execute(social_returning_count_query)).scalar() or 0
    
    # Combine
    total_new = qr_new + social_new
    total_returning = qr_returning + social_returning
    total = total_new + total_returning
    
    return NewVsReturning(
        new_users=total_new,
        returning_users=total_returning,
        new_percentage=round((total_new / total * 100), 2) if total > 0 else 0.0,
        returning_percentage=round((total_returning / total * 100), 2) if total > 0 else 0.0
    )

# ============================================
# REGION ANALYTICS
# ============================================
@router.get("/regions", response_model=List[RegionAnalytics])
async def get_region_analytics(
    region_id: Optional[int] = Query(None, description="Specific region ID"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_details: bool = Query(False, description="Include cluster and branch breakdown"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)

    # ---------------- DATE FILTERS ----------------
    qr_date_filters = []
    social_date_filters = []

    try:
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            qr_date_filters.append(QRScan.scanned_at >= start_dt)
            social_date_filters.append(SocialClick.clicked_at >= start_dt)

        if end_date:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            qr_date_filters.append(QRScan.scanned_at <= end_dt)
            social_date_filters.append(SocialClick.clicked_at <= end_dt)
    except ValueError:
        pass

    # ---------------- FETCH REGIONS ----------------
    region_query = select(Region).where(Region.is_active == True)

    if region_id:
        region_query = region_query.where(Region.id == region_id)

    region_query = region_query.order_by(Region.name)

    regions_result = await db.execute(region_query)
    regions = regions_result.scalars().all()

    analytics = []

    for region in regions:
        # ---------------- BRANCH IDS ----------------
        branch_ids_query = (
            select(Branch.id)
            .join(Cluster)
            .where(Cluster.region_id == region.id, Branch.is_active == True)
        )
        branch_ids_result = await db.execute(branch_ids_query)
        branch_ids = [row[0] for row in branch_ids_result.all()]

        if not branch_ids:
            # If no branches, return zero analytics
            region_analytics = RegionAnalytics(
                region_id=region.id,
                region_name=region.name,
                total_qr_scans=0,
                total_social_clicks=0,
                detailed_platform_breakdown=[],
                combined_total=0,
                new_vs_returning=NewVsReturning(
                    new_users=0,
                    returning_users=0,
                    new_percentage=0.0,
                    returning_percentage=0.0
                ),
                clusters=[]
            )
            analytics.append(region_analytics)
            continue

        # ---------------- QR SCANS ----------------
        qr_query = (
            select(func.count(QRScan.id))
            .join(QRCode)
            .where(QRCode.branch_id.in_(branch_ids))
        )
        if qr_date_filters:
            qr_query = qr_query.where(and_(*qr_date_filters))

        total_qr_scans = (await db.execute(qr_query)).scalar() or 0

        # ---------------- SOCIAL CLICKS ----------------
        social_query = select(func.count(SocialClick.id)).where(
            SocialClick.branch_id.in_(branch_ids)
        )
        if social_date_filters:
            social_query = social_query.where(and_(*social_date_filters))

        total_social_clicks = (await db.execute(social_query)).scalar() or 0

        # ---------------- NEW VS RETURNING ----------------
        # IMPORTANT: Build queries with proper filtering
        qr_base_query = select(QRScan).join(QRCode).where(QRCode.branch_id.in_(branch_ids))
        social_base_query = select(SocialClick).where(SocialClick.branch_id.in_(branch_ids))
        
        # Add date filters if they exist
        if qr_date_filters:
            qr_base_query = qr_base_query.where(and_(*qr_date_filters))
        
        if social_date_filters:
            social_base_query = social_base_query.where(and_(*social_date_filters))

        new_vs_returning = await calculate_new_vs_returning(
            db, qr_base_query, social_base_query
        )

        region_analytics = RegionAnalytics(
            region_id=region.id,
            region_name=region.name,
            total_qr_scans=total_qr_scans,
            total_social_clicks=total_social_clicks,
            combined_total=total_qr_scans + total_social_clicks,
            new_vs_returning=new_vs_returning,
            clusters=[]
        )

        # ---------------- CLUSTER + BRANCH BREAKDOWN ----------------
        if include_details:
            clusters_result = await db.execute(
                select(Cluster)
                .where(Cluster.region_id == region.id, Cluster.is_active == True)
                .order_by(Cluster.name)
            )
            clusters = clusters_result.scalars().all()

            for cluster in clusters:
                cluster_analytics = await get_cluster_analytics_internal(
                    db=db,
                    cluster=cluster,
                    start_date=start_date,
                    end_date=end_date,
                    include_branches=True
                )
                region_analytics.clusters.append(cluster_analytics)

        analytics.append(region_analytics)

    return analytics


# ============================================
# CLUSTER ANALYTICS
# ============================================
async def get_cluster_analytics_internal(
    db: AsyncSession,
    cluster: Cluster,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_branches: bool = False
) -> ClusterAnalytics:
    """Internal function to get cluster analytics"""
    
    # Build date filters for both QR and Social
    qr_date_filters = []
    social_date_filters = []
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            qr_date_filters.append(QRScan.scanned_at >= start_dt)
            social_date_filters.append(SocialClick.clicked_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            qr_date_filters.append(QRScan.scanned_at <= end_dt)
            social_date_filters.append(SocialClick.clicked_at <= end_dt)
        except ValueError:
            pass
    
    # Get all branches in this cluster
    branch_ids_query = select(Branch.id).where(
        Branch.cluster_id == cluster.id,
        Branch.is_active == True
    )
    branch_ids_result = await db.execute(branch_ids_query)
    branch_ids = [row[0] for row in branch_ids_result.all()]
    
    if not branch_ids:
        # Return empty analytics if no branches
        return ClusterAnalytics(
            cluster_id=cluster.id,
            cluster_name=cluster.name,
            region_id=cluster.region_id,
            total_qr_scans=0,
            total_social_clicks=0,
            combined_total=0,
            new_vs_returning=NewVsReturning(
                new_users=0,
                returning_users=0,
                new_percentage=0.0,
                returning_percentage=0.0
            ),
            branches=[]
        )
    
    # QR Scans
    qr_query = select(func.count(QRScan.id)).join(QRCode).where(
        QRCode.branch_id.in_(branch_ids)
    )
    if qr_date_filters:
        qr_query = qr_query.where(and_(*qr_date_filters))
    
    total_qr_scans = (await db.execute(qr_query)).scalar() or 0
    
    # Social Clicks
    social_query = select(func.count(SocialClick.id)).where(
        SocialClick.branch_id.in_(branch_ids)
    )
    if social_date_filters:
        social_query = social_query.where(and_(*social_date_filters))
    
    total_social_clicks = (await db.execute(social_query)).scalar() or 0
    
    # New vs Returning - BUILD QUERY OBJECTS, NOT FILTER LISTS
    qr_base_query = select(QRScan).join(QRCode).where(QRCode.branch_id.in_(branch_ids))
    social_base_query = select(SocialClick).where(SocialClick.branch_id.in_(branch_ids))
    
    # Add date filters if they exist
    if qr_date_filters:
        qr_base_query = qr_base_query.where(and_(*qr_date_filters))
    
    if social_date_filters:
        social_base_query = social_base_query.where(and_(*social_date_filters))
    
    new_vs_returning = await calculate_new_vs_returning(
        db, qr_base_query, social_base_query
    )
    
    cluster_analytics = ClusterAnalytics(
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        region_id=cluster.region_id,
        total_qr_scans=total_qr_scans,
        total_social_clicks=total_social_clicks,
        combined_total=total_qr_scans + total_social_clicks,
        new_vs_returning=new_vs_returning,
        branches=[]
    )
    
    # Include branch details if requested
    if include_branches:
        branches_result = await db.execute(
            select(Branch).where(
                Branch.cluster_id == cluster.id,
                Branch.is_active == True
            ).order_by(Branch.name)
        )
        branches = branches_result.scalars().all()
        
        for branch in branches:
            branch_analytics = await get_branch_analytics_internal(
                db, branch, start_date, end_date
            )
            cluster_analytics.branches.append(branch_analytics)
    
    return cluster_analytics

@router.get("/clusters/{cluster_id}", response_model=ClusterAnalytics)
async def get_cluster_analytics(
    cluster_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_branches: bool = Query(True, description="Include branch breakdown"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get analytics for a specific cluster"""
    require_super_admin(current_user)
    
    result = await db.execute(
        select(Cluster).where(Cluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    return await get_cluster_analytics_internal(
        db, cluster, start_date, end_date, include_branches
    )


# ============================================
# BRANCH ANALYTICS
# ============================================
async def get_branch_analytics_internal(
    db: AsyncSession,
    branch: Branch,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> BranchAnalytics:
    """Internal function to get branch analytics"""
    
    # Build date filters for both QR and Social
    qr_date_filters = []
    social_date_filters = []
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            qr_date_filters.append(QRScan.scanned_at >= start_dt)
            social_date_filters.append(SocialClick.clicked_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            qr_date_filters.append(QRScan.scanned_at <= end_dt)
            social_date_filters.append(SocialClick.clicked_at <= end_dt)
        except ValueError:
            pass
    
    # QR Scans
    qr_query = select(func.count(QRScan.id)).join(QRCode).where(
        QRCode.branch_id == branch.id
    )
    if qr_date_filters:
        qr_query = qr_query.where(and_(*qr_date_filters))
    
    total_qr_scans = (await db.execute(qr_query)).scalar() or 0
    
    # Social Clicks
    social_query = select(func.count(SocialClick.id)).where(
        SocialClick.branch_id == branch.id
    )
    if social_date_filters:
        social_query = social_query.where(and_(*social_date_filters))
    
    total_social_clicks = (await db.execute(social_query)).scalar() or 0
    
    # New vs Returning - BUILD QUERY OBJECTS, NOT FILTER LISTS
    qr_base_query = select(QRScan).join(QRCode).where(QRCode.branch_id == branch.id)
    social_base_query = select(SocialClick).where(SocialClick.branch_id == branch.id)
    
    # Add date filters if they exist
    if qr_date_filters:
        qr_base_query = qr_base_query.where(and_(*qr_date_filters))
    
    if social_date_filters:
        social_base_query = social_base_query.where(and_(*social_date_filters))
    
    new_vs_returning = await calculate_new_vs_returning(
        db, qr_base_query, social_base_query
    )
    
    return BranchAnalytics(
        branch_id=branch.id,
        branch_name=branch.name,
        cluster_id=branch.cluster_id,
        total_qr_scans=total_qr_scans,
        total_social_clicks=total_social_clicks,
        combined_total=total_qr_scans + total_social_clicks,
        new_vs_returning=new_vs_returning
    )

@router.get("/branches/{branch_id}", response_model=BranchAnalytics)
async def get_branch_analytics(
    branch_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get analytics for a specific branch"""
    require_super_admin(current_user)
    
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = result.scalar_one_or_none()
    
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    return await get_branch_analytics_internal(db, branch, start_date, end_date)


@router.get("/branches/{branch_id}/social-breakdown")
async def get_branch_social_breakdown(
    branch_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get social media platform breakdown for a specific branch"""
    require_super_admin(current_user)
    
    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    query = select(
        SocialClick.platform,
        func.count(SocialClick.id).label('count')
    ).where(SocialClick.branch_id == branch_id)
    
    if start_date:
        try:
            query = query.where(SocialClick.clicked_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            query = query.where(SocialClick.clicked_at <= end_dt)
        except ValueError:
            pass
    
    query = query.group_by(SocialClick.platform).order_by(func.count(SocialClick.id).desc())
    
    result = await db.execute(query)
    breakdown = [{"platform": row.platform, "count": row.count} for row in result.all()]
    
    return {"branch_id": branch_id, "branch_name": branch.name, "platform_breakdown": breakdown}


# ============================================
# SOCIAL MEDIA ANALYTICS
# ============================================
@router.get("/social", response_model=SocialAnalytics)
async def get_social_analytics(
    region_id: Optional[int] = None,
    cluster_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get social media analytics with hierarchical filtering
    """
    require_super_admin(current_user)
    
    # Build base query
    social_base_query = select(SocialClick)
    
    # Hierarchical filtering
    if branch_id:
        social_base_query = social_base_query.where(SocialClick.branch_id == branch_id)
    elif cluster_id:
        # Get all branches in cluster
        branch_ids_query = select(Branch.id).where(Branch.cluster_id == cluster_id)
        branch_ids_result = await db.execute(branch_ids_query)
        branch_ids = [row[0] for row in branch_ids_result.all()]
        social_base_query = social_base_query.where(SocialClick.branch_id.in_(branch_ids))
    elif region_id:
        # Get all branches in region
        branch_ids_query = select(Branch.id).join(Cluster).where(Cluster.region_id == region_id)
        branch_ids_result = await db.execute(branch_ids_query)
        branch_ids = [row[0] for row in branch_ids_result.all()]
        social_base_query = social_base_query.where(SocialClick.branch_id.in_(branch_ids))
    
    # Date filters
    if start_date:
        try:
            social_base_query = social_base_query.where(SocialClick.clicked_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            social_base_query = social_base_query.where(SocialClick.clicked_at <= end_dt)
        except ValueError:
            pass
    
    # Total clicks - use the same base query
    total_query = select(func.count()).select_from(social_base_query.subquery())
    total_clicks = (await db.execute(total_query)).scalar() or 0
    
    # Platform breakdown
    platform_query = select(
        SocialClick.platform,
        func.count(SocialClick.id).label('count')
    )
    
    # Apply the same filters as social_base_query
    if branch_id:
        platform_query = platform_query.where(SocialClick.branch_id == branch_id)
    elif cluster_id:
        branch_ids_query = select(Branch.id).where(Branch.cluster_id == cluster_id)
        branch_ids_result = await db.execute(branch_ids_query)
        branch_ids = [row[0] for row in branch_ids_result.all()]
        platform_query = platform_query.where(SocialClick.branch_id.in_(branch_ids))
    elif region_id:
        branch_ids_query = select(Branch.id).join(Cluster).where(Cluster.region_id == region_id)
        branch_ids_result = await db.execute(branch_ids_query)
        branch_ids = [row[0] for row in branch_ids_result.all()]
        platform_query = platform_query.where(SocialClick.branch_id.in_(branch_ids))
    
    if start_date:
        try:
            platform_query = platform_query.where(SocialClick.clicked_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date) + timedelta(days=1) - timedelta(seconds=1)
            platform_query = platform_query.where(SocialClick.clicked_at <= end_dt)
        except ValueError:
            pass
    
    platform_query = platform_query.group_by(SocialClick.platform).order_by(func.count(SocialClick.id).desc())
    
    platform_result = await db.execute(platform_query)
    platform_breakdown = [
        {"platform": row.platform, "count": row.count}
        for row in platform_result.all()
    ]
    
    # New vs Returning - pass query object, not filters list
    new_vs_returning = await calculate_new_vs_returning(
        db, qr_base_query=None, social_base_query=social_base_query
    )
    
    return SocialAnalytics(
        total_clicks=total_clicks,
        new_vs_returning=new_vs_returning,
        platform_breakdown=platform_breakdown,
        region_id=region_id,
        cluster_id=cluster_id,
        branch_id=branch_id
    )