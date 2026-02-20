from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

# ============================================
# REGION SCHEMAS
# ============================================
class RegionCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    code: str = Field(min_length=2, max_length=20)

class RegionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    is_active: Optional[bool] = None

class RegionResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# CLUSTER SCHEMAS
# ============================================
class ClusterCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    region_id: int

class ClusterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    is_active: Optional[bool] = None

class ClusterResponse(BaseModel):
    id: int
    name: str
    code: str
    region_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# BRANCH SCHEMAS
# ============================================
class BranchCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    code: str = Field(min_length=2, max_length=20)
    location: Optional[str] = Field(None, max_length=200)
    cluster_id: int

class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    location: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None

class BranchResponse(BaseModel):
    id: int
    name: str
    code: str
    location: Optional[str]
    cluster_id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# USER SCHEMAS
# ============================================
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    is_super_admin: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_super_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================
# QR CODE SCHEMAS
# ============================================
class QRCodeCreate(BaseModel):
    code: str = Field(min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9\-_]+$')
    target_url: str = Field(min_length=1, max_length=2000)
    branch_id: int


class QRCodeUpdate(BaseModel):
    target_url: Optional[str] = Field(None, min_length=1, max_length=2000)
    is_active: Optional[bool] = None


class QRCodeResponse(BaseModel):
    id: int
    code: str
    target_url: str
    branch_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: int
    scan_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ============================================
# QR SCAN SCHEMAS
# ============================================
class QRScanCreate(BaseModel):
    qr_code_id: int
    device_type: Optional[str] = None
    device_name: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    session_id: Optional[str] = None
    is_new_user: bool = True


class QRScanResponse(BaseModel):
    id: int
    qr_code_id: int
    scanned_at: datetime
    device_type: Optional[str]
    device_name: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    city: Optional[str]
    country: Optional[str]
    is_new_user: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================
# ANALYTICS SCHEMAS
# ============================================
class DeviceBreakdown(BaseModel):
    mobile: int = 0
    desktop: int = 0
    tablet: int = 0


class LocationBreakdown(BaseModel):
    country: str
    city: str
    count: int


class HourlyBreakdown(BaseModel):
    hour: int
    count: int


class NewVsReturning(BaseModel):
    new_users: int = 0
    returning_users: int = 0
    new_percentage: float = 0.0
    returning_percentage: float = 0.0


# Region Level Analytics
class RegionAnalytics(BaseModel):
    region_id: int
    region_name: str
    total_qr_scans: int
    total_social_clicks: int
    detailed_platform_breakdown: List[dict] = []
    combined_total: int
    new_vs_returning: NewVsReturning
    clusters: List[ClusterAnalytics] = []


# Cluster Level Analytics
class ClusterAnalytics(BaseModel):
    cluster_id: int
    cluster_name: str
    region_id: int
    total_qr_scans: int
    total_social_clicks: int
    combined_total: int
    new_vs_returning: NewVsReturning
    branches: List[BranchAnalytics] = []


# Branch Level Analytics
class BranchAnalytics(BaseModel):
    branch_id: int
    branch_name: str
    cluster_id: int
    total_qr_scans: int
    total_social_clicks: int
    combined_total: int
    new_vs_returning: NewVsReturning


# Update forward references
RegionAnalytics.model_rebuild()
ClusterAnalytics.model_rebuild()


# Detailed QR Analytics
class QRAnalytics(BaseModel):
    qr_code_id: int
    branch_id: Optional[int] = None
    total_scans: int
    scans_today: int
    scans_this_week: int
    scans_this_month: int
    
    new_vs_returning: NewVsReturning
    device_breakdown: DeviceBreakdown
    mobile_percentage: float
    
    top_countries: List[LocationBreakdown]
    top_cities: List[LocationBreakdown]
    
    peak_hour: Optional[int]
    hourly_breakdown: List[HourlyBreakdown]
    
    recent_scans: List[QRScanResponse]
    
    page: int = 1
    page_size: int = 10
    total_pages: int = 1
    filtered_scan_count: int = 0


# Social Media Analytics
class SocialAnalytics(BaseModel):
    total_clicks: int
    new_vs_returning: NewVsReturning
    platform_breakdown: List[dict]
    region_id: Optional[int] = None
    cluster_id: Optional[int] = None
    branch_id: Optional[int] = None


# ============================================
# AUTH SCHEMAS
# ============================================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None