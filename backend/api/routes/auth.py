# backend/api/routes/auth.py
from fastapi import APIRouter, Body, HTTPException
from backend.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()

@router.post("/employee/create")
async def create_employee(email: str = Body(...), password: str = Body(...), name: str = Body(...), company: str = Body(None)):
    return auth_service.create_employee(email, password, name, company)

@router.post("/employee/login")
async def employee_login(email: str = Body(...), password: str = Body(...)):
    return auth_service.employee_login(email, password)

@router.post("/recruiter/register")
async def register_recruiter(email: str, name: str, company: str):
    return auth_service.register_recruiter(email, name, company)