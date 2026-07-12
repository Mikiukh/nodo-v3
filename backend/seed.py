from app import app, initialize_database


with app.app_context():
    initialize_database()
    print('Banco preparado. Nenhuma conta demo foi criada.')
