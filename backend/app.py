@app.get('/api/chat/history')
@require_auth
def chat_history():
    room = request.args.get('room', 'global')
    ms = ChatMessage.query.filter_by(room=room).order_by(ChatMessage.created_at.desc()).limit(80).all()
    ms.reverse()

    return {
        'messages': [
            {
                'id': m.id,
                'room': m.room,
                'content': m.content,
                'username': m.username,
                'user_id': m.user_id,
                'created_at': m.created_at.isoformat()
            }
            for m in ms
        ]
    }


@app.post("/api/chat/send")
@require_auth
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
