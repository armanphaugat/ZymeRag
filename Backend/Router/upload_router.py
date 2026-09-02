from fastapi import APIRouter, Depends, Request
from Backend.Middleware.auth import *
from Backend.Controller.upload_controller import *
upload_router = APIRouter()
upload_router.add_api_route("/upload_pdf", upload_pdf, methods=["POST"])
upload_router.add_api_route("/upload_docx", upload_docx, methods=["POST"])
upload_router.add_api_route("/upload_image", upload_image, methods=["POST"])
upload_router.add_api_route("/upload_csv", upload_csv, methods=["POST"])
upload_router.add_api_route("/upload_audio", upload_audio, methods=["POST"])