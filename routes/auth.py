from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from schemas import UserLogin, Token, UserCreate, UserResponse
from auth import authenticate_user, create_access_token, get_password_hash, get_current_user
from models import User
from config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ============================================
# LOGIN
# ============================================
@router.post("/login", response_model=Token)
async def login(
    user_login: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    Returns JWT access token.
    """
    # Authenticate user
    user = await authenticate_user(db, user_login.email, user_login.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# ============================================
# REGISTER (Optional - for creating new marketing users)
# ============================================
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Only logged-in users can create new users
):
    """
    Register a new user (requires authentication).
    Only existing users can create new marketing team members.
    """
    from sqlalchemy import select
    
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_create.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_create.password)
    new_user = User(
        email=user_create.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


# ============================================
# GET CURRENT USER INFO
# ============================================
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information.
    """
    return current_user


# ============================================
# LOGOUT (Client-side handling)
# ============================================
@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint.
    Since JWT is stateless, logout is handled client-side by deleting the token.
    This endpoint just validates the token is still valid.
    """
    return {
        "message": "Successfully logged out",
        "detail": "Please delete the token from client storage"
    }