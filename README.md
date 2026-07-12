# Nodo V4.0 LTS

A Nodo é uma plataforma social de estudos para programação com comunidade, missões, XP, Nodo Coins, Nodos, chat, amigos, loja, personalização, conquistas, notificações, Nodo AI e painel ADM.

## O que muda na V4.0

- Interface refeita com estrutura de aplicativo de comunidade e identidade própria da Nodo.
- Chat em tempo real com Socket.IO e reconexão automática.
- Autorização real para chat de Nodos e mensagens diretas.
- Sessões revogadas após troca de senha, banimento ou alteração de permissão.
- Conta ADM protegida por variável de ambiente e bloqueio do e-mail reservado no cadastro.
- Painel ADM com usuários, posts, Nodos, denúncias, missões, loja e logs de ações.
- Pesquisa global.
- PWA instalável no celular e computador.
- Frontend separado em `App.jsx`, `api.js`, `ui.jsx` e `main.jsx`.
- Dependências fixadas, sem `latest`.
- Tratamento de erros, limites de requisição e validações reforçadas.

## Estrutura

```text
backend/
  app.py
  models.py
  security.py
  seed.py
  requirements.txt
frontend/
  src/App.jsx
  src/api.js
  src/ui.jsx
  src/main.jsx
  src/style.css
  public/
```

## Ambiente local

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Produção

Leia `TUTORIAL_NODO_V4_0_DEPLOY.txt` antes de substituir a versão atual.

O comando do Render continua:

```bash
gunicorn --workers 1 --threads 100 --timeout 120 app:app
```

Não coloque `python seed.py &&` no Start Command.

## Segurança

Leia `SECURITY_REVIEW_NODO_V4_0.txt`. Esta versão recebeu revisão e testes automatizados, mas isso não substitui auditoria profissional ou teste de invasão autorizado.
