import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  BadgeCheck, Bot, CheckCircle2, Code2, Coins, Crown, Gem, GraduationCap,
  Hash, Home, ImagePlus, LayoutDashboard, Lock, LogOut, Mail, MessageCircle,
  Mic, Palette, Paperclip, Plus, Rocket, Search, Send, Settings, Shield,
  Smile, Sparkles, Store, Trophy, User, UserPlus, Users, Zap
} from 'lucide-react';
import './style.css';
import nodoLogo from './assets/nodo-logo.jpg';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const navItems = [
  ['dashboard', 'Dashboard', LayoutDashboard],
  ['missions', 'Missões', Code2],
  ['courses', 'Cursos', GraduationCap],
  ['ranking', 'Ranking', Trophy],
  ['store', 'Loja', Store],
  ['community', 'Comunidade', MessageCircle],
  ['groups', 'Nodos', Hash],
  ['friends', 'Amigos', Users],
  ['chat', 'Chat', Send],
  ['profile', 'Perfil', User],
];

function token(){ return localStorage.getItem('token') || ''; }
function saveUser(u){ localStorage.setItem('user', JSON.stringify(u)); }
function clearSession(){ localStorage.removeItem('token'); localStorage.removeItem('user'); }
async function api(path, opts={}){
  const headers = {'Content-Type':'application/json', ...(opts.headers || {})};
  if(token()) headers.Authorization = 'Bearer ' + token();
  const res = await fetch(API_URL + path, {...opts, headers});
  let data = {};
  try { data = await res.json(); } catch { data = {}; }
  if(!res.ok) throw new Error(data.error || data.detail || 'Erro na requisição');
  return data;
}
function fmtTime(value){
  if(!value) return '';
  try { return new Date(value).toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'}); } catch { return ''; }
}
function roomForDm(a,b){ const x=Math.min(a,b), y=Math.max(a,b); return `dm:${x}:${y}`; }

function App(){
  const [user,setUser] = useState(()=>JSON.parse(localStorage.getItem('user') || 'null'));
  useEffect(()=>{
    if(token()) api('/api/me').then(d=>{saveUser(d.user); setUser(d.user)}).catch(()=>{clearSession(); setUser(null)});
  },[]);
  return user ? <Shell user={user} setUser={setUser}/> : <Auth onLogin={setUser}/>;
}

function Auth({onLogin}){
  const [mode,setMode] = useState('login');
  const [form,setForm] = useState({username:'', email:'', password:''});
  const [error,setError] = useState('');
  const [loading,setLoading] = useState(false);
  async function submit(e){
    e.preventDefault(); setError(''); setLoading(true);
    try{
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const data = await api(path, {method:'POST', body:JSON.stringify(form)});
      localStorage.setItem('token', data.token); saveUser(data.user); onLogin(data.user);
    }catch(err){ setError(err.message); }
    finally{ setLoading(false); }
  }
  return <main className="landing">
    <section className="landingCard brandHero">
      <div className="logoWrap heroLogo"><img src={nodoLogo} alt="Logo Nodo"/></div>
      <p className="pretitle"><Shield size={16}/> Nodo V3.2</p>
      <h1>Aprenda, poste, evolua e construa seu caminho como dev.</h1>
      <p className="heroText">Uma rede social de programação com missões, cursos, ranking, grupos e uma loja de cosméticos por Nodo Coins.</p>
      <div className="featureGrid">
        <span><Code2/> Missões reais</span><span><MessageCircle/> Comunidade dev</span>
        <span><Gem/> Cosméticos</span><span><Bot/> Nodo AI</span>
      </div>
    </section>
    <form className="landingCard authCard" onSubmit={submit}>
      <div className="authTop"><img src={nodoLogo} alt="Nodo"/><div><b>{mode==='login'?'Entrar':'Criar conta'}</b><small>Sem conta demo pública.</small></div></div>
      {mode==='register' && <label>Nome<input placeholder="Seu nome" value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label>}
      <label>Email<input placeholder="seu@email.com" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
      <label>Senha<input type="password" placeholder="mínimo 8 caracteres" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label>
      {error && <p className="error">{error}</p>}
      <button className="primaryBtn" disabled={loading}>{loading?'Carregando...':mode==='login'?'Entrar':'Criar conta'}</button>
      <button type="button" className="linkBtn" onClick={()=>{setMode(mode==='login'?'register':'login'); setError('')}}>
        {mode==='login'?'Não tenho conta, quero criar':'Já tenho conta, quero entrar'}
      </button>
    </form>
  </main>
}

function Shell({user,setUser}){
  const [page,setPage] = useState('dashboard');
  const visibleNav = useMemo(()=> user.is_admin ? [...navItems, ['admin','Admin',Crown]] : navItems, [user.is_admin]);
  function logout(){ clearSession(); location.reload(); }
  const Page = {dashboard:Dashboard, missions:Missions, courses:Courses, ranking:Ranking, store:StorePage, community:Community, groups:Groups, friends:Friends, chat:GlobalChat, profile:Profile, admin:Admin}[page] || Dashboard;
  return <div className="appShell">
    <aside className="sideBar">
      <div className="sideBrand"><img src={nodoLogo} alt="Nodo"/><div><b>Nodo</b><small>V3.2</small></div></div>
      <nav>{visibleNav.map(([id,label,Icon])=><button key={id} className={page===id?'active':''} onClick={()=>setPage(id)}><Icon size={19}/><span>{label}</span></button>)}</nav>
      <button className="logoutBtn" onClick={logout}><LogOut size={18}/> Sair</button>
    </aside>
    <section className="workspace">
      <Topbar user={user}/>
      <Page user={user} setUser={setUser}/>
    </section>
  </div>
}
function Topbar({user}){return <header className="topbar"><div><p className="pretitle">Bem-vindo de volta</p><h2>{user.username}</h2></div><div className="topStats"><Pill>{user.level || 1} nível</Pill><Pill>{user.xp || 0} XP</Pill><Pill>{user.nodo_coins || 0} NC</Pill><Avatar src={user.avatar}/></div></header>}
function Pill({children}){return <span className="pill">{children}</span>}
function Avatar({src, small=false}){return <span className={small?'avatar small':'avatar'}>{src && String(src).startsWith('data:') ? <img src={src} alt="avatar"/> : (src || 'ND')}</span>}
function Title({eyebrow='Nodo', title, sub}){return <div className="title"><p className="pretitle">{eyebrow}</p><h1>{title}</h1>{sub&&<p>{sub}</p>}</div>}
function Stat({icon,label,value}){return <article className="statCard">{icon}<small>{label}</small><b>{value}</b></article>}

function Dashboard({user,setUser}){
  const [dash,setDash] = useState(null), [msg,setMsg] = useState('');
  async function load(){ try{setDash(await api('/api/dashboard'))}catch(e){setMsg(e.message)} }
  useEffect(()=>{load()},[]);
  async function checkin(){ try{const d=await api('/api/streak/checkin',{method:'POST'}); saveUser(d.user); setUser(d.user); setMsg(d.message); load();}catch(e){setMsg(e.message)} }
  return <section><Title title="Dashboard" sub="Seu resumo de estudo, comunidade e evolução." />{msg&&<p className="notice">{msg}</p>}
    <div className="heroPanel"><div><p className="pretitle">Sua jornada</p><h1>Continue evoluindo sem inflar Nodo Coins.</h1><p>As moedas agora são mais raras e os cosméticos ficam mais valiosos.</p><button className="primaryBtn" onClick={checkin}><CheckCircle2/> Check-in diário</button></div><div className="levelBadge"><span>{user.level}</span><small>LEVEL</small></div></div>
    <div className="statsGrid"><Stat icon={<Code2/>} label="Missões concluídas" value={dash?.stats?.completed_missions ?? '-'}/><Stat icon={<Trophy/>} label="Posição no ranking" value={dash?.stats?.ranking_position ?? '-'}/><Stat icon={<MessageCircle/>} label="Posts" value={dash?.stats?.posts ?? '-'}/><Stat icon={<Hash/>} label="Nodos" value={dash?.stats?.groups ?? '-'}/></div>
  </section>
}
function Missions({setUser}){
  const [missions,setMissions] = useState([]), [answers,setAnswers] = useState({}), [msg,setMsg] = useState('');
  async function load(){ setMissions((await api('/api/missions')).missions); }
  useEffect(()=>{load()},[]);
  async function submit(id){ try{const d=await api(`/api/missions/${id}/submit`,{method:'POST', body:JSON.stringify({answer:answers[id]||''})}); if(d.user){saveUser(d.user); setUser(d.user)} setMsg(d.message); load();}catch(e){setMsg(e.message)} }
  return <section><Title title="Missões" sub="Recompensas menores em Nodo Coins para preservar valor futuro."/>{msg&&<p className="notice">{msg}</p>}<div className="cardGrid">{missions.map(m=><article className="missionCard" key={m.id}><div className="cardHead"><b>{m.title}</b><Pill>{m.difficulty}</Pill></div><p>{m.description}</p><small>{m.category} • +{m.xp_reward} XP • +{m.coin_reward} NC</small><textarea disabled={m.completed} placeholder="Escreva sua resposta..." value={answers[m.id]||''} onChange={e=>setAnswers({...answers,[m.id]:e.target.value})}/><button disabled={m.completed} onClick={()=>submit(m.id)}>{m.completed?'Concluída':'Enviar resposta'}</button></article>)}</div></section>
}
function Courses(){const [courses,setCourses]=useState([]); useEffect(()=>{api('/api/courses').then(d=>setCourses(d.courses))},[]); return <section><Title title="Cursos" sub="Trilhas para organizar o estudo."/><div className="cardGrid">{courses.map(c=><article className="softCard" key={c.id}><GraduationCap/><h3>{c.title}</h3><p>{c.description}</p><small>{c.category} • {c.level}</small></article>)}</div></section>}
function Ranking(){const [ranking,setRanking]=useState([]); useEffect(()=>{api('/api/ranking').then(d=>setRanking(d.ranking))},[]); return <section><Title title="Ranking" sub="XP, nível e evolução da comunidade."/><div className="tableCard">{ranking.map((u,i)=><div className="rankRow" key={u.id}><b>#{i+1}</b><Avatar src={u.avatar} small/><span>{u.username}</span><small>Level {u.level}</small><small>{u.xp} XP</small><small>{u.nodo_coins} NC</small></div>)}</div></section>}
function CosmeticIcon({slug}){return <div className={`cosIcon ${slug||'default'}`}><span></span><i></i></div>}
function StorePage({setUser}){const [items,setItems]=useState([]),[msg,setMsg]=useState(''); async function load(){setItems((await api('/api/store')).items)} useEffect(()=>{load()},[]); async function buy(id){try{const d=await api(`/api/store/${id}/purchase`,{method:'POST'}); saveUser(d.user); setUser(d.user); setMsg(d.message); load();}catch(e){setMsg(e.message)}} return <section><Title title="Loja" sub="Cosméticos visuais estilo premium, sem vantagem injusta."/>{msg&&<p className="notice">{msg}</p>}<div className="cardGrid shopGrid">{items.map(i=><article className="shopCard" key={i.id}><CosmeticIcon slug={i.icon}/><h3>{i.name}</h3><p>{i.description}</p><small>{i.item_type} • {i.price} NC</small><button disabled={i.owned} onClick={()=>buy(i.id)}>{i.owned?'Comprado':'Comprar'}</button></article>)}</div></section>}
function Community(){const [posts,setPosts]=useState([]), [text,setText]=useState(''), [msg,setMsg]=useState(''); async function load(){setPosts((await api('/api/posts')).posts)} useEffect(()=>{load()},[]); async function post(e){e.preventDefault(); if(!text.trim())return; try{await api('/api/posts',{method:'POST',body:JSON.stringify({content:text})}); setText(''); load();}catch(err){setMsg(err.message)}} return <section><Title title="Comunidade" sub="Feed dev para dúvidas, ideias e projetos."/>{msg&&<p className="error">{msg}</p>}<form className="composer" onSubmit={post}><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Publique uma ideia, dúvida ou projeto..."/><button><Send/> Publicar</button></form><div className="feed">{posts.map(p=><article className="postCard" key={p.id}><div className="postUser"><Avatar src={p.user.avatar} small/><b>{p.user.username}</b><small>{fmtTime(p.created_at)}</small></div><p>{p.content}</p></article>)}</div></section>}
function Groups(){const [groups,setGroups]=useState([]),[mine,setMine]=useState([]),[selected,setSelected]=useState(null),[form,setForm]=useState({name:'',description:'',topic:'Programação'}),[msg,setMsg]=useState(''); async function load(){const a=await api('/api/groups'); const b=await api('/api/my-groups'); setGroups(a.groups); setMine(b.groups)} useEffect(()=>{load()},[]); async function create(e){e.preventDefault(); try{const d=await api('/api/groups',{method:'POST',body:JSON.stringify(form)}); setMsg(d.message); setForm({name:'',description:'',topic:'Programação'}); load(); setSelected(d.group_id);}catch(err){setMsg(err.message)}} async function join(g){await api(`/api/groups/${g.id}/join`,{method:'POST'}); load(); setSelected(g.id)} const current = groups.find(g=>g.id===selected) || mine.find(g=>g.id===selected); return <section><Title title="Nodos" sub="Grupos de estudo e projetos com chat próprio."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><div><form className="panelForm" onSubmit={create}><h3><Plus/> Criar Nodo</h3><input placeholder="Nome do Nodo" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input placeholder="Tema" value={form.topic} onChange={e=>setForm({...form,topic:e.target.value})}/><textarea placeholder="Descrição" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><button>Criar</button></form><div className="cardGrid">{groups.map(g=><article className="softCard compact" key={g.id}><div className="cardHead"><b>{g.name}</b><Pill>{g.topic}</Pill></div><p>{g.description}</p><small>{g.members_count} membros</small><div className="row"><button onClick={()=>setSelected(g.id)}>Abrir</button>{!g.is_member&&<button className="ghostBtn" onClick={()=>join(g)}>Entrar</button>}</div></article>)}</div></div><aside className="chatSide">{current ? <ChatRoom room={`group:${current.id}`} title={current.name} sub="Chat do Nodo"/> : <div className="emptyState"><Hash/><b>Escolha um Nodo</b><p>Crie ou abra um grupo para conversar.</p></div>}</aside></div></section>}
function ChatRoom({room='global', title='Chat geral', sub='Conversa da comunidade'}){const [messages,setMessages]=useState([]),[text,setText]=useState(''),[error,setError]=useState(''); const bottom=useRef(null); async function load(){try{setMessages((await api(`/api/chat/history?room=${encodeURIComponent(room)}`)).messages)}catch(e){setError(e.message)}} useEffect(()=>{load(); const id=setInterval(load,3000); return()=>clearInterval(id)},[room]); useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth'})},[messages]); async function send(e){e.preventDefault(); if(!text.trim()) return; try{const d=await api('/api/chat/message',{method:'POST',body:JSON.stringify({room,content:text})}); setText(''); setMessages(m=>[...m,d.message]);}catch(err){setError(err.message)}} return <div className="chatPanel"><div className="chatHeader"><div><b>{title}</b><small>{sub}</small></div><Pill>{messages.length} msg</Pill></div>{error&&<p className="error">{error}</p>}<div className="messages">{messages.map(m=><div className="bubble" key={m.id}><b>{m.username}</b><p>{m.content}</p><small>{fmtTime(m.created_at)}</small></div>)}<div ref={bottom}/></div><form className="chatComposer" onSubmit={send}><button type="button" className="iconBtn"><Smile size={18}/></button><button type="button" className="iconBtn"><Paperclip size={18}/></button><input value={text} onChange={e=>setText(e.target.value)} placeholder="Mensagem..."/><button type="button" className="iconBtn"><Mic size={18}/></button><button className="sendBtn"><Send size={18}/></button></form></div>}
function GlobalChat(){return <section><Title title="Chat" sub="Chat geral com visual moderno e envio por backend REST."/><ChatRoom room="global" title="Chat geral" sub="Todos da Nodo"/></section>}
function Friends({user}){const [q,setQ]=useState(''),[results,setResults]=useState([]),[friends,setFriends]=useState([]),[dm,setDm]=useState(null),[msg,setMsg]=useState(''); async function loadFriends(){setFriends((await api('/api/friends')).friends)} useEffect(()=>{loadFriends()},[]); async function search(e){e.preventDefault(); setResults((await api('/api/users?q='+encodeURIComponent(q))).users)} async function add(id){try{const d=await api(`/api/friends/${id}`,{method:'POST'}); setMsg(d.message); loadFriends();}catch(e){setMsg(e.message)}} return <section><Title title="Amigos" sub="Procure devs e abra conversas privadas."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><div><form className="searchBar" onSubmit={search}><Search/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar usuário"/><button>Buscar</button></form><h3>Resultados</h3>{results.map(u=><div className="userLine" key={u.id}><Avatar src={u.avatar} small/><b>{u.username}</b><button onClick={()=>add(u.id)}><UserPlus size={16}/> adicionar</button></div>)}<h3>Amigos</h3>{friends.map(f=><div className="userLine" key={f.id}><Avatar src={f.avatar} small/><b>{f.username}</b><button onClick={()=>setDm(f)}>Conversar</button></div>)}</div><aside className="chatSide">{dm ? <ChatRoom room={roomForDm(user.id,dm.id)} title={dm.username} sub="Mensagem privada"/> : <div className="emptyState"><Users/><b>Escolha um amigo</b><p>Converse em privado.</p></div>}</aside></div></section>}
function Profile({user,setUser}){const [form,setForm]=useState({username:user.username,email:user.email,phone:user.phone||'',bio:user.bio||'',avatar:user.avatar||'ND'}),[pass,setPass]=useState({current_password:'',new_password:''}),[msg,setMsg]=useState(''); function fileToAvatar(file){if(!file)return;if(file.size>180000){alert('Imagem muito pesada.');return}const r=new FileReader();r.onload=()=>setForm({...form,avatar:r.result});r.readAsDataURL(file)} async function save(e){e.preventDefault();const d=await api('/api/me',{method:'PUT',body:JSON.stringify(form)}); saveUser(d.user); setUser(d.user); setMsg('Perfil salvo')} async function changePass(e){e.preventDefault(); await api('/api/me/password',{method:'PUT',body:JSON.stringify(pass)}); setPass({current_password:'',new_password:''}); setMsg('Senha alterada')} return <section><Title title="Perfil" sub="Personalização leve, sem pesar a plataforma."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><form className="panelForm" onSubmit={save}><Avatar src={form.avatar}/><label className="uploadBtn"><ImagePlus/> Escolher imagem<input type="file" accept="image/*" onChange={e=>fileToAvatar(e.target.files[0])}/></label><input value={form.username} onChange={e=>setForm({...form,username:e.target.value})} placeholder="Nome"/><input value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="Email"/><input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} placeholder="Telefone opcional"/><textarea value={form.bio} onChange={e=>setForm({...form,bio:e.target.value})} placeholder="Bio"/><button>Salvar perfil</button></form><form className="panelForm" onSubmit={changePass}><h3><Lock/> Segurança</h3><input type="password" value={pass.current_password} onChange={e=>setPass({...pass,current_password:e.target.value})} placeholder="Senha atual"/><input type="password" value={pass.new_password} onChange={e=>setPass({...pass,new_password:e.target.value})} placeholder="Nova senha"/><button>Alterar senha</button><p className="muted">2FA entra na próxima etapa.</p></form></div></section>}
function Admin(){const [sum,setSum]=useState(null),[mission,setMission]=useState({title:'',description:'',category:'Programação',difficulty:'iniciante',xp_reward:50,coin_reward:1}),[item,setItem]=useState({name:'',description:'',icon:'profile-pro',item_type:'cosmetico',price:50}),[msg,setMsg]=useState(''); async function load(){setSum(await api('/api/admin/summary'))} useEffect(()=>{load()},[]); async function createMission(e){e.preventDefault();try{const d=await api('/api/admin/missions',{method:'POST',body:JSON.stringify(mission)});setMsg(d.message);setMission({...mission,title:'',description:''});load()}catch(err){setMsg(err.message)}} async function createItem(e){e.preventDefault();try{const d=await api('/api/admin/store',{method:'POST',body:JSON.stringify(item)});setMsg(d.message);setItem({...item,name:'',description:''});load()}catch(err){setMsg(err.message)}} return <section><Title title="Admin" sub="Controle de missões e loja."/>{msg&&<p className="notice">{msg}</p>}<div className="statsGrid"><Stat icon={<Users/>} label="Usuários" value={sum?.users??'-'}/><Stat icon={<Code2/>} label="Missões" value={sum?.missions??'-'}/><Stat icon={<Hash/>} label="Nodos" value={sum?.groups??'-'}/><Stat icon={<Store/>} label="Loja" value={sum?.store_items??'-'}/></div><div className="split"><form className="panelForm" onSubmit={createMission}><h3>Nova missão</h3><input placeholder="Título" value={mission.title} onChange={e=>setMission({...mission,title:e.target.value})}/><textarea placeholder="Descrição" value={mission.description} onChange={e=>setMission({...mission,description:e.target.value})}/><input placeholder="Categoria" value={mission.category} onChange={e=>setMission({...mission,category:e.target.value})}/><input placeholder="Dificuldade" value={mission.difficulty} onChange={e=>setMission({...mission,difficulty:e.target.value})}/><input type="number" value={mission.xp_reward} onChange={e=>setMission({...mission,xp_reward:e.target.value})}/><input type="number" max="5" value={mission.coin_reward} onChange={e=>setMission({...mission,coin_reward:e.target.value})}/><button>Criar missão</button></form><form className="panelForm" onSubmit={createItem}><h3>Novo cosmético</h3><input placeholder="Nome" value={item.name} onChange={e=>setItem({...item,name:e.target.value})}/><textarea placeholder="Descrição" value={item.description} onChange={e=>setItem({...item,description:e.target.value})}/><select value={item.icon} onChange={e=>setItem({...item,icon:e.target.value})}><option value="carbon-frame">Moldura Carbon</option><option value="python-badge">Badge Python</option><option value="web-badge">Badge Web</option><option value="neon-banner">Banner Neon</option><option value="name-glow">Nome Glow</option><option value="profile-pro">Perfil Pro</option></select><input placeholder="Tipo" value={item.item_type} onChange={e=>setItem({...item,item_type:e.target.value})}/><input type="number" value={item.price} onChange={e=>setItem({...item,price:e.target.value})}/><button>Criar item</button></form></div></section>}

createRoot(document.getElementById('root')).render(<App/>);
