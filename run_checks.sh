#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT/backend"
python3 -m py_compile app.py models.py security.py seed.py
if python3 -c 'import flask, flask_sqlalchemy, flask_socketio, bcrypt, jwt' >/dev/null 2>&1; then
  python3 -m unittest discover -s tests -v
else
  echo "Dependências do backend não instaladas; teste funcional pulado."
fi

cd "$ROOT/frontend"
npm install
npm run build
npm audit --omit=dev

echo "Nodo V4.0: verificações concluídas."
