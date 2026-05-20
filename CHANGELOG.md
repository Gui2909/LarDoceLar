# Changelog

## [Unreleased]

### Added

- Documentação do projeto em `README.md` (instalação, execução, autenticação e visão geral da API).
- `.gitignore` para excluir `venv/`, caches e `.env` do versionamento.
- `requirements.txt` e `.env.example` para publicação no GitHub.
- **Frontend web** em `frontend/` (login, PDV, produtos, estoque, caixa, relatórios e usuários).
- Endpoints auxiliares: `GET /auth/setup`, `GET /cash/status`, `GET /stock`, `GET /users`.
- Migração automática de schema (`database/migrations.py`) para bancos criados com versão antiga das tabelas.

### Changed

- `DATABASE_URL` lida via variável de ambiente (credenciais removidas do código versionado).
- `GET /orders/{id}` retorna nome do produto nos itens do pedido.
- Raiz `/` serve a interface do PDV.

### Fixed

- Erro 500 em `/products` e demais rotas quando o PostgreSQL não tinha colunas `is_active`, `status` e campos de `cash_flow`.

### Build / QA

- **Build**: importação de `main` com migrações aplicadas; consulta a `products` validada após patch de schema.
- **Testes**: não há suíte de testes automatizada no repositório; não executado nesta alteração.
- **Cobertura**: não aplicável enquanto não existir projeto de testes.
