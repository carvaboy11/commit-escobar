# Taverna do Javali Dourado

Junta as aulas de 19/10 (Docker) e 26/10 (microsserviços e mensageria).

O cliente faz um pedido na API, que guarda tudo no MySQL, manda o pedido pro
RabbitMQ e já responde. A cozinha (um worker separado) pega o pedido da fila,
prepara e marca `pronto = true` no banco.

```
curl  ->  api  ->  mysql
           |
           v
        rabbitmq  ->  cozinha  ->  mysql
```

## Rodando

```
cp .env.example .env        # no powershell: copy .env.example .env
docker compose up -d --build
docker compose ps
```

Precisa aparecer `db` e `rabbitmq` como healthy.

## Fazendo um pedido

```
curl http://localhost:8000/saude
curl http://localhost:8000/pedidos

curl -X POST http://localhost:8000/pedidos -H "Content-Type: application/json" -d '{"cliente":"Thorin","item":"Hidromel"}'

docker compose logs -f cozinha
curl http://localhost:8000/pedidos
```

O POST responde com `pronto: false`. Uns 2 segundos depois a cozinha termina e o
GET já mostra `true`. No PowerShell use `curl.exe` e escape as aspas do json, ou
use o Swagger em http://localhost:8000/docs.

O painel do RabbitMQ fica em http://localhost:15672 (usuário e senha do `.env`).

## Cozinha fechada

```
docker compose stop cozinha
# faz uns 3 pedidos com o curl de cima
docker compose exec rabbitmq rabbitmqctl list_queues name messages_ready
docker compose start cozinha
docker compose logs -f cozinha
```

Com a cozinha parada a API continua aceitando pedidos, eles esperam na fila e
são preparados quando ela volta.

## Persistência

```
docker compose down
docker compose up -d
curl http://localhost:8000/pedidos      # os pedidos continuam la
```

`docker compose down -v` apaga o volume do MySQL (e roda o `init.sql` de novo).

## Testes e CI

```
cd api
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Os testes não precisam de banco nem de fila, eles trocam `inserir` e `publicar`
por funções falsas. O `.github/workflows/ci.yml` roda esse mesmo pytest a cada
push e, se passar, constrói as duas imagens. Só publica no GHCR quando é push
na main.

## Problemas comuns

| erro | causa | solução |
|---|---|---|
| Can't connect to MySQL on 'localhost' | DB_HOST errado dentro do contêiner | DB_HOST=db |
| Access denied for user | mudou a senha do .env depois do volume criado | docker compose down -v |
| tabela ou coluna nova não aparece | init.sql só roda quando o volume é criado | docker compose down -v |
| porta 8000 ocupada | outro processo usando | trocar para "8001:8000" no compose |

## Limitação conhecida

Se o RabbitMQ estiver fora do ar na hora do POST, o pedido é salvo mas a cozinha
nunca fica sabendo (fica `pronto = false` pra sempre). Dá pra resolver com um
processo que reenvia os pedidos pendentes, ou com o padrão outbox.

## Versões

Usei `mysql:8.4` e `python:3.12-slim`. Se quiser igual ao da aula, troque por
`mysql:9.7` e `python:3.14-slim`.
