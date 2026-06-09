from app import app
from models import db, User, Mission
from security import hash_password
with app.app_context():
    db.drop_all(); db.create_all()
    db.session.add(User(username='Demo Nodo', email='demo@nodo.com', password_hash=hash_password('12345678'), avatar='🚀', bio='Conta de teste da Nodo.'))
    db.session.add_all([
        Mission(title='Primeiro script Python', description='Explique como criaria um script Python que imprime uma mensagem no terminal.', category='Programação', xp_reward=50),
        Mission(title='Página HTML pessoal', description='Explique quais tags HTML usaria para criar uma página com nome, descrição e links.', category='Web', xp_reward=70),
        Mission(title='Segurança de conta', description='Explique pelo menos 5 formas de proteger uma conta online contra invasões.', category='Cyber ético', xp_reward=80),
        Mission(title='GitHub básico', description='Explique o passo a passo para criar um repositório e enviar um projeto usando Git.', category='Dev', xp_reward=90),
        Mission(title='XSS na defesa', description='Explique o que é XSS e como um desenvolvedor pode prevenir esse tipo de falha.', category='Cyber ético', xp_reward=100),
    ])
    db.session.commit(); print('Banco preparado. Login demo: demo@nodo.com / 12345678')
