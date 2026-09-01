from fastapi import APIRouter, Depends, Request
from Backend.Middleware.auth import *
from Backend.Controller.upload_controller import *
upload_router = APIRouter()
upload_router.add_api_route("/upload_file", upload_pdf, methods=["POST"])