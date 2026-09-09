from fastapi import APIRouter, Depends, Request
from Backend.Controller.query_controller import query_endpoint
from Backend.Middleware.auth import *
query_router = APIRouter()
query_router.add_api_route("/query", query_endpoint, methods=["GET"])