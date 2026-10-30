import json
import os
import time

import pika
import pymysql

FILA = "pedido.criado"


def conectar_banco():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=True,
    )


def conectar_fila():
    params = pika.URLParameters(os.environ["AMQP_URL"])
    for tentativa in range(1, 31):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            print(f"rabbitmq ainda nao subiu (tentativa {tentativa}/30)", flush=True)
            time.sleep(2)
    raise RuntimeError("rabbitmq nao respondeu")


def ao_receber(canal, metodo, props, corpo):
    try:
        evento = json.loads(corpo)
        pedido_id = evento["id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        print("pedido ilegivel, jogado fora", flush=True)
        canal.basic_nack(metodo.delivery_tag, requeue=False)
        return

    print(f"cozinha: preparando {evento.get('item')} pra {evento.get('cliente')}...", flush=True)
    time.sleep(2)  # tempo de preparo

    # rodar duas vezes o mesmo update nao estraga nada (idempotente)
    con = conectar_banco()
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE pedidos SET pronto = TRUE WHERE id = %s", (pedido_id,))
    finally:
        con.close()

    print(f"cozinha: pedido {pedido_id} pronto!", flush=True)
    # so confirma depois de ter terminado tudo
    canal.basic_ack(metodo.delivery_tag)


def main():
    con = conectar_fila()
    canal = con.channel()
    canal.queue_declare(queue=FILA, durable=True)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue=FILA, on_message_callback=ao_receber)
    print("cozinha aberta, esperando pedidos...", flush=True)
    canal.start_consuming()


if __name__ == "__main__":
    main()
