import pika
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)

PEDIDO = {"cliente": "Thorin", "item": "Hidromel"}


def test_criar_pedido_manda_pra_cozinha(monkeypatch):
    eventos = []
    monkeypatch.setattr(main, "inserir", lambda cliente, item: 7)
    monkeypatch.setattr(main, "publicar", lambda evento: eventos.append(evento))

    r = client.post("/pedidos", json=PEDIDO)

    assert r.status_code == 201
    assert r.json() == {"id": 7, "cliente": "Thorin", "item": "Hidromel", "pronto": False}
    assert eventos == [{"id": 7, "cliente": "Thorin", "item": "Hidromel"}]


def test_item_vazio_da_422(monkeypatch):
    eventos = []
    monkeypatch.setattr(main, "publicar", lambda evento: eventos.append(evento))

    r = client.post("/pedidos", json={"cliente": "Thorin", "item": ""})

    assert r.status_code == 422
    assert eventos == []


def test_fila_fora_do_ar_ainda_salva(monkeypatch):
    def quebrado(evento):
        raise pika.exceptions.AMQPConnectionError("fora do ar")

    monkeypatch.setattr(main, "inserir", lambda cliente, item: 1)
    monkeypatch.setattr(main, "publicar", quebrado)

    r = client.post("/pedidos", json=PEDIDO)

    assert r.status_code == 201


def test_pedido_inexistente_da_404(monkeypatch):
    monkeypatch.setattr(main, "buscar", lambda pedido_id: None)

    r = client.get("/pedidos/999")

    assert r.status_code == 404
