"""
Fixtures de pytest para pruebas unitarias y de integración.
"""
import pytest
from httpx import AsyncClient
# from medsimulator.app.main import app

# TODO: Fixtures para base de datos de prueba
# TODO: Fixtures para mockear clientes de LLM (Anthropic, Groq, OpenRouter)

@pytest.fixture
async def async_client():
    """
    Cliente HTTP asíncrono para probar la API.
    """
    # async with AsyncClient(app=app, base_url="http://test") as client:
    #     yield client
    pass

@pytest.fixture
def mock_caso_clinico():
    """
    Retorna datos de un caso clínico de prueba.
    """
    return {
        "id": "test_caso",
        "paciente": {
            "nombre": "Test",
            "edad": 30
        }
    }
