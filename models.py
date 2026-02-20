from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    qr_codes = relationship("QRCode", back_populates="creator")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', super_admin={self.is_super_admin})>"


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # NTR, Krishna
    code = Column(String(20), unique=True, nullable=False)  # NTR, KRI
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    clusters = relationship("Cluster", back_populates="region", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Region(id={self.id}, name='{self.name}')>"


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=False)  # C1, C2, C3
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    region = relationship("Region", back_populates="clusters")
    branches = relationship("Branch", back_populates="cluster", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_region_cluster', 'region_id', 'code'),
    )

    def __repr__(self):
        return f"<Cluster(id={self.id}, name='{self.name}', region_id={self.region_id})>"


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=False)  # B1, B2, B3, B4, B5
    location = Column(String(200), nullable=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cluster = relationship("Cluster", back_populates="branches")
    qr_codes = relationship("QRCode", back_populates="branch", cascade="all, delete-orphan")
    social_clicks = relationship("SocialClick", back_populates="branch")

    __table_args__ = (
        Index('idx_cluster_branch', 'cluster_id', 'code'),
    )

    def __repr__(self):
        return f"<Branch(id={self.id}, name='{self.name}', cluster_id={self.cluster_id})>"


class QRCode(Base):
    __tablename__ = "qr_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    branch = relationship("Branch", back_populates="qr_codes")
    creator = relationship("User", back_populates="qr_codes")
    scans = relationship("QRScan", back_populates="qr_code", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_branch_active', 'branch_id', 'is_active'),
        Index('idx_branch_created_at', 'branch_id', 'created_at'),
    )

    def __repr__(self):
        return f"<QRCode(id={self.id}, code='{self.code}')>"


class QRScan(Base):
    __tablename__ = "qr_scans"

    id = Column(Integer, primary_key=True, index=True)
    qr_code_id = Column(Integer, ForeignKey("qr_codes.id"), nullable=False, index=True)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Device info
    device_type = Column(String(20), index=True)
    device_name = Column(String(100))
    browser = Column(String(50), index=True)
    os = Column(String(50))
    
    # Location info
    ip_address = Column(String(45))
    country = Column(String(100), index=True)
    city = Column(String(100), index=True)
    region = Column(String(100))
    
    # Session tracking for new vs returning
    session_id = Column(String(100), index=True)
    is_new_user = Column(Boolean, default=True, index=True)  # Track new vs returning
    
    # Raw data
    user_agent = Column(Text)

    # Relationships
    qr_code = relationship("QRCode", back_populates="scans")

    __table_args__ = (
        Index('idx_qr_scanned', 'qr_code_id', 'scanned_at'),
        Index('idx_qr_device', 'qr_code_id', 'device_type'),
        Index('idx_qr_location', 'qr_code_id', 'country', 'city'),
        Index('idx_scanned_at_qr', 'scanned_at', 'qr_code_id'),
        Index('idx_new_user', 'is_new_user', 'scanned_at'),
    )

    def __repr__(self):
        return f"<QRScan(id={self.id}, qr_code_id={self.qr_code_id})>"


class SocialClick(Base):
    __tablename__ = "social_clicks"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, index=True)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Device info
    device_type = Column(String(20))
    browser = Column(String(50))
    os = Column(String(50))
    
    # Location info
    ip_address = Column(String(45))
    country = Column(String(100))
    city = Column(String(100))
    
    # Session tracking for new vs returning
    session_id = Column(String(100), index=True)
    is_new_user = Column(Boolean, default=True, index=True)  # Track new vs returning
    
    user_agent = Column(Text)

    # Relationships
    branch = relationship("Branch", back_populates="social_clicks")

    __table_args__ = (
        Index('idx_branch_platform_clicked', 'branch_id', 'platform', 'clicked_at'),
        Index('idx_platform_clicked', 'platform', 'clicked_at'),
        Index('idx_clicked_at', 'clicked_at'),
        Index('idx_new_user_social', 'is_new_user', 'clicked_at'),
    )

    def __repr__(self):
        return f"<SocialClick(id={self.id}, platform='{self.platform}')>"
    
class SessionFirstSeen(Base):
    """
    Tracks the first time we see a session to prevent phantom users.
    
    The session_id is a PRIMARY KEY, which means the database GUARANTEES
    that we can only insert one record per session_id. This eliminates 
    race conditions entirely - if two requests try to mark the same session
    as "new" simultaneously, one will succeed and one will fail gracefully.
    """
    __tablename__ = "session_first_seen"

    session_id = Column(String(100), primary_key=True, index=True)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    first_action_type = Column(String(20), nullable=False, index=True)  # 'qr_scan' or 'social_click'
    
    # Optional: Track origin
    first_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    first_qr_code_id = Column(Integer, ForeignKey("qr_codes.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships (optional)
    first_branch = relationship("Branch", foreign_keys=[first_branch_id])
    first_qr_code = relationship("QRCode", foreign_keys=[first_qr_code_id])

    # Indexes for performance
    __table_args__ = (
        Index('idx_session_created', 'created_at'),
        Index('idx_session_action_created', 'first_action_type', 'created_at'),
    )

    def __repr__(self):
        return f"<SessionFirstSeen(session_id='{self.session_id}', first_action='{self.first_action_type}')>"
