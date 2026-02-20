from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from schemas import (
    BranchUpdate, ClusterUpdate, RegionCreate, RegionResponse,
    ClusterCreate, ClusterResponse,
    BranchCreate, BranchResponse, RegionUpdate
)
from auth import get_current_user
from models import User, Region, Cluster, Branch

router = APIRouter(prefix="/api", tags=["Hierarchy Management"])


def require_super_admin(current_user: User):
    """Helper to check if user is super admin"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can perform this action"
        )


# ============================================
# REGION ROUTES
# ============================================
@router.get("/regions", response_model=List[RegionResponse])
async def get_all_regions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all regions"""
    result = await db.execute(
        select(Region).order_by(Region.name)
    )
    return result.scalars().all()


@router.post("/regions", response_model=RegionResponse, status_code=status.HTTP_201_CREATED)
async def create_region(
    region: RegionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new region (Super Admin only)"""
    require_super_admin(current_user)
    
    # Check if already exists
    result = await db.execute(
        select(Region).where(Region.name == region.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Region name already exists"
        )
    
    new_region = Region(name=region.name, code=region.code)
    db.add(new_region)
    try:
        await db.commit()
        await db.refresh(new_region)
        return new_region
    except IntegrityError as e:
        await db.rollback()
        # Check which field caused the duplicate
        msg = str(e.orig)
        if 'regions_code_key' in msg or 'unique constraint' in msg and 'code' in msg:
            detail = 'Region code already exists'
        elif 'regions_name_key' in msg or 'unique constraint' in msg and 'name' in msg:
            detail = 'Region name already exists'
        else:
            detail = 'Duplicate region entry'
        raise HTTPException(status_code=400, detail=detail)

@router.patch("/regions/{region_id}", response_model=RegionResponse)
async def update_region(
    region_id: int,
    region_update: RegionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)

    result = await db.execute(select(Region).where(Region.id == region_id))
    region = result.scalar_one_or_none()

    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    update_data = region_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(region, key, value)
    try:
        await db.commit()
        await db.refresh(region)
        return region
    except IntegrityError as e:
        await db.rollback()
        msg = str(e.orig)
        if 'regions_code_key' in msg or 'unique constraint' in msg and 'code' in msg:
            detail = 'Region code already exists'
        elif 'regions_name_key' in msg or 'unique constraint' in msg and 'name' in msg:
            detail = 'Region name already exists'
        else:
            detail = 'Duplicate region entry'
        raise HTTPException(status_code=400, detail=detail)



# ============================================
# CLUSTER ROUTES
# ============================================
@router.get("/clusters", response_model=List[ClusterResponse])
async def get_all_clusters(
    region_id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all clusters, optionally filtered by region"""
    query = select(Cluster)
    
    if region_id:
        query = query.where(Cluster.region_id == region_id)
    
    query = query.order_by(Cluster.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/clusters", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    cluster: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new cluster (Super Admin only)"""
    require_super_admin(current_user)
    
    # Verify region exists
    result = await db.execute(
        select(Region).where(Region.id == cluster.region_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found"
        )
    
    new_cluster = Cluster(
        name=cluster.name,
        code=cluster.code,
        region_id=cluster.region_id
    )
    db.add(new_cluster)
    try:
        await db.commit()
        await db.refresh(new_cluster)
        return new_cluster
    except IntegrityError as e:
        await db.rollback()
        msg = str(e.orig)
        if 'clusters_code' in msg and 'unique' in msg:
            detail = 'Cluster code already exists in this region'
        elif 'clusters_name' in msg and 'unique' in msg:
            detail = 'Cluster name already exists in this region'
        else:
            detail = 'Duplicate cluster entry'
        raise HTTPException(status_code=400, detail=detail)

@router.patch("/clusters/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    cluster_update: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)

    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    update_data = cluster_update.model_dump(exclude_unset=True)

    # Optional safety: validate region exists if region_id is being changed
    if "region_id" in update_data:
        region_check = await db.execute(select(Region).where(Region.id == update_data["region_id"]))
        if not region_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Region not found")

    for key, value in update_data.items():
        setattr(cluster, key, value)
    try:
        await db.commit()
        await db.refresh(cluster)
        return cluster
    except IntegrityError as e:
        await db.rollback()
        msg = str(e.orig)
        if 'clusters_code' in msg and 'unique' in msg:
            detail = 'Cluster code already exists in this region'
        elif 'clusters_name' in msg and 'unique' in msg:
            detail = 'Cluster name already exists in this region'
        else:
            detail = 'Duplicate cluster entry'
        raise HTTPException(status_code=400, detail=detail)


# ============================================
# BRANCH ROUTES
# ============================================
@router.get("/branches", response_model=List[BranchResponse])
async def get_all_branches(
    region_id: int = None,
    cluster_id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all branches, optionally filtered by region or cluster"""
    query = select(Branch)
    
    if cluster_id:
        query = query.where(Branch.cluster_id == cluster_id)
    elif region_id:
        # Get branches through cluster
        query = query.join(Cluster).where(Cluster.region_id == region_id)
    
    query = query.order_by(Branch.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    branch: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new branch (Super Admin only)"""
    require_super_admin(current_user)
    
    # Verify cluster exists
    result = await db.execute(
        select(Cluster).where(Cluster.id == branch.cluster_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found"
        )
    
    new_branch = Branch(
        name=branch.name,
        code=branch.code,
        location=branch.location,
        cluster_id=branch.cluster_id
    )
    db.add(new_branch)
    try:
        await db.commit()
        await db.refresh(new_branch)
        return new_branch
    except IntegrityError as e:
        await db.rollback()
        msg = str(e.orig)
        if 'branches_code' in msg and 'unique' in msg:
            detail = 'Branch code already exists in this cluster'
        elif 'branches_name' in msg and 'unique' in msg:
            detail = 'Branch name already exists in this cluster'
        else:
            detail = 'Duplicate branch entry'
        raise HTTPException(status_code=400, detail=detail)

@router.patch("/branches/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: int,
    branch_update: BranchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_super_admin(current_user)

    result = await db.execute(select(Branch).where(Branch.id == branch_id))
    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    update_data = branch_update.model_dump(exclude_unset=True)

    # Optional safety: validate cluster exists if cluster_id is added later
    if "cluster_id" in update_data:
        cluster_check = await db.execute(select(Cluster).where(Cluster.id == update_data["cluster_id"]))
        if not cluster_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Cluster not found")

    for key, value in update_data.items():
        setattr(branch, key, value)
    try:
        await db.commit()
        await db.refresh(branch)
        return branch
    except IntegrityError as e:
        await db.rollback()
        msg = str(e.orig)
        if 'branches_code' in msg and 'unique' in msg:
            detail = 'Branch code already exists in this cluster'
        elif 'branches_name' in msg and 'unique' in msg:
            detail = 'Branch name already exists in this cluster'
        else:
            detail = 'Duplicate branch entry'
        raise HTTPException(status_code=400, detail=detail)


@router.delete("/branches/{branch_id}")
async def deactivate_branch(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate branch (Super Admin only)"""
    require_super_admin(current_user)
    
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = result.scalar_one_or_none()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    branch.is_active = False
    await db.commit()
    
    return {"message": f"Branch '{branch.name}' deactivated successfully"}

