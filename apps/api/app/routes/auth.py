"""
Auth routes.
Registration and login are handled entirely by Supabase on the frontend.
This module only exposes /auth/me so the frontend can fetch user metadata
(plan, email) using the Supabase JWT it already holds.
"""
from fastapi import APIRouter, Depends

from app.models import User
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user.to_dict()
