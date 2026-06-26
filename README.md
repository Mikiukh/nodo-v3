# Nodo V3.3

Versão focada em design limpo, personalização estilo app social, admin completo e correção dos textos públicos da interface.

## O que mudou

- Logo oficial da Nodo mantida no frontend.
- Tela inicial mais limpa e profissional.
- Textos públicos encurtados: nada de termos internos como backend, REST ou detalhes técnicos.
- Nova aba **Personalizar**.
- Personalização de perfil com preview:
  - Moldura
  - Banner
  - Efeito
  - Selo
  - Nome
  - Tema
- Loja conectada com personalização.
- Cosméticos com raridade: comum, raro, épico e lendário.
- Nodo Coins mais controlados.
- Admin com mais acesso:
  - usuários
  - posts
  - Nodos/grupos
  - missões
  - loja/cosméticos
  - dar/remover ADM
  - ajustar XP/NC
  - apagar posts, grupos, missões e itens da loja
- Chat geral, chat de grupo e DM mantidos por API/polling.
- Conta demo bloqueada.
- Admin definido por e-mail em `ADMIN_EMAILS`.
- Backend sem eventlet.

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

Não coloque senha no código. Admin é liberado pelo e-mail da conta.
