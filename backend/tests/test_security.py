import os
import tempfile
import unittest

fd, database_path = tempfile.mkstemp(prefix='nodo-v4-test-', suffix='.db')
os.close(fd)
os.environ['DATABASE_URL'] = f'sqlite:///{database_path}'
os.environ['SECRET_KEY'] = 'test-secret-key-01234567890123456789'
os.environ['JWT_SECRET'] = 'test-jwt-key-012345678901234567890'
os.environ['CLIENT_ORIGIN'] = 'http://localhost:5173'
os.environ['ADMIN_EMAILS'] = 'admin@example.com'

from app import app, initialize_database, socketio  # noqa: E402
from models import db, Friend, User  # noqa: E402
from security import hash_password  # noqa: E402


class NodoSecuritySmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        with app.app_context():
            initialize_database()
            admin = User(
                username='Admin',
                email='admin@example.com',
                password_hash=hash_password('abcdefghij'),
            )
            db.session.add(admin)
            db.session.commit()
            app._nodo_db_ready = False
            initialize_database()
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            os.remove(database_path)
        except OSError:
            pass

    def register(self, username, email):
        response = self.client.post('/api/auth/register', json={
            'username': username,
            'email': email,
            'password': 'abcdefghij',
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()['token']

    def login_admin(self):
        response = self.client.post('/api/auth/login', json={
            'email': 'admin@example.com',
            'password': 'abcdefghij',
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()['token']

    def auth(self, token):
        return {'Authorization': f'Bearer {token}'}

    def test_room_authorization_and_token_revocation(self):
        first = self.register('UserOne', 'one@example.com')
        second = self.register('UserTwo', 'two@example.com')
        admin = self.login_admin()

        group_response = self.client.post('/api/groups', headers=self.auth(first), json={'name': 'Grupo Teste'})
        group_id = group_response.get_json()['group_id']
        denied = self.client.get(f'/api/chat/history?room=group:{group_id}', headers=self.auth(second))
        self.assertEqual(denied.status_code, 403)
        allowed_admin = self.client.get(f'/api/chat/history?room=group:{group_id}', headers=self.auth(admin))
        self.assertEqual(allowed_admin.status_code, 200)

        with app.app_context():
            first_id = User.query.filter_by(email='one@example.com').one().id
            second_id = User.query.filter_by(email='two@example.com').one().id
        dm_room = f'dm:{min(first_id, second_id)}:{max(first_id, second_id)}'
        denied_dm = self.client.get(f'/api/chat/history?room={dm_room}', headers=self.auth(first))
        self.assertEqual(denied_dm.status_code, 403)
        request_response = self.client.post(f'/api/friends/{second_id}', headers=self.auth(first))
        self.assertEqual(request_response.status_code, 200)
        with app.app_context():
            friend_id = Friend.query.filter_by(requester_id=first_id, addressee_id=second_id).one().id
        accepted = self.client.post(f'/api/friends/{friend_id}/accept', headers=self.auth(second))
        self.assertEqual(accepted.status_code, 200)
        allowed_dm = self.client.get(f'/api/chat/history?room={dm_room}', headers=self.auth(first))
        self.assertEqual(allowed_dm.status_code, 200)

        socket_client = socketio.test_client(app)
        socket_client.emit('join', {'token': 'invalid', 'room': 'global'})
        invalid_events = socket_client.get_received()
        self.assertTrue(any(event['name'] == 'system' for event in invalid_events))
        socket_client.emit('join', {'token': first, 'room': dm_room})
        joined_events = socket_client.get_received()
        self.assertTrue(any(event['name'] == 'system' for event in joined_events))
        socket_client.emit('message', {'token': first, 'room': dm_room, 'content': 'Mensagem por socket'})
        message_events = socket_client.get_received()
        payloads = [event.get('args') for event in message_events if event.get('name') == 'message']
        self.assertTrue(any((payload[0] if isinstance(payload, list) else payload).get('content') == 'Mensagem por socket' for payload in payloads))
        socket_client.disconnect()

        changed = self.client.put('/api/me/password', headers=self.auth(first), json={
            'current_password': 'abcdefghij',
            'new_password': 'abcdefghijk',
        })
        self.assertEqual(changed.status_code, 200)
        old_session = self.client.get('/api/me', headers=self.auth(first))
        self.assertEqual(old_session.status_code, 401)

        banned = self.client.patch(f'/api/admin/users/{second_id}', headers=self.auth(admin), json={'is_banned': True})
        self.assertEqual(banned.status_code, 200)
        blocked = self.client.get('/api/me', headers=self.auth(second))
        self.assertEqual(blocked.status_code, 403)


if __name__ == '__main__':
    unittest.main()
