# Nodo V3.4 — Discord UI + Social Core

A Nodo é uma plataforma social de estudos para programação com comunidade, missões, XP, Nodo Coins, Nodos/grupos, chat, loja, personalização e painel admin.

## Novidades da V3.4

- Interface reorganizada no estilo de aplicativo de comunidade, inspirada na experiência do Discord, mas com identidade própria da Nodo.
- Barra lateral de Nodos, canais, área principal e painel de atividade.
- Comunidade com curtidas, comentários e denúncias.
- Amigos com pedido de amizade e DM.
- Chat geral e chat de grupos com visual mais limpo.
- Conquistas.
- Notificações.
- Feed de atividade.
- Loja e personalização com cosméticos equipáveis.
- Painel Admin mais forte.
- Melhorias de segurança no backend.

## Variáveis importantes

No Render, configure:

```env
PYTHON_VERSION=3.11.9
SECRET_KEY=troque_por_uma_chave_forte
JWT_SECRET=troque_por_uma_chave_jwt_forte
CLIENT_ORIGIN=https://nodo-v3.vercel.app
ADMIN_EMAILS=pedwyz73@gmail.com
OPENAI_API_KEY=
DATABASE_URL=
```

Para produção, use Postgres em `DATABASE_URL`. SQLite funciona para testes, mas não é ideal para produção.

## Start Command no Render

```bash
gunicorn --workers 1 --threads 100 --timeout 120 app:app
```

Não use `python seed.py &&` no Start Command.

## Testes feitos na versão empacotada

```bash
python3 -m py_compile app.py models.py seed.py security.py
npm run build
```
