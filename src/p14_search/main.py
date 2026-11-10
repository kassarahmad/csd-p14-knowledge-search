"""ASGI entry point: uvicorn p14_search.main:app"""

from p14_search.api.app import create_app

app = create_app()
