# Comandas Backend

API backend para gerenciamento de comandas, clientes, funcionários e produtos.

O projeto usa FastAPI com SQLAlchemy, autenticação JWT, rate limiting e configuração por variáveis de ambiente.

## Stack

- Python 3.12+
- FastAPI
- Uvicorn para desenvolvimento local
- Hypercorn para execução em container com HTTPS/QUIC
- SQLAlchemy
- SQLite para desenvolvimento local com `uv run dev`
- MySQL no Docker Compose
- `uv` para ambiente, dependências e execução local

## Como Rodar Localmente

Na raiz do projeto:

```bash
uv run dev
```

A API ficará disponível em:

```text
http://127.0.0.1:8000/docs
```

O comando `uv run dev`:

- cria/usa o ambiente virtual `.venv`;
- instala as dependências a partir do `uv.lock`;
- executa o FastAPI com reload;
- usa SQLite por padrão no desenvolvimento local.

## Como Rodar Com Docker

Na raiz do projeto:

```bash
docker compose -f compose.yml up --build
```

O Docker Compose sobe:

- `db`: banco MySQL 8;
- `comandas_api`: API FastAPI servida por Hypercorn.

No Docker, o host `db` usado no `.env` funciona porque é o nome do serviço MySQL dentro da rede do Compose.

## Variáveis de Ambiente

O projeto carrega configurações do arquivo `.env`.

Principais variáveis:

```env
HOST=
PORT=
RELOAD=

DB_SGDB=
DB_NAME=
DB_HOST=
DB_USER=
DB_PASS=
DB_PORT=

SECRET_KEY=
ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=
REFRESH_TOKEN_EXPIRE_DAYS=

RATE_LIMIT_CRITICAL=
RATE_LIMIT_RESTRICTIVE=
RATE_LIMIT_MODERATE=
RATE_LIMIT_LOW=
RATE_LIMIT_LIGHT=
RATE_LIMIT_DEFAULT=

CORS_ORIGINS=
```

Para desenvolvimento local com `uv run dev`, o entrypoint força SQLite por padrão antes da aplicação carregar o `.env`.

## Arquitetura

O projeto está organizado em camadas simples:

```text
src/
├── main.py                 # cria a aplicação FastAPI e registra rotas/middlewares
├── dev.py                  # comando local usado por `uv run dev`
├── settings.py             # leitura de variáveis de ambiente e string de conexão
├── routers/                # endpoints da API
├── services/               # regras de negócio e serviços auxiliares
├── domain/schemas/         # schemas Pydantic de entrada/saída
└── infra/
    ├── database.py         # configuração de banco e criação de tabelas
    ├── dependencies.py     # dependências compartilhadas do FastAPI
    ├── security.py         # autenticação/JWT
    ├── rate_limit.py       # rate limiting
    ├── middleware/         # middlewares customizados
    └── orm/                # modelos SQLAlchemy
```

### Fluxo Principal

```text
Cliente HTTP
  -> routers/
  -> services/
  -> infra/orm/
  -> database
```

## Endpoints Principais

As rotas são registradas em `src/main.py`:

- Auditoria
- Autenticação
- Funcionários
- Clientes
- Produtos
- Comandas
- Health check

A documentação interativa fica em:

```text
/docs
```

## Arquivos Importantes

- `pyproject.toml`: configuração do projeto Python, dependências e script `dev`.
- `uv.lock`: versões travadas das dependências usadas pelo `uv`.
- `src/dev.py`: entrypoint local para desenvolvimento.
- `compose.yml`: serviços Docker da API e MySQL.
- `Dockerfile`: imagem da API para execução com Hypercorn.
- `.env`: configuração local e de container.
- `.gitignore`: ignora caches, `.venv` e arquivos gerados.

## Comandos Úteis

Rodar local:

```bash
uv run dev
```

Sincronizar dependências:

```bash
uv sync
```

Rodar Docker:

```bash
docker compose -f compose.yml up --build
```

Parar Docker:

```bash
docker compose -f compose.yml down
```
