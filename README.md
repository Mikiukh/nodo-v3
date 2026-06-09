# Nodo V3

Atualizações:
- Dashboard sem texto de escola.
- Comunidade com posts.
- Aba Nodos para criar/entrar em nodos.
- Aba Grupos mostrando nodos criados ou que você entrou.
- Chat privado dentro de cada nodo.
- Lista de pessoas no nodo.
- Amigos com busca por nome de usuário.
- Chat geral.
- IA renomeada para Nodo AI.
- Missões exigem resposta escrita para ganhar XP.
- Perfil com nome, email, telefone, descrição, foto leve e troca de senha.
- Responsivo para PC e celular.

## Rodar

Backend:
```bash
cd ~/Downloads/nodo-v3/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
python app.py
```

Frontend:
```bash
cd ~/Downloads/nodo-v3/frontend
npm install
npm run dev
```

Abrir: http://localhost:5173

Demo: demo@nodo.com / 12345678
