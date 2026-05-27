# LarDoceLar PDV

API REST de **ponto de venda (PDV)** para gestão de vendas, caixa, estoque e relatórios, pensada para uso em doceria ou comércio de pequeno porte.

## Funcionalidades

- **Dashboard interativo com resumo do dia**: 🏠 Tela inicial moderna com cards interativos de vendas do dia, pedidos fechados, pedidos abertos e total em fiado pendente. Possui efeitos de elevação visual no hover e cliques de navegação rápida direto para "Pedidos Abertos" e "Fiado".
- **Pedidos com Desconto e Observações**: 🛒 Possibilidade de aplicar descontos em reais (R$) nos pedidos no PDV e adicionar observações/anotações personalizadas (ex: "Sem cebola", "Entrega no balcão").
- **Busca de produtos e Filtro de Categorias no PDV**: 🔍 Barra de pesquisa em tempo real combinada com filtros rápidos do tipo chips/tags para categorias ("Todos", "Doces", "Salgados", etc.).
- **Seleção e edição rápida de quantidade no PDV**: ➕ Mini modal ao clicar no produto para definir a quantidade a adicionar, e ajuste inline de quantidade direto no carrinho de compras.
- **Sanfona/Acordeão dinâmico na listagem de pedidos**: 📋 Visualização imediata dos itens, quantidades, preços, desconto e totais diretamente abaixo da linha correspondente do pedido na tabela ao clicar em "Ver", com efeitos suaves de transição.
- **Impressão de Cupom Térmico (Bobina 80mm)**: 🖨️ Sistema híbrido inteligente otimizado para bobinas térmicas (como a TANCA TP-650):
  - **Impressão direta via Socket TCP**: Envio silencioso e instantâneo via socket de rede direto para a impressora local no IP `192.168.5.98` na porta `9100` usando comandos RAW ESC/POS, ideal para velocidade extrema ao rodar o servidor local.
  - **Contingência no Navegador (Chrome/Nuvem)**: Abertura automática de janela otimizada no padrão do Google Chrome para impressão local rápida, garantindo compatibilidade total com a nuvem do Render.
- **Usuários e autenticação**: cadastro de usuários com papéis `admin` e `cashier`; login que retorna um token UUID usado nas demais requisições.
- **Produtos**: CRUD (criação e alteração restritas a admin); listagem com filtro de produtos ativos.
- **Caixa**: abertura e fechamento de sessão, suprimento, sangria, fluxo de caixa e integração com vendas fechadas.
- **Estoque**: entrada, saída e ajuste de quantidade; alerta de estoque baixo; baixa automática no checkout quando há quantidade suficiente.
- **Relatórios**: resumo diário por data (totais e agrupamento por forma de pagamento).

## Stack

| Componente | Tecnologia |
|------------|------------|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) |
| Frontend | HTML, CSS e JavaScript (SPA servida pelo FastAPI) |
| Validação | Pydantic |
| ORM | SQLAlchemy |
| Banco de dados | PostgreSQL (driver `psycopg2`) |
| Servidor ASGI | Uvicorn |

## Requisitos

- Python 3.10+ (recomendado 3.11 ou superior)
- PostgreSQL com um banco criado para a aplicação (o projeto espera o nome configurado em `database/connection.py`)

## Configuração do banco

A URL de conexão vem da variável de ambiente **`DATABASE_URL`** (não versionar credenciais no Git).

1. Copie `.env.example` para `.env`
2. Ajuste usuário, senha, host, porta e nome do banco no `.env`

No PowerShell, antes de subir a API:

```powershell
$env:DATABASE_URL = "postgresql+psycopg2://usuario:senha@127.0.0.1:5432/LarDoceLar"
```

Na primeira execução, o SQLAlchemy cria as tabelas com `Base.metadata.create_all` ao importar o aplicativo.

## Instalação

```powershell
cd LarDoceLar
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*(Se já existir um `venv` no projeto, ative-o e rode `pip install -r requirements.txt`.)*

## Como executar

```powershell
.\venv\Scripts\Activate.ps1
# Carregue DATABASE_URL (arquivo .env ou variável de ambiente)
$env:DATABASE_URL = "postgresql+psycopg2://usuario:senha@127.0.0.1:5432/LarDoceLar"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Documentação interativa (Swagger): `http://127.0.0.1:8000/docs`
- **Interface web (PDV)**: `http://127.0.0.1:8000/`
- Esquema OpenAPI em JSON: `http://127.0.0.1:8000/openapi.json`

## Autenticação

1. **Primeiro usuário**: `POST /users` sem token — o primeiro cadastro é forçado como `admin`.
2. **Demais usuários**: `POST /users` exige header `X-Token` de um usuário **admin**.
3. **Login**: `POST /auth/login` com `name` e `password` retorna `token`.
4. **Requisições protegidas**: envie o token no header **`X-Token`**.

## Papéis (`role`)

| Papel | Descrição resumida |
|-------|-------------------|
| `admin` | Produtos, usuários, caixa (abrir/fechar), cancelamento de pedido, estoque, relatórios, fluxo de caixa |
| `cashier` | Pedidos, suprimento de caixa, consulta de estoque baixo |

## Estrutura do repositório

```
LarDoceLar/
├── main.py              # Aplicação FastAPI e rotas
├── frontend/            # Interface web (PDV)
│   ├── index.html
│   ├── css/app.css
│   └── js/
├── database/
│   └── connection.py   # Engine SQLAlchemy e sessão
└── models/             # Modelos ORM (usuários, pedidos, produtos, caixa, estoque, etc.)
```

## Observações de segurança (produção)

- Os tokens de sessão ficam **em memória** (`TOKENS`); ao reiniciar o servidor, é necessário fazer login novamente.
- Senhas são armazenadas como hash SHA-256; para ambientes críticos avalie algoritmos dedicados (por exemplo bcrypt/argon2) e HTTPS obrigatório.
- Não versionar credenciais reais: use variáveis de ambiente ou cofre de segredos para `DATABASE_URL`.

## Licença

Defina a licença do projeto conforme a decisão da equipe (este repositório não inclui arquivo de licença por padrão).
