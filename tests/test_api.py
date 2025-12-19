from fastapi.testclient import TestClient
from api.main import app

# Create a test client using the FastAPI app
client = TestClient(app)

def test_health_check():
    """
    Test 1: Verify the API is alive (Root Endpoint)
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "API Online", "service": "CattleCounter"}

def test_invalid_endpoint():
    """
    Test 2: Verify 404 on non-existent routes
    """
    response = client.get("/non-existent-route")
    assert response.status_code == 404