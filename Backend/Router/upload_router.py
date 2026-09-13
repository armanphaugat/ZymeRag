from fastapi import APIRouter, Depends, Request
from Backend.Middleware.auth import auth_middleware
from Backend.Controller.upload_controller import *

upload_router = APIRouter()
upload_router.add_api_route("/upload_pdf", upload_pdf, methods=["POST"], dependencies=[Depends(auth_middleware)])
upload_router.add_api_route("/upload_docx", upload_docx, methods=["POST"], dependencies=[Depends(auth_middleware)])
upload_router.add_api_route("/upload_image", upload_image, methods=["POST"], dependencies=[Depends(auth_middleware)])
upload_router.add_api_route("/upload_csv", upload_csv, methods=["POST"], dependencies=[Depends(auth_middleware)])
upload_router.add_api_route("/upload_audio", upload_audio, methods=["POST"], dependencies=[Depends(auth_middleware)])
upload_router.add_api_route("/upload_video", upload_video, methods=["POST"], dependencies=[Depends(auth_middleware)])