from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from database import get_db
from schemas import BranchCreate, BranchResponse, BranchPerformance
from auth import get_current_user
from models import User, Branch, QRCode, QRScan, SocialClick

router = APIRouter(prefix="/branches", tags=["Branches"])

# ============================================
# CREATE BRANCH (Super Admin Only)
# ============================================
@router.post("/", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
async def create_branch(
    branch: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new branch (Super Admin only)"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create branches"
        )
    
    # Check if branch name already exists
    result = await db.execute(
        select(Branch).where(Branch.name == branch.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch name already exists"
        )
    
    new_branch = Branch(
        name=branch.name,
        location=branch.location
    )
    
    db.add(new_branch)
    await db.commit()
    await db.refresh(new_branch)
    
    return new_branch


# ============================================
# GET ALL BRANCHES
# ============================================
@router.get("/", response_model=List[BranchResponse])
async def get_all_branches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all branches"""
    result = await db.execute(
        select(Branch).where(Branch.is_active == True).order_by(Branch.name)
    )
    branches = result.scalars().all()
    return branches


# ============================================
# GET BRANCH PERFORMANCE (Super Admin Dashboard)
# ============================================
@router.get("/performance", response_model=List[BranchPerformance])
async def get_branches_performance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance metrics for all branches (Super Admin only)"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can view all branches performance"
        )
    
    # Get all active branches
    branches_result = await db.execute(
        select(Branch).where(Branch.is_active == True).order_by(Branch.name)
    )
    branches = branches_result.scalars().all()
    
    performance_data = []
    
    for branch in branches:
        # Get QR scans count for this branch
        qr_scans_query = select(func.count(QRScan.id)).join(
            QRCode, QRCode.id == QRScan.qr_code_id
        ).where(QRCode.branch_id == branch.id)
        
        scans_result = await db.execute(qr_scans_query)
        total_scans = scans_result.scalar() or 0
        
        # Get social clicks count for this branch
        social_clicks_query = select(func.count(SocialClick.id)).where(
            SocialClick.branch_id == branch.id
        )
        
        clicks_result = await db.execute(social_clicks_query)
        total_social_clicks = clicks_result.scalar() or 0
        
        performance_data.append(
            BranchPerformance(
                branch_id=branch.id,
                branch_name=branch.name,
                total_scans=total_scans,
                total_social_clicks=total_social_clicks,
                combined_total=total_scans + total_social_clicks
            )
        )
    
    return performance_data


# ============================================
# UPDATE BRANCH (Super Admin Only)
# ============================================
@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: int,
    branch_update: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update branch details (Super Admin only)"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can update branches"
        )
    
    result = await db.execute(
        select(Branch).where(Branch.id == branch_id)
    )
    branch = result.scalar_one_or_none()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    branch.name = branch_update.name
    branch.location = branch_update.location
    
    await db.commit()
    await db.refresh(branch)
    
    return branch


# ============================================
# DEACTIVATE BRANCH (Super Admin Only)
# ============================================
@router.delete("/{branch_id}")
async def deactivate_branch(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate a branch (Super Admin only)"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can deactivate branches"
        )
    
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