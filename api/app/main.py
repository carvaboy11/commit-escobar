import json
import os

import pika
import pymysql
from pymysql.cursors import DictCursor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Taverna do Javali Dourado")

FILA = "pedido.criado"


class PedidoEntrada(BaseModel):
    cliente: str = Field(min_length=1, max_length=60)
    item: str = Field(min_length=1, max_length=60)


class Pedido(BaseModel):
    id: int
    cliente: str
    item: str
    pronto: bool


def conectar():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=DictCursor,
        autocommit=True,
    )


def listar():
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT id, cliente, item, pronto FROM pedidos ORDER BY id")
            return cur.fetchall()
    finally:
        con.close()


def buscar(pedido_id):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                "SELECT id, cliente, item, pronto FROM pedidos WHERE id = %s", (pedido_id,)
            )
            return cur.fetchone()
    finally:
        con.close()


def inserir(cliente, item):
    con = conectar()
    try:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO pedidos (cliente, item) VALUES (%s, %s)", (cliente, item)
            )
            return cur.lastrowid
    finally:
        con.close()


def publicar(evento):
    params = pika.URLParameters(os.environ["AMQP_URL"])
    con = pika.BlockingConnection(params)
    try:
        canal = con.channel()
        canal.queue_declare(queue=FILA, durable=True)
        canal.basic_publish(
            exchange="",
            routing_key=FILA,
            body=json.dumps(evento),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        con.close()


@app.get("/saude")
def saude():
    try:
        conectar().close()
    except pymysql.err.MySQLError:
        raise HTTPException(503, "banco fora do ar")
    return {"api": "ok", "banco": "ok"}


@app.get("/pedidos", response_model=list[Pedido])
def listar_pedidos():
    return listar()


@app.get("/pedidos/{pedido_id}", response_model=Pedido)
def buscar_pedido(pedido_id: int):
    pedido = buscar(pedido_id)
    if pedido is None:
        raise HTTPException(404, "pedido nao encontrado")
    return pedido


@app.post("/pedidos", response_model=Pedido, status_code=201)
def criar_pedido(entrada: PedidoEntrada):
    novo_id = inserir(entrada.cliente, entrada.item)
    try:
        publicar({"id": novo_id, "cliente": entrada.cliente, "item": entrada.item})
    except pika.exceptions.AMQPError:
        # o pedido ja foi salvo, so a cozinha que nao vai ficar sabendo por enquanto
        print(f"fila fora do ar, pedido {novo_id} nao chegou na cozinha", flush=True)
    return {"id": novo_id, "cliente": entrada.cliente, "item": entrada.item, "pronto": False}
