import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { io } from 'socket.io-client';
import {
  Bell,
  Bot,
  Check,
  Code2,
  Coins,
  Crown,
  Flame,
  Flag,
  Gem,
  GraduationCap,
  Hash,
  Heart,
  Home,
  ImagePlus,
  Download,
  LogOut,
  Menu,
  MessageCircle,
  Palette,
  Plus,
  Search,
  Send,
  Settings,
  Shield,
  ShoppingBag,
  Smile,
  Sparkles,
  Store,
  Trash2,
  Trophy,
  User,
  UserMinus,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { api, clearSession, getStoredUser, getToken, saveSession, SOCKET_URL } from './api';
import {
  Avatar,
  Badge,
  CosmeticIcon,
  dateMini,
  Empty,
  Loading,
  ProfileCard,
  roomForDm,
  safeRarity,
  time,
  Title,
  Toast,
} from './ui';
import nodoLogo from './assets/nodo-logo.jpg';

const APP_NAME = 'Nodo';
const NAV_ITEMS = [
  ['dashboard', 'Início', Home],
  ['community', 'Comunidade', MessageCircle],
  ['chat', 'Chat', Send],
  ['groups', 'Nodos', Hash],
  ['friends', 'Amigos', Users],
  ['missions', 'Missões', Code2],
  ['achievements', 'Conquistas', Trophy],
  ['store', 'Loja', Store],
  ['customize', 'Personalizar', Palette],
  ['ranking', 'Ranking', Crown],
  ['courses', 'Cursos', GraduationCap],
  ['ai', 'Nodo AI', Bot],
  ['profile', 'Perfil', User],
  ['notifications', 'Notificações', Bell],
];
const COSMETIC_CATEGORIES = [
  ['all', 'Todos'],
  ['frame', 'Moldura'],
  ['banner', 'Banner'],
  ['effect', 'Efeito'],
  ['badge', 'Selo'],
  ['nameplate', 'Nome'],
  ['theme', 'Tema'],
];

function updateLocalUser(user, setUser) {
  saveSession('', user);
  setUser(user);
}

export default function App() {
  const [user, setUser] = useState(getStoredUser);
  const [checking, setChecking] = useState(Boolean(getToken()));

  useEffect(() => {
    const expire = () => {
      clearSession();
      setUser(null);
      setChecking(false);
    };
    window.addEventListener('nodo:session-expired', expire);
    return () => window.removeEventListener('nodo:session-expired', expire);
  }, []);

  useEffect(() => {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    api('/api/me')
      .then(({ user: freshUser }) => {
        saveSession('', freshUser);
        setUser(freshUser);
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setChecking(false));
  }, []);

  if (checking) return <div className="appBoot"><img src={nodoLogo} alt="Nodo" /><Loading label="Abrindo a Nodo" /></div>;
  return user ? <Shell user={user} setUser={setUser} /> : <Auth onLogin={setUser} />;
}

function Auth({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setMessage('');
    setLoading(true);
    try {
      const data = await api(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify(form) });
      saveSession(data.token, data.user);
      onLogin(data.user);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginScreen">
      <section className="loginBrand">
        <div className="brandMark"><img src={nodoLogo} alt="Nodo" /></div>
        <p>Nodo</p>
        <h1>Aprenda. Compartilhe. Evolua.</h1>
        <div className="loginChips"><span>Comunidade</span><span>Missões</span><span>Nodos</span><span>Perfil</span></div>
      </section>
      <form className="loginPanel" onSubmit={submit}>
        <div className="loginTop"><img src={nodoLogo} alt="Nodo" /><div><b>{mode === 'login' ? 'Bem-vindo de volta' : 'Crie sua conta'}</b><small>{APP_NAME}</small></div></div>
        {mode === 'register' ? <label>Nome<input autoComplete="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="PedroDev" /></label> : null}
        <label>Email<input type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="seu@email.com" /></label>
        <label>Senha<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="mínimo 10 caracteres" /></label>
        <Toast message={message} type="error" onClose={() => setMessage('')} />
        <button className="primary wide" disabled={loading}>{loading ? 'Carregando...' : mode === 'login' ? 'Entrar' : 'Criar conta'}</button>
        <button className="ghost wide" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage(''); }}>
          {mode === 'login' ? 'Criar conta' : 'Já tenho conta'}
        </button>
      </form>
    </main>
  );
}

function Shell({ user, setUser }) {
  const [page, setPage] = useState('dashboard');
  const [notifications, setNotifications] = useState({ unread: 0, notifications: [] });
  const [mobileMenu, setMobileMenu] = useState(false);
  const [deferredInstall, setDeferredInstall] = useState(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const nav = useMemo(() => user.is_admin ? [...NAV_ITEMS, ['admin', 'Admin', Shield]] : NAV_ITEMS, [user.is_admin]);

  const refreshNotifications = useCallback(() => {
    api('/api/notifications').then(setNotifications).catch(() => {});
  }, []);

  useEffect(() => {
    refreshNotifications();
    const timer = setInterval(refreshNotifications, 30000);
    return () => clearInterval(timer);
  }, [refreshNotifications]);

  useEffect(() => {
    const capture = (event) => {
      event.preventDefault();
      setDeferredInstall(event);
    };
    window.addEventListener('beforeinstallprompt', capture);
    return () => window.removeEventListener('beforeinstallprompt', capture);
  }, []);

  function navigate(next) {
    setPage(next);
    setMobileMenu(false);
  }

  function logout() {
    clearSession();
    location.reload();
  }

  async function installApp() {
    if (!deferredInstall) return;
    deferredInstall.prompt();
    await deferredInstall.userChoice;
    setDeferredInstall(null);
  }

  const currentProps = { user, setUser, setPage: navigate, refreshNotifications };
  const Current = {
    dashboard: Dashboard,
    community: Community,
    chat: GlobalChat,
    groups: Groups,
    friends: Friends,
    missions: Missions,
    achievements: Achievements,
    store: StorePage,
    customize: Customize,
    ranking: Ranking,
    courses: Courses,
    ai: NodoAI,
    profile: Profile,
    notifications: NotificationsPage,
    admin: Admin,
  }[page] || Dashboard;

  return (
    <div className="discordShell">
      <aside className="serverRail">
        <button className="serverIcon active" onClick={() => navigate('dashboard')} aria-label="Início"><img src={nodoLogo} alt="Nodo" /></button>
        <span className="railDivider" />
        <button className="serverIcon" onClick={() => navigate('groups')} aria-label="Nodos"><Hash size={22} /></button>
        <button className="serverIcon" onClick={() => navigate('chat')} aria-label="Chat"><MessageCircle size={22} /></button>
        <button className="serverIcon add" onClick={() => navigate('customize')} aria-label="Personalizar"><Sparkles size={21} /></button>
      </aside>

      <aside className={`channelPanel ${mobileMenu ? 'open' : ''}`}>
        <div className="guildHead"><div><b>Nodo</b><small>Comunidade dev</small></div><button className="mobileClose" onClick={() => setMobileMenu(false)}><X size={18} /></button></div>
        <nav className="channelGroup">
          <p>Navegação</p>
          {nav.map(([id, label, Icon]) => (
            <button key={id} onClick={() => navigate(id)} className={page === id ? 'active' : ''}>
              <Icon size={18} /><span>{label}</span>{id === 'notifications' && notifications.unread > 0 ? <i>{notifications.unread}</i> : null}
            </button>
          ))}
        </nav>
        <div className="miniProfile">
          <Avatar user={user} small />
          <div><b>{user.username}</b><small>Nível {user.level || 1} · {user.nodo_coins || 0} NC</small></div>
          <button onClick={logout} aria-label="Sair"><LogOut size={17} /></button>
        </div>
      </aside>

      {mobileMenu ? <button className="menuBackdrop" onClick={() => setMobileMenu(false)} aria-label="Fechar menu" /> : null}

      <main className="mainPanel">
        <Topbar
          user={user}
          unread={notifications.unread}
          setPage={navigate}
          openMenu={() => setMobileMenu(true)}
          openSearch={() => setSearchOpen(true)}
          canInstall={Boolean(deferredInstall)}
          installApp={installApp}
        />
        <Current {...currentProps} />
      </main>
      <RightBar user={user} />
      <MobileDock page={page} setPage={navigate} unread={notifications.unread} />
      {searchOpen ? <SearchModal onClose={() => setSearchOpen(false)} setPage={navigate} /> : null}
    </div>
  );
}

function Topbar({ user, unread, setPage, openMenu, openSearch, canInstall, installApp }) {
  return (
    <header className="topbar">
      <button className="mobileMenuButton" onClick={openMenu}><Menu size={20} /></button>
      <button className="globalSearch" onClick={openSearch}><Search size={17} /><span>Pesquisar na Nodo</span><kbd>Ctrl K</kbd></button>
      <div className="topActions">
        {canInstall ? <button className="iconButton installButton" onClick={installApp} title="Instalar Nodo"><Download size={18} /></button> : null}
        <Badge>{user.nodo_coins || 0} NC</Badge>
        <button className="iconButton notificationButton" onClick={() => setPage('notifications')} aria-label="Notificações"><Bell size={18} />{unread > 0 ? <i>{unread}</i> : null}</button>
        <button className="avatarButton" onClick={() => setPage('profile')}><Avatar user={user} small /></button>
      </div>
    </header>
  );
}

function MobileDock({ page, setPage, unread }) {
  const rows = [['dashboard', Home], ['community', MessageCircle], ['chat', Send], ['friends', Users], ['profile', User]];
  return <nav className="mobileDock">{rows.map(([id, Icon]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => setPage(id)}><Icon size={20} />{id === 'profile' && unread > 0 ? <i>{unread}</i> : null}</button>)}</nav>;
}

function RightBar({ user }) {
  const [activityRows, setActivityRows] = useState([]);
  useEffect(() => { api('/api/activity').then((data) => setActivityRows(data.activity || [])).catch(() => {}); }, []);
  return (
    <aside className="memberPanel">
      <h3>Seu perfil</h3>
      <ProfileCard user={user} compact />
      <h3>Atividade</h3>
      <div className="activityList">
        {activityRows.slice(0, 12).map((row) => <div className="activity" key={row.id}><span /><p>{row.text}</p><small>{dateMini(row.created_at)}</small></div>)}
        {!activityRows.length ? <p className="muted">Sem atividade ainda.</p> : null}
      </div>
    </aside>
  );
}

function SearchModal({ onClose, setPage }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ users: [], groups: [], posts: [] });
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  useEffect(() => inputRef.current?.focus(), []);
  useEffect(() => {
    if (query.trim().length < 2) { setResults({ users: [], groups: [], posts: [] }); return; }
    const timer = setTimeout(() => {
      setLoading(true);
      api(`/api/search?q=${encodeURIComponent(query)}`).then(setResults).catch(() => {}).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  function go(page) { setPage(page); onClose(); }
  return (
    <div className="modalBackdrop" onMouseDown={onClose}>
      <section className="searchModal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="searchModalInput"><Search size={20} /><input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Usuários, Nodos ou posts" /><button onClick={onClose}><X size={18} /></button></div>
        {loading ? <Loading /> : null}
        <div className="searchResults">
          {results.users.length ? <div><h4>Usuários</h4>{results.users.map((row) => <button key={row.id} onClick={() => go('friends')}><Avatar user={row} small /><span>{row.username}</span></button>)}</div> : null}
          {results.groups.length ? <div><h4>Nodos</h4>{results.groups.map((row) => <button key={row.id} onClick={() => go('groups')}><Hash size={18} /><span>{row.name}</span></button>)}</div> : null}
          {results.posts.length ? <div><h4>Posts</h4>{results.posts.map((row) => <button key={row.id} onClick={() => go('community')}><MessageCircle size={18} /><span>{row.content.slice(0, 90)}</span></button>)}</div> : null}
          {query.length >= 2 && !loading && !results.users.length && !results.groups.length && !results.posts.length ? <Empty>Nenhum resultado.</Empty> : null}
        </div>
      </section>
    </div>
  );
}

function Stat({ icon, label, value }) {
  return <article className="statCard"><span>{icon}</span><div><small>{label}</small><b>{value}</b></div></article>;
}

function Dashboard({ user, setUser, setPage }) {
  const [dashboardData, setDashboardData] = useState(null);
  const [message, setMessage] = useState('');
  const load = useCallback(() => api('/api/dashboard').then(setDashboardData), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function checkin() {
    try {
      const data = await api('/api/streak/checkin', { method: 'POST' });
      updateLocalUser(data.user, setUser);
      setMessage(data.message);
      load();
    } catch (error) { setMessage(error.message); }
  }
  return (
    <section className="pageSection">
      <Title title="Início" subtitle="Sua jornada" icon={<Home />} />
      <Toast message={message} onClose={() => setMessage('')} />
      <div className="dashboardHero">
        <div className="heroCopy"><span className="eyebrow">Nodo</span><h2>Evolua todos os dias.</h2><p>Aprenda, compartilhe e construa junto.</p><div className="row"><button className="primary" onClick={checkin}><Flame size={18} /> Check-in</button><button className="secondary" onClick={() => setPage('missions')}>Ver missões</button></div></div>
        <ProfileCard user={user} />
      </div>
      <div className="statsGrid">
        <Stat icon={<Code2 />} label="Missões" value={`${dashboardData?.stats?.completed_missions ?? '-'} / ${dashboardData?.stats?.total_missions ?? '-'}`} />
        <Stat icon={<Trophy />} label="Ranking" value={dashboardData?.stats?.ranking_position ? `#${dashboardData.stats.ranking_position}` : '-'} />
        <Stat icon={<MessageCircle />} label="Posts" value={dashboardData?.stats?.posts ?? '-'} />
        <Stat icon={<Gem />} label="Conquistas" value={dashboardData?.stats?.achievements ?? '-'} />
      </div>
      <NotificationPreview setPage={setPage} />
    </section>
  );
}

function Community() {
  const [posts, setPosts] = useState([]);
  const [text, setText] = useState('');
  const [comments, setComments] = useState({});
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => api('/api/posts').then((data) => setPosts(data.posts || [])).finally(() => setLoading(false)), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function publish() {
    if (!text.trim()) return;
    try { await api('/api/posts', { method: 'POST', body: JSON.stringify({ content: text }) }); setText(''); await load(); }
    catch (error) { setMessage(error.message); }
  }
  async function like(id) { try { const data = await api(`/api/posts/${id}/like`, { method: 'POST' }); setPosts((rows) => rows.map((row) => row.id === id ? data.post : row)); } catch (error) { setMessage(error.message); } }
  async function comment(id) { const content = comments[id] || ''; if (!content.trim()) return; try { const data = await api(`/api/posts/${id}/comments`, { method: 'POST', body: JSON.stringify({ content }) }); setComments({ ...comments, [id]: '' }); setPosts((rows) => rows.map((row) => row.id === id ? data.post : row)); } catch (error) { setMessage(error.message); } }
  async function report(post) { const reason = window.prompt('Motivo da denúncia:') || ''; if (!reason.trim()) return; try { const data = await api('/api/reports', { method: 'POST', body: JSON.stringify({ target_type: 'post', target_id: post.id, reason }) }); setMessage(data.message); } catch (error) { setMessage(error.message); } }
  return (
    <section className="pageSection contentNarrow">
      <Title title="Comunidade" subtitle="Feed" icon={<MessageCircle />} />
      <Toast message={message} onClose={() => setMessage('')} />
      <div className="composer"><textarea value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} placeholder="Compartilhe algo com a comunidade..." /><div><small>{text.length}/1000</small><button className="primary" onClick={publish} disabled={!text.trim()}><Send size={17} /> Publicar</button></div></div>
      {loading ? <Loading /> : null}
      <div className="feed">
        {posts.map((post) => <article className="postCard" key={post.id}>
          <div className="postHeader"><Avatar user={post.user} small /><div><b>{post.user.username}</b><small>{dateMini(post.created_at)} · {time(post.created_at)}</small></div><button className="iconButton" onClick={() => report(post)} title="Denunciar"><Flag size={15} /></button></div>
          <p className="postText">{post.content}</p>
          <div className="postActions"><button className={post.liked ? 'liked' : ''} onClick={() => like(post.id)}><Heart size={17} /> {post.likes_count}</button><span><MessageCircle size={17} /> {post.comments_count}</span></div>
          <div className="comments">{(post.comments || []).map((item) => <div key={item.id}><b>{item.user.username}</b><span>{item.content}</span></div>)}<div className="commentBox"><input value={comments[post.id] || ''} onChange={(e) => setComments({ ...comments, [post.id]: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') comment(post.id); }} placeholder="Escreva um comentário" /><button onClick={() => comment(post.id)}><Send size={15} /></button></div></div>
        </article>)}
        {!loading && !posts.length ? <Empty>Seja a primeira pessoa a publicar.</Empty> : null}
      </div>
    </section>
  );
}

function ChatBox({ room = 'global', title = 'Chat', subtitle = 'Sala' }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [message, setMessage] = useState('');
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const listRef = useRef(null);
  const socketRef = useRef(null);

  const addMessage = useCallback((incoming) => {
    if (incoming.room !== room) return;
    setMessages((rows) => rows.some((row) => row.id === incoming.id) ? rows : [...rows, incoming].slice(-100));
  }, [room]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api(`/api/chat/history?room=${encodeURIComponent(room)}`)
      .then((data) => { if (mounted) setMessages(data.messages || []); })
      .catch((error) => { if (mounted) setMessage(error.message); })
      .finally(() => { if (mounted) setLoading(false); });

    const socket = io(SOCKET_URL, { transports: ['websocket', 'polling'], reconnection: true, timeout: 10000 });
    socketRef.current = socket;
    socket.on('connect', () => { setConnected(true); socket.emit('join', { token: getToken(), room }); });
    socket.on('disconnect', () => setConnected(false));
    socket.on('message', addMessage);
    socket.on('system', (data) => { if (data?.error) setMessage(data.error); });

    return () => {
      mounted = false;
      socket.emit('leave', { token: getToken(), room });
      socket.off('message', addMessage);
      socket.disconnect();
      socketRef.current = null;
    };
  }, [room, addMessage]);

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }); }, [messages]);

  async function send() {
    const content = text.trim();
    if (!content) return;
    setText('');
    if (socketRef.current?.connected) {
      socketRef.current.emit('message', { token: getToken(), room, content });
      return;
    }
    try { const data = await api('/api/chat/message', { method: 'POST', body: JSON.stringify({ room, content }) }); addMessage(data.message); }
    catch (error) { setText(content); setMessage(error.message); }
  }

  return (
    <div className="chatBox">
      <div className="chatHead"><Hash size={18} /><div><b>{title}</b><small>{subtitle}</small></div><span className={connected ? 'onlineDot' : 'offlineDot'}>{connected ? 'online' : 'reconectando'}</span></div>
      <Toast message={message} type="error" onClose={() => setMessage('')} />
      <div className="messages" ref={listRef}>
        {loading ? <Loading label="Carregando mensagens" /> : null}
        {messages.map((item) => <div className="chatMessage" key={item.id}><Avatar user={item.user || { username: item.username, avatar: item.username }} small /><div><div className="messageMeta"><b>{item.username}</b><small>{dateMini(item.created_at)} {time(item.created_at)}</small></div><p>{item.content}</p></div></div>)}
        {!loading && !messages.length ? <Empty>Nenhuma mensagem ainda.</Empty> : null}
      </div>
      <div className="chatInput"><button className="iconButton" type="button"><Plus size={18} /></button><input value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder={`Conversar em ${title}`} /><button className="iconButton" type="button"><Smile size={18} /></button><button className="sendButton" onClick={send} disabled={!text.trim()}><Send size={18} /></button></div>
    </div>
  );
}

function GlobalChat() {
  return <section className="pageSection chatPage"><Title title="Chat" subtitle="Geral" icon={<Send />} /><ChatBox room="global" title="geral" subtitle="Comunidade" /></section>;
}

function Groups() {
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ name: '', description: '', topic: '' });
  const [active, setActive] = useState(null);
  const [message, setMessage] = useState('');
  const load = useCallback(() => api('/api/groups').then((data) => setGroups(data.groups || [])), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function create() { try { await api('/api/groups', { method: 'POST', body: JSON.stringify(form) }); setForm({ name: '', description: '', topic: '' }); await load(); setMessage('Nodo criado'); } catch (error) { setMessage(error.message); } }
  async function join(group) { try { await api(`/api/groups/${group.id}/join`, { method: 'POST' }); await load(); setActive({ ...group, is_member: true }); } catch (error) { setMessage(error.message); } }
  return (
    <section className="pageSection">
      <Title title="Nodos" subtitle="Grupos" icon={<Hash />} />
      <Toast message={message} onClose={() => setMessage('')} />
      <div className="splitLayout">
        <div>
          <div className="createGroupPanel"><input placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /><input placeholder="Tema" value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} /><input className="grow" placeholder="Descrição" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /><button className="primary" onClick={create}><Plus size={17} /> Criar</button></div>
          <div className="cardGrid">{groups.map((group) => <article className="contentCard" key={group.id}><div className="cardIcon"><Hash /></div><div><h3>{group.name}</h3><small>{group.topic} · nível {group.level}</small></div><p>{group.description || 'Sem descrição.'}</p><div className="row"><Badge>{group.members_count} membros</Badge>{group.is_member ? <button className="secondary" onClick={() => setActive(group)}>Abrir chat</button> : <button className="primary" onClick={() => join(group)}>Entrar</button>}</div></article>)}</div>
        </div>
        <aside>{active?.is_member ? <ChatBox room={`group:${active.id}`} title={active.name} subtitle="Nodo" /> : <Empty>Escolha um Nodo do qual você participa.</Empty>}</aside>
      </div>
    </section>
  );
}

function Friends({ user }) {
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState([]);
  const [data, setData] = useState({ friends: [], pending: [] });
  const [dm, setDm] = useState(null);
  const [message, setMessage] = useState('');
  const load = useCallback(() => api('/api/friends').then(setData), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function search() { if (query.trim().length < 2) return; try { const result = await api(`/api/users?q=${encodeURIComponent(query)}`); setUsers(result.users || []); } catch (error) { setMessage(error.message); } }
  async function add(id) { try { const result = await api(`/api/friends/${id}`, { method: 'POST' }); setMessage(result.message); await load(); } catch (error) { setMessage(error.message); } }
  async function accept(id) { try { await api(`/api/friends/${id}/accept`, { method: 'POST' }); await load(); } catch (error) { setMessage(error.message); } }
  async function reject(id) { try { await api(`/api/friends/${id}/reject`, { method: 'POST' }); await load(); } catch (error) { setMessage(error.message); } }
  async function remove(id) { if (!window.confirm('Remover amizade?')) return; try { await api(`/api/friends/user/${id}`, { method: 'DELETE' }); if (dm?.id === id) setDm(null); await load(); } catch (error) { setMessage(error.message); } }
  return (
    <section className="pageSection">
      <Title title="Amigos" subtitle="Pedidos e DM" icon={<Users />} />
      <Toast message={message} onClose={() => setMessage('')} />
      <div className="splitLayout">
        <div>
          <div className="searchBar"><Search size={18} /><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') search(); }} placeholder="Buscar usuário" /><button onClick={search}>Buscar</button></div>
          {data.pending?.length ? <div className="panel"><h3>Pedidos</h3>{data.pending.map((requestRow) => <div className="userRow" key={requestRow.id}><Avatar user={requestRow.user} small /><b>{requestRow.user.username}</b><div className="row"><button className="primary" onClick={() => accept(requestRow.id)}><Check size={16} /> Aceitar</button><button className="secondary" onClick={() => reject(requestRow.id)}><X size={16} /></button></div></div>)}</div> : null}
          <div className="panel"><h3>Amigos</h3>{data.friends?.map((friend) => <div className="userRow" key={friend.id}><Avatar user={friend} small /><div><b>{friend.username}</b><small>Nível {friend.level}</small></div><div className="row"><button className="primary" onClick={() => setDm(friend)}><MessageCircle size={16} /> DM</button><button className="secondary" onClick={() => remove(friend.id)} title="Remover"><UserMinus size={16} /></button></div></div>)}{!data.friends?.length ? <p className="muted">Nenhum amigo ainda.</p> : null}</div>
          {users.length ? <div className="panel"><h3>Resultados</h3>{users.map((found) => <div className="userRow" key={found.id}><Avatar user={found} small /><b>{found.username}</b><button className="secondary" onClick={() => add(found.id)}><UserPlus size={16} /> Adicionar</button></div>)}</div> : null}
        </div>
        <aside>{dm ? <ChatBox room={roomForDm(user.id, dm.id)} title={dm.username} subtitle="Mensagem direta" /> : <Empty>Abra uma conversa.</Empty>}</aside>
      </div>
    </section>
  );
}

function Missions({ setUser }) {
  const [rows, setRows] = useState([]);
  const [answers, setAnswers] = useState({});
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(null);
  const load = useCallback(() => api('/api/missions').then((data) => setRows(data.missions || [])), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function submit(id) { setBusy(id); try { const data = await api(`/api/missions/${id}/submit`, { method: 'POST', body: JSON.stringify({ answer: answers[id] || '' }) }); updateLocalUser(data.user, setUser); setMessage(data.message); await load(); } catch (error) { setMessage(error.message); } finally { setBusy(null); } }
  return <section className="pageSection"><Title title="Missões" subtitle="Desafios" icon={<Code2 />} /><Toast message={message} onClose={() => setMessage('')} /><div className="cardGrid">{rows.map((mission) => <article className={`contentCard missionCard ${mission.completed ? 'completed' : ''}`} key={mission.id}><div className="cardIcon"><Code2 /></div><div><h3>{mission.title}</h3><small>{mission.category} · {mission.difficulty}</small></div><p>{mission.description}</p><Badge>+{mission.xp_reward} XP · +{mission.coin_reward} NC</Badge><textarea disabled={mission.completed} value={answers[mission.id] || ''} onChange={(e) => setAnswers({ ...answers, [mission.id]: e.target.value })} placeholder="Sua resposta" /><button className={mission.completed ? 'secondary' : 'primary'} disabled={mission.completed || busy === mission.id} onClick={() => submit(mission.id)}>{mission.completed ? 'Concluída' : busy === mission.id ? 'Enviando...' : 'Enviar'}</button></article>)}</div></section>;
}

function Courses() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api('/api/courses').then((data) => setRows(data.courses || [])).catch(() => {}); }, []);
  return <section className="pageSection"><Title title="Cursos" subtitle="Trilhas" icon={<GraduationCap />} /><div className="cardGrid">{rows.map((course) => <article className="contentCard" key={course.id}><div className="cardIcon"><GraduationCap /></div><h3>{course.title}</h3><p>{course.description}</p><Badge>{course.category} · {course.level}</Badge></article>)}</div></section>;
}

function Ranking() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api('/api/ranking').then((data) => setRows(data.ranking || [])).catch(() => {}); }, []);
  return <section className="pageSection"><Title title="Ranking" subtitle="Top devs" icon={<Trophy />} /><div className="panel rankingTable">{rows.map((row, index) => <div className={`rankingRow top-${index + 1}`} key={row.id}><b>#{index + 1}</b><Avatar user={row} small /><span>{row.username}</span><Badge>Nível {row.level}</Badge><Badge>{row.xp} XP</Badge><Badge>{row.nodo_coins} NC</Badge></div>)}</div></section>;
}

function Achievements() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api('/api/achievements').then((data) => setRows(data.achievements || [])).catch(() => {}); }, []);
  return <section className="pageSection"><Title title="Conquistas" subtitle="Troféus" icon={<Trophy />} /><div className="cardGrid">{rows.map((achievement) => <article className={`contentCard achievementCard ${achievement.unlocked ? 'unlocked' : 'locked'}`} key={achievement.id}><div className="cardIcon"><Trophy /></div><h3>{achievement.title}</h3><p>{achievement.description}</p><Badge>{achievement.unlocked ? 'Desbloqueada' : 'Bloqueada'}</Badge></article>)}</div></section>;
}

function Tabs({ rows, value, onChange }) {
  return <div className="tabs">{rows.map(([id, label]) => <button key={id} onClick={() => onChange(id)} className={value === id ? 'active' : ''}>{label}</button>)}</div>;
}

function StorePage({ setUser }) {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState('all');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(null);
  const load = useCallback(() => api('/api/store').then((data) => setItems(data.items || [])), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function buy(id) { setBusy(id); try { const data = await api(`/api/store/${id}/purchase`, { method: 'POST' }); updateLocalUser(data.user, setUser); setMessage(data.message); await load(); } catch (error) { setMessage(error.message); } finally { setBusy(null); } }
  const visible = items.filter((item) => category === 'all' || item.item_type === category);
  return <section className="pageSection"><Title title="Loja" subtitle="Cosméticos" icon={<ShoppingBag />} /><Toast message={message} onClose={() => setMessage('')} /><Tabs rows={COSMETIC_CATEGORIES} value={category} onChange={setCategory} /><div className="shopGrid">{visible.map((item) => <article className={`shopItem rarity-${safeRarity(item.rarity)}`} key={item.id}><CosmeticIcon slug={item.icon} /><div className="shopInfo"><h3>{item.name}</h3><p>{item.description}</p><div className="row"><Badge>{item.rarity}</Badge><Badge>{item.price} NC</Badge></div></div><button disabled={item.owned || busy === item.id} onClick={() => buy(item.id)}>{item.owned ? 'Comprado' : busy === item.id ? 'Comprando...' : 'Comprar'}</button></article>)}</div></section>;
}

function Customize({ user, setUser }) {
  const [items, setItems] = useState([]);
  const [category, setCategory] = useState('frame');
  const [preview, setPreview] = useState({});
  const [message, setMessage] = useState('');
  useEffect(() => { api('/api/store').then((data) => setItems(data.items || [])).catch((error) => setMessage(error.message)); }, []);
  async function equip(item) { if (!item.owned && item.price !== 0) { setMessage('Compre esse item na loja'); return; } try { const data = await api('/api/me/equip', { method: 'POST', body: JSON.stringify({ slot: item.item_type, item_id: item.id }) }); updateLocalUser(data.user, setUser); setMessage('Equipado'); } catch (error) { setMessage(error.message); } }
  const visible = items.filter((item) => item.item_type === category);
  return <section className="pageSection"><Title title="Personalizar" subtitle="Seu visual" icon={<Palette />} /><Toast message={message} onClose={() => setMessage('')} /><div className="customLayout"><div><Tabs rows={COSMETIC_CATEGORIES.filter(([id]) => id !== 'all')} value={category} onChange={setCategory} /><div className="customGrid">{visible.map((item) => <button className={`customItem ${item.owned || item.price === 0 ? 'owned' : 'locked'}`} key={item.id} onMouseEnter={() => setPreview({ [item.item_type]: item.icon })} onFocus={() => setPreview({ [item.item_type]: item.icon })} onClick={() => equip(item)}><CosmeticIcon slug={item.icon} /><b>{item.name}</b><span>{item.owned || item.price === 0 ? 'Equipar' : `${item.price} NC`}</span></button>)}</div></div><aside className="stickyPreview"><ProfileCard user={user} override={preview} /><div className="panel"><h3>Prévia</h3><button className="secondary" onClick={() => setPreview({})}>Limpar</button></div></aside></div></section>;
}

function Profile({ user, setUser }) {
  const [profile, setProfile] = useState({ username: user.username, phone: user.phone || '', bio: user.bio || '', avatar: user.avatar || '' });
  const [emailForm, setEmailForm] = useState({ email: user.email, current_password: '' });
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '' });
  const [message, setMessage] = useState('');
  async function saveProfile() { try { const data = await api('/api/me', { method: 'PUT', body: JSON.stringify(profile) }); updateLocalUser(data.user, setUser); setMessage('Perfil salvo'); } catch (error) { setMessage(error.message); } }
  async function saveEmail() { try { const data = await api('/api/me/email', { method: 'PUT', body: JSON.stringify(emailForm) }); saveSession(data.token, data.user); setUser(data.user); setMessage('Email alterado'); setEmailForm({ email: data.user.email, current_password: '' }); } catch (error) { setMessage(error.message); } }
  async function savePassword() { try { const data = await api('/api/me/password', { method: 'PUT', body: JSON.stringify(passwordForm) }); saveSession(data.token, null); setPasswordForm({ current_password: '', new_password: '' }); setMessage('Senha alterada'); } catch (error) { setMessage(error.message); } }
  async function logoutAll() { if (!window.confirm('Encerrar todas as sessões?')) return; try { await api('/api/me/logout-all', { method: 'POST' }); clearSession(); location.reload(); } catch (error) { setMessage(error.message); } }
  function upload(event) { const file = event.target.files?.[0]; if (!file) return; if (file.size > 250000) { setMessage('Use uma imagem menor que 250 KB'); return; } const reader = new FileReader(); reader.onload = () => setProfile({ ...profile, avatar: reader.result }); reader.readAsDataURL(file); }
  return <section className="pageSection"><Title title="Perfil" subtitle="Conta" icon={<User />} /><Toast message={message} onClose={() => setMessage('')} /><div className="settingsLayout"><nav className="settingsNav"><a href="#profile">Perfil</a><a href="#email">Email</a><a href="#password">Senha</a><a href="#sessions">Sessões</a></nav><div className="settingsContent"><div id="profile" className="panel formPanel"><h3>Perfil</h3><label>Nome<input value={profile.username} onChange={(e) => setProfile({ ...profile, username: e.target.value })} /></label><label>Telefone<input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} /></label><label>Bio<textarea value={profile.bio} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} /></label><label className="upload"><ImagePlus size={18} /> Escolher avatar<input type="file" accept="image/png,image/jpeg,image/webp" onChange={upload} /></label><button className="primary" onClick={saveProfile}>Salvar</button></div><div id="email" className="panel formPanel"><h3>Email</h3><label>Novo email<input type="email" disabled={user.is_admin} value={emailForm.email} onChange={(e) => setEmailForm({ ...emailForm, email: e.target.value })} /></label><label>Senha atual<input type="password" disabled={user.is_admin} value={emailForm.current_password} onChange={(e) => setEmailForm({ ...emailForm, current_password: e.target.value })} /></label>{user.is_admin ? <p className="muted">O email do ADM é protegido.</p> : <button className="primary" onClick={saveEmail}>Alterar email</button>}</div><div id="password" className="panel formPanel"><h3>Senha</h3><label>Senha atual<input type="password" value={passwordForm.current_password} onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })} /></label><label>Nova senha<input type="password" value={passwordForm.new_password} onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })} /></label><button className="primary" onClick={savePassword}>Alterar senha</button></div><div id="sessions" className="panel formPanel"><h3>Sessões</h3><p className="muted">Encerra a sessão em todos os dispositivos.</p><button className="dangerButton" onClick={logoutAll}>Encerrar todas</button></div></div><aside><ProfileCard user={{ ...user, ...profile }} /></aside></div></section>;
}

function NotificationPreview({ setPage }) {
  const [data, setData] = useState({ notifications: [] });
  useEffect(() => { api('/api/notifications').then(setData).catch(() => {}); }, []);
  return <div className="panel"><div className="panelHeader"><h3>Notificações</h3><button className="textButton" onClick={() => setPage('notifications')}>Ver todas</button></div>{data.notifications?.slice(0, 4).map((row) => <div className="notificationRow" key={row.id}><Bell size={17} /><div><b>{row.title}</b><p>{row.body}</p></div><small>{dateMini(row.created_at)}</small></div>)}{!data.notifications?.length ? <p className="muted">Nada novo.</p> : null}</div>;
}

function NotificationsPage({ setPage, refreshNotifications }) {
  const [data, setData] = useState({ notifications: [] });
  const [loading, setLoading] = useState(true);
  useEffect(() => { Promise.all([api('/api/notifications'), api('/api/notifications/read', { method: 'POST' })]).then(([rows]) => setData(rows)).finally(() => { setLoading(false); refreshNotifications(); }); }, [refreshNotifications]);
  return <section className="pageSection contentNarrow"><Title title="Notificações" subtitle="Novidades" icon={<Bell />} />{loading ? <Loading /> : <div className="panel">{data.notifications?.map((row) => <button className={`notificationRow full ${row.is_read ? '' : 'unread'}`} key={row.id} onClick={() => row.action && setPage(row.action)}><Bell size={18} /><div><b>{row.title}</b><p>{row.body}</p></div><small>{dateMini(row.created_at)}</small></button>)}{!data.notifications?.length ? <Empty>Nenhuma notificação.</Empty> : null}</div>}</section>;
}

function NodoAI() {
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Como posso ajudar no seu projeto?' }]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  async function send() { const content = text.trim(); if (!content || loading) return; setMessages((rows) => [...rows, { role: 'user', content }]); setText(''); setLoading(true); try { const data = await api('/api/ai', { method: 'POST', body: JSON.stringify({ message: content }) }); setMessages((rows) => [...rows, { role: 'assistant', content: data.reply }]); } catch (error) { setMessages((rows) => [...rows, { role: 'assistant', content: error.message }]); } finally { setLoading(false); } }
  return <section className="pageSection aiPage"><Title title="Nodo AI" subtitle="Assistente" icon={<Bot />} /><div className="aiChat">{messages.map((row, index) => <div className={`aiMessage ${row.role}`} key={`${row.role}-${index}`}><span>{row.role === 'assistant' ? <Bot size={18} /> : <User size={18} />}</span><p>{row.content}</p></div>)}{loading ? <Loading label="Pensando" /> : null}</div><div className="aiInput"><textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="Pergunte sobre programação..." /><button className="primary" onClick={send}><Send size={18} /></button></div></section>;
}

function Admin() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('users');
  const [message, setMessage] = useState('');
  const [missionForm, setMissionForm] = useState({ title: '', description: '', category: 'Programação', difficulty: 'iniciante', xp_reward: 30, coin_reward: 1 });
  const [itemForm, setItemForm] = useState({ name: '', description: '', item_type: 'badge', icon: '', rarity: 'comum', price: 25 });
  const load = useCallback(() => api('/api/admin/overview').then(setData), []);
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [load]);
  async function patchUser(id, body) { try { await api(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }); await load(); } catch (error) { setMessage(error.message); } }
  async function remove(path) { if (!window.confirm('Confirmar exclusão?')) return; try { await api(path, { method: 'DELETE' }); await load(); } catch (error) { setMessage(error.message); } }
  async function createMission() { try { await api('/api/admin/missions', { method: 'POST', body: JSON.stringify(missionForm) }); setMissionForm({ title: '', description: '', category: 'Programação', difficulty: 'iniciante', xp_reward: 30, coin_reward: 1 }); await load(); setMessage('Missão criada'); } catch (error) { setMessage(error.message); } }
  async function createItem() { try { await api('/api/admin/store', { method: 'POST', body: JSON.stringify(itemForm) }); setItemForm({ name: '', description: '', item_type: 'badge', icon: '', rarity: 'comum', price: 25 }); await load(); setMessage('Item criado'); } catch (error) { setMessage(error.message); } }
  async function updateReport(id, status) { try { await api(`/api/admin/reports/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }); await load(); } catch (error) { setMessage(error.message); } }
  if (!data) return <section className="pageSection"><Title title="Admin" subtitle="Controle" icon={<Shield />} /><Loading /></section>;
  const tabs = [['users', 'Usuários'], ['posts', 'Posts'], ['groups', 'Nodos'], ['reports', 'Denúncias'], ['missions', 'Missões'], ['store', 'Loja'], ['audit', 'Logs']];
  return <section className="pageSection"><Title title="Admin" subtitle="Controle" icon={<Shield />} /><Toast message={message} onClose={() => setMessage('')} /><div className="statsGrid"><Stat icon={<Users />} label="Usuários" value={data.summary.users} /><Stat icon={<MessageCircle />} label="Posts" value={data.summary.posts} /><Stat icon={<Hash />} label="Nodos" value={data.summary.groups} /><Stat icon={<Flag />} label="Denúncias" value={data.summary.reports} /></div><Tabs rows={tabs} value={tab} onChange={setTab} />
    {tab === 'users' ? <div className="panel adminTable"><h3>Usuários</h3>{data.users.map((row) => <AdminUserRow key={row.id} user={row} patchUser={patchUser} />)}</div> : null}
    {tab === 'posts' ? <div className="panel adminTable"><h3>Posts</h3>{data.posts.map((row) => <div className="adminRow" key={row.id}><Avatar user={row.user} small /><b>{row.user.username}</b><span>{row.content}</span><button className="dangerIcon" onClick={() => remove(`/api/admin/posts/${row.id}`)}><Trash2 size={16} /></button></div>)}</div> : null}
    {tab === 'groups' ? <div className="panel adminTable"><h3>Nodos</h3>{data.groups.map((row) => <div className="adminRow" key={row.id}><Hash size={18} /><b>{row.name}</b><span>{row.members_count} membros</span><button className="dangerIcon" onClick={() => remove(`/api/admin/groups/${row.id}`)}><Trash2 size={16} /></button></div>)}</div> : null}
    {tab === 'reports' ? <div className="panel adminTable"><h3>Denúncias</h3>{data.reports.map((row) => <div className="adminRow reportRow" key={row.id}><Flag size={18} /><b>{row.target_type} #{row.target_id}</b><span>{row.reason || 'Sem motivo'}</span><select value={row.status} onChange={(e) => updateReport(row.id, e.target.value)}><option value="open">Aberta</option><option value="reviewing">Analisando</option><option value="closed">Fechada</option><option value="dismissed">Ignorada</option></select></div>)}</div> : null}
    {tab === 'missions' ? <div className="adminSplit"><div className="panel formPanel"><h3>Nova missão</h3><input placeholder="Título" value={missionForm.title} onChange={(e) => setMissionForm({ ...missionForm, title: e.target.value })} /><textarea placeholder="Descrição" value={missionForm.description} onChange={(e) => setMissionForm({ ...missionForm, description: e.target.value })} /><div className="formGrid"><input placeholder="Categoria" value={missionForm.category} onChange={(e) => setMissionForm({ ...missionForm, category: e.target.value })} /><select value={missionForm.difficulty} onChange={(e) => setMissionForm({ ...missionForm, difficulty: e.target.value })}><option>iniciante</option><option>intermediário</option><option>avançado</option></select><input type="number" value={missionForm.xp_reward} onChange={(e) => setMissionForm({ ...missionForm, xp_reward: Number(e.target.value) })} /><input type="number" value={missionForm.coin_reward} onChange={(e) => setMissionForm({ ...missionForm, coin_reward: Number(e.target.value) })} /></div><button className="primary" onClick={createMission}>Criar</button></div><div className="panel adminTable"><h3>Missões</h3>{data.missions.map((row) => <div className="adminRow" key={row.id}><Code2 size={18} /><b>{row.title}</b><span>{row.xp_reward} XP · {row.coin_reward} NC</span><button className="dangerIcon" onClick={() => remove(`/api/admin/missions/${row.id}`)}><Trash2 size={16} /></button></div>)}</div></div> : null}
    {tab === 'store' ? <div className="adminSplit"><div className="panel formPanel"><h3>Novo item</h3><input placeholder="Nome" value={itemForm.name} onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })} /><input placeholder="Identificador: badge-exemplo" value={itemForm.icon} onChange={(e) => setItemForm({ ...itemForm, icon: e.target.value })} /><textarea placeholder="Descrição" value={itemForm.description} onChange={(e) => setItemForm({ ...itemForm, description: e.target.value })} /><div className="formGrid"><select value={itemForm.item_type} onChange={(e) => setItemForm({ ...itemForm, item_type: e.target.value })}><option value="frame">Moldura</option><option value="banner">Banner</option><option value="effect">Efeito</option><option value="badge">Selo</option><option value="nameplate">Nome</option><option value="theme">Tema</option></select><select value={itemForm.rarity} onChange={(e) => setItemForm({ ...itemForm, rarity: e.target.value })}><option>comum</option><option>raro</option><option>épico</option><option>lendário</option></select><input type="number" value={itemForm.price} onChange={(e) => setItemForm({ ...itemForm, price: Number(e.target.value) })} /></div><button className="primary" onClick={createItem}>Criar</button></div><div className="panel adminTable"><h3>Itens</h3>{data.store_items.map((row) => <div className="adminRow" key={row.id}><CosmeticIcon slug={row.icon} /><b>{row.name}</b><span>{row.price} NC</span><button className="dangerIcon" onClick={() => remove(`/api/admin/store/${row.id}`)}><Trash2 size={16} /></button></div>)}</div></div> : null}
    {tab === 'audit' ? <div className="panel adminTable"><h3>Logs</h3>{data.audit.map((row) => <div className="auditRow" key={row.id}><Shield size={16} /><div><b>{row.admin} · {row.action}</b><p>{row.target_type} {row.target_id || ''} {row.details}</p></div><small>{dateMini(row.created_at)} {time(row.created_at)}</small></div>)}</div> : null}
  </section>;
}

function AdminUserRow({ user, patchUser }) {
  const [coins, setCoins] = useState(user.nodo_coins || 0);
  const [xp, setXp] = useState(user.xp || 0);
  useEffect(() => { setCoins(user.nodo_coins || 0); setXp(user.xp || 0); }, [user]);
  return <div className="adminUserRow"><Avatar user={user} small /><div><b>{user.username}</b><small>{user.email}</small></div><label>NC<input type="number" value={coins} onChange={(e) => setCoins(Number(e.target.value))} onBlur={() => patchUser(user.id, { nodo_coins: coins })} /></label><label>XP<input type="number" value={xp} onChange={(e) => setXp(Number(e.target.value))} onBlur={() => patchUser(user.id, { xp })} /></label><button className={user.is_admin ? 'primary' : 'secondary'} onClick={() => patchUser(user.id, { is_admin: !user.is_admin })}>{user.is_admin ? 'ADM' : 'Dar ADM'}</button><button className={user.is_banned ? 'dangerButton' : 'secondary'} onClick={() => patchUser(user.id, { is_banned: !user.is_banned })}>{user.is_banned ? 'Desbanir' : 'Banir'}</button></div>;
}
