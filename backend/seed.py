from app import app, run_light_migrations, seed_if_empty

with app.app_context():
    run_light_migrations()
    seed_if_empty()
    print('Banco preparado. Conta demo automática desativada.')
