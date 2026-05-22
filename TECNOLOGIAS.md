# LarDoceLar PDV - Stack de Tecnologias

Este documento resume as tecnologias, bibliotecas e ferramentas utilizadas no desenvolvimento e funcionamento do sistema de Ponto de Venda (PDV) da LarDoceLar.

## 🎨 Frontend (Interface do Usuário)
O frontend foi construído de forma **nativa (Vanilla)**, sem o uso de frameworks pesados (como React ou Angular), garantindo um sistema ultraleve, rápido e de fácil manutenção.

*   **HTML5 & CSS3:** Estruturação semântica e estilização moderna usando CSS Flexbox, Grid Layout e CSS Variables para temas e cores consistentes.
*   **Vanilla JavaScript (ES6+):** Toda a interatividade, controle de estado, renderização de telas (SPA) e comunicação com o backend foram feitas em JS puro.
*   **Fetch API:** Utilizado para comunicação assíncrona (requisições HTTP) com o servidor.
*   **Google Fonts:** Utilização da família tipográfica **DM Sans** para um design moderno, legível e profissional.
*   **CSS Print Media Queries (`@media print`):** Para geração de relatórios limpos, escondendo menus e gerando folhas PDF nativas direto pelo navegador.

## ⚙️ Backend (Servidor e Lógica de Negócios)
O backend foi construído em Python, focado em alta performance e código limpo através de rotas assíncronas.

*   **Python 3:** Linguagem principal do servidor.
*   **FastAPI:** Framework web assíncrono e de alto desempenho utilizado para criar toda a API RESTful do sistema.
*   **Uvicorn:** Servidor web ASGI ultra-rápido para rodar a aplicação FastAPI.
*   **SQLAlchemy (ORM):** Biblioteca de Mapeamento Objeto-Relacional para interagir com o banco de dados usando objetos Python sem precisar escrever SQL puro o tempo todo.
*   **Pydantic:** Utilizado para validação estrita de dados e tipagem de entrada/saída das rotas (schemas).
*   **python-dotenv:** Gerenciamento de variáveis de ambiente de forma segura (`.env`).
*   **Pillow (PIL):** Biblioteca de processamento de imagens (utilizada em scripts para tratar a transparência da logomarca/ícones).

## 🗄️ Banco de Dados
A aplicação foi desenvolvida para ser híbrida em relação ao banco de dados, utilizando o SQLAlchemy como ponte.

*   **SQLite:** Banco de dados relacional em arquivo local, utilizado principalmente para desenvolvimento e testes rápidos.
*   **PostgreSQL (psycopg2-binary):** SGBD relacional robusto e escalável, utilizado no ambiente de produção para garantir integridade e performance (hospedado no provedor de nuvem).

## 🚀 DevOps e Hospedagem
*   **Git & GitHub:** Controle de versão para salvar, rastrear o histórico e gerenciar o código-fonte (repositório `Gui2909/LarDoceLar`).
*   **Render:** Plataforma (PaaS) utilizada para hospedar tanto o banco de dados PostgreSQL quanto a própria aplicação web e API online.
*   **Ambientes Virtuais (venv / pip):** Gerenciamento e isolamento das dependências do Python.
