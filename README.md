# Nodo V3.2

Versão focada em design, logo oficial, correção da conta demo, admin por e-mail, chat via REST/polling, cosméticos melhores e economia de Nodo Coins mais controlada.

## Principais mudanças

- Logo oficial adicionada no frontend em `frontend/src/assets/nodo-logo.jpg`.
- Tela inicial refeita com visual mais profissional.
- Layout interno redesenhado: sidebar, cards, loja, chat, comunidade e dashboard.
- Conta demo automática removida.
- Login `demo@nodo.com` bloqueado no backend.
- Admin por e-mail via `ADMIN_EMAILS`.
- Nodo Coins reduzidos: cadastro começa com 5 NC, check-in dá 1 NC e missões dão 1–3 NC por padrão.
- Loja com cosméticos visuais mais trabalhados.
- Chat geral, chat de Nodos e DM funcionam por endpoint REST `/api/chat/message`, com polling de histórico.
- Backend sem eventlet, usando `threading` para evitar erro no Render.

## Render

Start Command recomendado:

```bash
gunicorn --workers 1 --threads 100 --timeout 120 app:app
```

Variáveis importantes:

```env
PYTHON_VERSION=3.11.9
CLIENT_ORIGIN=https://nodo-v3.vercel.app
ADMIN_EMAILS=pedwyz73@gmail.com
```

Não coloque senha no código ou nas variáveis públicas. O admin é definido pelo e-mail da conta.
