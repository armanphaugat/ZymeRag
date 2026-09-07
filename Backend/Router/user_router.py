from fastapi import APIRouter, Depends, Request
from Backend.Middleware.auth import *
from Backend.Controller.user_controller import *
user_router = APIRouter()
user_router.add_api_route("/create_user", create_user, methods=["POST"])
user_router.add_api_route("/refresh_access_token", refresh_access_token, methods=["POST"],dependencies=[Depends(auth_middleware)])
user_router.add_api_route("/log_out", logout_user, methods=["POST"])
