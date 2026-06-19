# Nodo V3.1

Versão feita em cima da Nodo V3, sem recomeçar do zero.

## O que mudou

- Design geral mais bonito e moderno.
- Dashboard novo com XP, level, streak, Nodo Coins e posição no ranking.
- Ranking global.
- Nodo Coins.
- Check-in diário.
- Streak diário.
- Loja simples de cosméticos.
- Cursos/trilhas iniciais.
- Painel Admin simples.
- Perfil público/privado separado: email e telefone não aparecem mais em posts, ranking, amigos e grupos.
- Socket do chat agora tenta usar token para não confiar no username enviado pelo cliente.
- Backend preparado para SQLite local e Postgres externo via `DATABASE_URL`.
- Frontend com Vite e `vercel.json` para SPA.

## Rodar local

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
python app.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://localhost:5173
```

Conta demo/admin:

```text
demo@nodo.com / 12345678
```

## Variáveis importantes

Backend:

```text
SECRET_KEY=troque_essa_chave
JWT_SECRET=troque_esse_jwt
OPENAI_API_KEY=
CLIENT_ORIGIN=http://localhost:5173
DATABASE_URL=sqlite:///nodo.db
ADMIN_EMAIL=demo@nodo.com
```

Frontend:

```text
VITE_API_URL=http://localhost:5000
VITE_SOCKET_URL=http://localhost:5000
```

## Trocar a V3 pela V3.1 sem quebrar

1. Faça backup da pasta/repositório atual.
2. Copie os arquivos da V3.1 por cima da V3.
3. Rode local primeiro.
4. Suba em uma branch nova, por exemplo `nodo-v3-1`.
5. Deixe a Vercel gerar Preview Deploy.
6. Teste login, dashboard, missões, ranking, loja e admin.
7. Só depois faça merge/push para a branch de produção.

