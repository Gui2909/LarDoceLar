# Changelog

## [Unreleased]

### Added

- Documentação do projeto em `README.md` (instalação, execução, autenticação e visão geral da API).
- `.gitignore` para excluir `venv/`, caches e `.env` do versionamento.
- `requirements.txt` e `.env.example` para publicação no GitHub.

### Changed

- `DATABASE_URL` lida via variável de ambiente (credenciais removidas do código versionado).

### Build / QA

- **Build**: importação de `main` com o interpretador do `venv` concluída com sucesso (`LarDoceLar PDV`).
- **Testes**: não há suíte de testes automatizada no repositório; não executado nesta alteração.
- **Cobertura**: não aplicável enquanto não existir projeto de testes.
