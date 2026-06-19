from app import app, run_light_migrations, seed_if_empty

with app.app_context():
    run_light_migrations()
    seed_if_empty()
    print('Banco preparado. Login demo/admin: demo@nodo.com / 12345678')
