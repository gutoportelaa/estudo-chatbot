from fastapi.testclient import TestClient
from app.main import app

# Instanciamos o cliente de testes
client = TestClient(app)

def test_health_check_retorna_status_ok():
    # 1. AÇÃO: Fazemos uma requisição GET para a rota /health
    response = client.get("/health")
    
    # 2. VERIFICAÇÃO: O status HTTP deve ser 200 (Sucesso)
    assert response.status_code == 200
    
    # 3. VERIFICAÇÃO: O corpo da resposta deve conter os dados corretos
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data