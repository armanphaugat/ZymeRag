from fastapi import APIRouter, Depends, Request
from Backend.Controller.delete_controller import delete_id
from Backend.Middleware.auth import *
from Backend.Controller.upload_controller import *
delete_router = APIRouter()
delete_router.add_api_route("/delete_content", delete_id, methods=["DELETE"])