import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from openai import OpenAI
from models import db, User, Friend, Group, Post, ChatMessage, Mission, CompletedMission
from security import hash_password, verify_password, make_token, require_auth

app=Flask(__name__); app.config['SECRET_KEY']=os.getenv('SECRET_KEY','dev'); app.config['SQLALCHEMY_DATABASE_URI']=os.getenv('DATABASE_URL','sqlite:///nodo.db'); app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
CORS(app, resources={r'/api/*': {'origins': os.getenv('CLIENT_ORIGIN','*')}})
socketio=SocketIO(app, cors_allowed_origins='*', async_mode='threading'); db.init_app(app)
def user_public(u): return {'id':u.id,'username':u.username,'email':u.email,'phone':u.phone,'bio':u.bio,'avatar':u.avatar,'xp':u.xp,'level':u.level}
@app.get('/api/health')
def health(): return {'ok':True}
@app.post('/api/auth/register')
def register():
    d=request.json or {}; username=(d.get('username') or '').strip(); email=(d.get('email') or '').strip().lower(); password=d.get('password') or ''
    if len(username)<3: return jsonify({'error':'Nome precisa ter pelo menos 3 caracteres'}),400
    if '@' not in email: return jsonify({'error':'Email inválido'}),400
    if len(password)<8: return jsonify({'error':'Senha precisa ter pelo menos 8 caracteres'}),400
    if User.query.filter_by(email=email).first(): return jsonify({'error':'Email já cadastrado'}),400
    u=User(username=username,email=email,password_hash=hash_password(password)); db.session.add(u); db.session.commit(); return {'token':make_token(u.id),'user':user_public(u)}
@app.post('/api/auth/login')
def login():
    d=request.json or {}; u=User.query.filter_by(email=(d.get('email') or '').strip().lower()).first()
    if not u or not verify_password(d.get('password') or '', u.password_hash): return jsonify({'error':'Email ou senha inválidos'}),401
    return {'token':make_token(u.id),'user':user_public(u)}
@app.get('/api/me')
@require_auth
def me(): return {'user':user_public(User.query.get_or_404(request.user_id))}
@app.put('/api/me')
@require_auth
def update_me():
    u=User.query.get_or_404(request.user_id); d=request.json or {}
    if d.get('username') and len(d['username'].strip())>=3: u.username=d['username'].strip()[:80]
    if d.get('email') and '@' in d['email']:
        email=d['email'].strip().lower(); exists=User.query.filter(User.email==email, User.id!=u.id).first()
        if exists: return jsonify({'error':'Esse email já está em uso'}),400
        u.email=email
    if 'phone' in d: u.phone=(d.get('phone') or '')[:30]
    if 'bio' in d: u.bio=(d.get('bio') or '')[:500]
    if 'avatar' in d:
        av=d.get('avatar') or '👨‍💻'
        if len(av)>250000: return jsonify({'error':'Imagem muito pesada'}),400
        u.avatar=av
    db.session.commit(); return {'user':user_public(u)}
@app.put('/api/me/password')
@require_auth
def update_password():
    u=User.query.get_or_404(request.user_id); d=request.json or {}
    if not verify_password(d.get('current_password') or '', u.password_hash): return jsonify({'error':'Senha atual incorreta'}),400
    if len(d.get('new_password') or '')<8: return jsonify({'error':'Nova senha precisa ter pelo menos 8 caracteres'}),400
    u.password_hash=hash_password(d['new_password']); db.session.commit(); return {'message':'Senha alterada'}
@app.get('/api/users')
@require_auth
def search_users():
    q=(request.args.get('q') or '').strip(); query=User.query
    if q: query=query.filter(User.username.ilike(f'%{q}%'))
    return {'users':[user_public(u) for u in query.limit(30).all() if u.id!=request.user_id]}
@app.post('/api/friends/<int:user_id>')
@require_auth
def add_friend(user_id):
    if user_id==request.user_id: return jsonify({'error':'Você não pode adicionar você mesmo'}),400
    if not User.query.get(user_id): return jsonify({'error':'Usuário não encontrado'}),404
    exists=Friend.query.filter(((Friend.requester_id==request.user_id)&(Friend.addressee_id==user_id))|((Friend.requester_id==user_id)&(Friend.addressee_id==request.user_id))).first()
    if not exists: db.session.add(Friend(requester_id=request.user_id, addressee_id=user_id)); db.session.commit()
    return {'message':'Amigo adicionado'}
@app.get('/api/friends')
@require_auth
def friends():
    rows=Friend.query.filter(((Friend.requester_id==request.user_id)|(Friend.addressee_id==request.user_id)), Friend.status=='accepted').all(); ids=[r.addressee_id if r.requester_id==request.user_id else r.requester_id for r in rows]
    users=User.query.filter(User.id.in_(ids)).all() if ids else []; return {'friends':[user_public(u) for u in users]}
@app.get('/api/groups')
@require_auth
def list_groups():
    gs=Group.query.order_by(Group.created_at.desc()).all(); return {'groups':[{'id':g.id,'name':g.name,'description':g.description,'topic':g.topic,'owner_id':g.owner_id,'members_count':len(g.members),'is_member':any(m.id==request.user_id for m in g.members)} for g in gs]}
@app.get('/api/my-groups')
@require_auth
def my_groups():
    u=User.query.get_or_404(request.user_id); return {'groups':[{'id':g.id,'name':g.name,'description':g.description,'topic':g.topic,'members_count':len(g.members)} for g in u.groups]}
@app.get('/api/groups/<int:gid>')
@require_auth
def group_detail(gid):
    g=Group.query.get_or_404(gid); return {'group':{'id':g.id,'name':g.name,'description':g.description,'topic':g.topic,'members_count':len(g.members),'members':[user_public(u) for u in g.members]}}
@app.post('/api/groups')
@require_auth
def create_group():
    d=request.json or {}; name=(d.get('name') or '').strip()
    if len(name)<3: return jsonify({'error':'Nome do grupo muito curto'}),400
    u=User.query.get_or_404(request.user_id); g=Group(name=name,description=(d.get('description') or '')[:400],topic=(d.get('topic') or 'Programação')[:80],owner_id=u.id,members=[u]); db.session.add(g); db.session.commit(); return {'message':'Nodo criado','group_id':g.id}
@app.post('/api/groups/<int:gid>/join')
@require_auth
def join_group(gid):
    g=Group.query.get_or_404(gid); u=User.query.get_or_404(request.user_id)
    if u not in g.members: g.members.append(u); db.session.commit()
    return {'message':'Você entrou no nodo'}
@app.get('/api/posts')
@require_auth
def list_posts():
    ps=Post.query.order_by(Post.created_at.desc()).limit(50).all(); return {'posts':[{'id':p.id,'content':p.content,'user':user_public(p.user),'created_at':p.created_at.isoformat()} for p in ps]}
@app.post('/api/posts')
@require_auth
def create_post():
    c=((request.json or {}).get('content') or '').strip()
    if len(c)<2: return jsonify({'error':'Digite algo'}),400
    db.session.add(Post(content=c[:1000], user_id=request.user_id)); db.session.commit(); return {'message':'Publicado'}
@app.get('/api/missions')
@require_auth
def missions():
    done={c.mission_id for c in CompletedMission.query.filter_by(user_id=request.user_id).all()}; ms=Mission.query.all(); return {'missions':[{'id':m.id,'title':m.title,'description':m.description,'category':m.category,'xp_reward':m.xp_reward,'completed':m.id in done} for m in ms]}
@app.post('/api/missions/<int:mid>/submit')
@require_auth
def submit_mission(mid):
    m=Mission.query.get_or_404(mid); ans=((request.json or {}).get('answer') or '').strip()
    if len(ans)<20: return jsonify({'error':'Resposta muito curta. Explique melhor para ganhar XP.'}),400
    if CompletedMission.query.filter_by(user_id=request.user_id, mission_id=mid).first(): return jsonify({'error':'Missão já concluída'}),400
    u=User.query.get_or_404(request.user_id); u.xp+=m.xp_reward; u.level=max(1,u.xp//150+1); db.session.add(CompletedMission(user_id=u.id, mission_id=m.id, answer=ans[:1200])); db.session.commit(); return {'message':'Resposta enviada. XP recebido!','user':user_public(u)}
@app.get('/api/chat/history')
@require_auth
def chat_history():
    room=request.args.get('room','global'); ms=ChatMessage.query.filter_by(room=room).order_by(ChatMessage.created_at.desc()).limit(80).all(); ms.reverse(); return {'messages':[{'id':m.id,'room':m.room,'content':m.content,'username':m.username,'user_id':m.user_id,'created_at':m.created_at.isoformat()} for m in ms]}
    @app.post("/api/chat/send")@require_auth
def chat_send():
    data = request.json or {}
    room = data.get("room", "global")
    content = (data.get("content") or "").strip()

    if not content:
        return jsonify({"error": "Mensagem vazia"}), 400

    user = User.query.get_or_404(request.user_id)

    msg = ChatMessage(
        room=room,
        content=content[:1000],
        username=user.username,
        user_id=user.id
    )

    db.session.add(msg)
    db.session.commit()

    return {
        "message": {
            "id": msg.id,
            "room": msg.room,
            "content": msg.content,
            "username": msg.username,
            "user_id": msg.user_id,
            "created_at": msg.created_at.isoformat()
        }
    }
@app.post('/api/ai')
@require_auth
def ai_chat():
    prompt=((request.json or {}).get('message') or '').strip(); key=os.getenv('OPENAI_API_KEY')
    if not prompt: return jsonify({'error':'Mensagem vazia'}),400
    if not key: return {'reply':'Nodo AI ainda não está configurada. Coloque sua OPENAI_API_KEY no arquivo backend/.env.'}
    try:
        client=OpenAI(api_key=key); resp=client.chat.completions.create(model='gpt-3.5-turbo', messages=[{'role':'system','content':'Você é a Nodo AI. Ajude com programação, projetos e segurança ética. Não ajude com invasão, golpes, malware ou crime.'},{'role':'user','content':prompt}], temperature=.4)
        return {'reply':resp.choices[0].message.content}
    except Exception as e: return jsonify({'error':'Erro na Nodo AI','detail':str(e)}),500
@socketio.on('join')
def on_join(data):
    room=(data or {}).get('room','global'); join_room(room); emit('system',{'message':f'Entrou na sala {room}'},to=request.sid)
@socketio.on('message')
def on_message(data):
    room=(data or {}).get('room','global'); content=((data or {}).get('content') or '').strip(); username=((data or {}).get('username') or 'Anônimo')[:120]; user_id=(data or {}).get('user_id')
    if not content: return
    msg=ChatMessage(room=room,content=content[:1000],username=username,user_id=user_id); db.session.add(msg); db.session.commit(); emit('message',{'id':msg.id,'room':room,'content':msg.content,'username':username,'user_id':user_id,'created_at':msg.created_at.isoformat()},to=room)
if __name__=='__main__':
    with app.app_context(): db.create_all()
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT',5000)), debug=True)
