import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  BadgeCheck, Bot, CheckCircle2, Code2, Coins, Crown, Gem, GraduationCap,
  Hash, ImagePlus, LayoutDashboard, Lock, LogOut, MessageCircle, Mic,
  Palette, Paperclip, Plus, Search, Send, Shield, Smile, Sparkles, Store,
  Trash2, Trophy, User, UserPlus, Users, Wand2, Zap
} from 'lucide-react';
import './style.css';
import nodoLogo from './assets/nodo-logo.jpg';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const navItems = [
  ['dashboard', 'Início', LayoutDashboard],
  ['community', 'Comunidade', MessageCircle],
  ['chat', 'Chat', Send],
  ['groups', 'Nodos', Hash],
  ['missions', 'Missões', Code2],
  ['courses', 'Cursos', GraduationCap],
  ['ranking', 'Ranking', Trophy],
  ['store', 'Loja', Store],
  ['customize', 'Personalizar', Palette],
  ['friends', 'Amigos', Users],
  ['profile', 'Perfil', User],
];

const categories = [
  ['all', 'Todos'], ['frame', 'Moldura'], ['banner', 'Banner'], ['effect', 'Efeito'],
  ['badge', 'Selo'], ['nameplate', 'Nome'], ['theme', 'Tema']
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
function cos(user){ return user?.cosmetics || {}; }
function rarityLabel(r){ return r || 'comum'; }
function itemClass(item){ return `rarity-${String(item?.rarity || 'comum').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()}`; }

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
      <div className="logoWrap heroLogo"><img src={nodoLogo} alt="Nodo"/></div>
      <p className="pretitle"><Sparkles size={16}/> Nodo</p>
      <h1>Aprenda programação em comunidade.</h1>
      <p className="heroText">Missões, perfil, grupos, chat e personalização em uma só plataforma.</p>
      <div className="featureGrid">
        <span><Code2/> Missões</span><span><MessageCircle/> Comunidade</span>
        <span><Gem/> Loja</span><span><Bot/> IA</span>
      </div>
    </section>
    <form className="landingCard authCard" onSubmit={submit}>
      <div className="authTop"><img src={nodoLogo} alt="Nodo"/><div><b>{mode==='login'?'Entrar':'Criar conta'}</b><small>Nodo</small></div></div>
      {mode==='register' && <label>Nome<input placeholder="Seu nome" value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label>}
      <label>Email<input placeholder="seu@email.com" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label>
      <label>Senha<input type="password" placeholder="mínimo 8 caracteres" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label>
      {error && <p className="error">{error}</p>}
      <button className="primaryBtn" disabled={loading}>{loading?'Carregando...':mode==='login'?'Entrar':'Criar conta'}</button>
      <button type="button" className="linkBtn" onClick={()=>{setMode(mode==='login'?'register':'login'); setError('')}}>
        {mode==='login'?'Criar conta':'Entrar'}
      </button>
    </form>
  </main>;
}

function Shell({user,setUser}){
  const [page,setPage] = useState('dashboard');
  const visibleNav = useMemo(()=> user.is_admin ? [...navItems, ['admin','Admin',Crown]] : navItems, [user.is_admin]);
  function logout(){ clearSession(); location.reload(); }
  const Page = {dashboard:Dashboard, missions:Missions, courses:Courses, ranking:Ranking, store:StorePage, community:Community, groups:Groups, friends:Friends, chat:GlobalChat, profile:Profile, customize:Customize, admin:Admin}[page] || Dashboard;
  return <div className="appShell">
    <aside className="sideBar">
      <div className="sideBrand"><img src={nodoLogo} alt="Nodo"/><div><b>Nodo</b><small>Dev social</small></div></div>
      <nav>{visibleNav.map(([id,label,Icon])=><button key={id} className={page===id?'active':''} onClick={()=>setPage(id)}><Icon size={19}/><span>{label}</span></button>)}</nav>
      <button className="logoutBtn" onClick={logout}><LogOut size={18}/> Sair</button>
    </aside>
    <section className="workspace">
      <Topbar user={user}/>
      <Page user={user} setUser={setUser}/>
    </section>
  </div>;
}

function Topbar({user}){return <header className="topbar"><div><p className="pretitle">Nodo</p><h2>{user.username}</h2></div><div className="topStats"><Pill>{user.level || 1} nível</Pill><Pill>{user.xp || 0} XP</Pill><Pill>{user.nodo_coins || 0} NC</Pill><Avatar user={user}/></div></header>;}
function Pill({children}){return <span className="pill">{children}</span>;}
function Title({eyebrow='Nodo', title, sub}){return <div className="title"><p className="pretitle">{eyebrow}</p><h1>{title}</h1>{sub&&<p>{sub}</p>}</div>;}
function Stat({icon,label,value}){return <article className="statCard">{icon}<small>{label}</small><b>{value}</b></article>;}

function Avatar({user, src, small=false}){
  const c = cos(user);
  const value = src ?? user?.avatar ?? 'ND';
  const frame = c.frame || '';
  return <span className={`avatar ${small?'small':''} ${frame}`}>
    {String(value).startsWith('data:') ? <img src={value} alt="avatar"/> : <span>{String(value).slice(0,2)}</span>}
    {c.badge && <i className={`miniBadge ${c.badge}`}></i>}
  </span>;
}

function ProfilePreview({user, override={}}){
  const c = {...cos(user), ...override};
  const display = {...user, cosmetics:c};
  return <article className={`profilePreview ${c.theme || 'theme-obsidian'} ${c.banner || ''} ${c.effect || ''}`}>
    <div className="previewBanner"></div>
    <div className="previewBody">
      <Avatar user={display}/>
      <div>
        <div className={`nameplate ${c.nameplate || ''}`}>{user.username}</div>
        <p>{user.bio || 'Sem bio ainda.'}</p>
        <div className="row"><Pill>Level {user.level || 1}</Pill><Pill>{user.xp || 0} XP</Pill>{c.badge && <Pill>Selo</Pill>}</div>
      </div>
    </div>
  </article>;
}

function CosmeticIcon({slug}){return <div className={`cosIcon ${slug||'default'}`}><span></span><i></i></div>;}

function Dashboard({user,setUser}){
  const [dash,setDash] = useState(null), [msg,setMsg] = useState('');
  async function load(){ try{setDash(await api('/api/dashboard'));}catch(e){setMsg(e.message);} }
  useEffect(()=>{load();},[]);
  async function checkin(){ try{const d=await api('/api/streak/checkin',{method:'POST'}); saveUser(d.user); setUser(d.user); setMsg(d.message); load();}catch(e){setMsg(e.message);} }
  return <section><Title title="Início" sub="Seu progresso na Nodo." />{msg&&<p className="notice">{msg}</p>}
    <div className="dashHero"><div><p className="pretitle">Hoje</p><h1>Continue evoluindo.</h1><p>Faça missões, converse e personalize seu perfil.</p><button className="primaryBtn" onClick={checkin}><CheckCircle2/> Check-in</button></div><ProfilePreview user={user}/></div>
    <div className="statsGrid"><Stat icon={<Code2/>} label="Missões" value={`${dash?.stats?.completed_missions ?? '-'} / ${dash?.stats?.total_missions ?? '-'}`}/><Stat icon={<Trophy/>} label="Ranking" value={dash?.stats?.ranking_position ?? '-'}/><Stat icon={<MessageCircle/>} label="Posts" value={dash?.stats?.posts ?? '-'}/><Stat icon={<Hash/>} label="Nodos" value={dash?.stats?.groups ?? '-'}/></div>
  </section>;
}

function Missions({setUser}){
  const [missions,setMissions] = useState([]), [answers,setAnswers] = useState({}), [msg,setMsg] = useState('');
  async function load(){ setMissions((await api('/api/missions')).missions); }
  useEffect(()=>{load();},[]);
  async function submit(id){ try{const d=await api(`/api/missions/${id}/submit`,{method:'POST', body:JSON.stringify({answer:answers[id]||''})}); if(d.user){saveUser(d.user); setUser(d.user);} setMsg(d.message); load();}catch(e){setMsg(e.message);} }
  return <section><Title title="Missões" sub="Complete desafios." />{msg&&<p className="notice">{msg}</p>}<div className="cardGrid">{missions.map(m=><article className="missionCard" key={m.id}><div className="cardHead"><b>{m.title}</b><Pill>{m.difficulty}</Pill></div><p>{m.description}</p><small>{m.category} • +{m.xp_reward} XP • +{m.coin_reward} NC</small><textarea disabled={m.completed} placeholder="Sua resposta..." value={answers[m.id]||''} onChange={e=>setAnswers({...answers,[m.id]:e.target.value})}/><button disabled={m.completed} onClick={()=>submit(m.id)}>{m.completed?'Concluída':'Enviar'}</button></article>)}</div></section>;
}

function Courses(){const [courses,setCourses]=useState([]); useEffect(()=>{api('/api/courses').then(d=>setCourses(d.courses));},[]); return <section><Title title="Cursos" sub="Trilhas de estudo."/><div className="cardGrid">{courses.map(c=><article className="softCard" key={c.id}><GraduationCap/><h3>{c.title}</h3><p>{c.description}</p><small>{c.category} • {c.level}</small></article>)}</div></section>;}
function Ranking(){const [ranking,setRanking]=useState([]); useEffect(()=>{api('/api/ranking').then(d=>setRanking(d.ranking));},[]); return <section><Title title="Ranking" sub="Comunidade."/><div className="tableCard">{ranking.map((u,i)=><div className="rankRow" key={u.id}><b>#{i+1}</b><Avatar user={u} small/><span className={`nameplate mini ${cos(u).nameplate||''}`}>{u.username}</span><small>Level {u.level}</small><small>{u.xp} XP</small><small>{u.nodo_coins} NC</small></div>)}</div></section>;}

function StorePage({user,setUser}){
  const [items,setItems]=useState([]),[msg,setMsg]=useState(''),[filter,setFilter]=useState('all');
  async function load(){setItems((await api('/api/store')).items);}
  useEffect(()=>{load();},[]);
  async function buy(id){try{const d=await api(`/api/store/${id}/purchase`,{method:'POST'}); saveUser(d.user); setUser(d.user); setMsg(d.message); load();}catch(e){setMsg(e.message);}}
  const shown = filter==='all' ? items : items.filter(i=>i.item_type===filter);
  return <section><Title title="Loja" sub="Cosméticos."/>{msg&&<p className="notice">{msg}</p>}<div className="tabs">{categories.map(([id,label])=><button key={id} className={filter===id?'active':''} onClick={()=>setFilter(id)}>{label}</button>)}</div><div className="cardGrid shopGrid">{shown.map(i=><article className={`shopCard ${itemClass(i)}`} key={i.id}><CosmeticIcon slug={i.icon}/><div className="cardHead"><h3>{i.name}</h3><Pill>{rarityLabel(i.rarity)}</Pill></div><p>{i.description}</p><small>{i.item_type} • {i.price} NC</small><button disabled={i.owned || i.price===0} onClick={()=>buy(i.id)}>{i.owned?'Comprado':i.price===0?'Grátis':'Comprar'}</button></article>)}</div></section>;
}

function Customize({user,setUser}){
  const [items,setItems]=useState([]),[msg,setMsg]=useState(''),[filter,setFilter]=useState('frame'),[selected,setSelected]=useState(null);
  async function load(){const d=await api('/api/store'); setItems(d.items); if(!selected && d.items.length) setSelected(d.items.find(x=>x.item_type==='frame')||d.items[0]);}
  useEffect(()=>{load();},[]);
  const shown = items.filter(i=> filter==='all' ? true : i.item_type===filter);
  const override = selected ? {[selected.item_type]: selected.icon} : {};
  async function equip(item){
    try{const d=await api('/api/me/equip',{method:'POST',body:JSON.stringify({slot:item.item_type,item_id:item.id})}); saveUser(d.user); setUser(d.user); setMsg('Equipado'); load();}
    catch(e){setMsg(e.message);}
  }
  async function buy(item){
    try{const d=await api(`/api/store/${item.id}/purchase`,{method:'POST'}); saveUser(d.user); setUser(d.user); setMsg('Comprado'); await load();}
    catch(e){setMsg(e.message);}
  }
  return <section><Title title="Personalizar" sub="Perfil, banner e efeitos."/>{msg&&<p className="notice">{msg}</p>}<div className="customLayout"><div><div className="tabs">{categories.slice(1).map(([id,label])=><button key={id} className={filter===id?'active':''} onClick={()=>setFilter(id)}>{label}</button>)}</div><div className="customGrid">{shown.map(i=><button className={`customItem ${selected?.id===i.id?'active':''} ${itemClass(i)}`} key={i.id} onClick={()=>setSelected(i)}><CosmeticIcon slug={i.icon}/><b>{i.name}</b><small>{rarityLabel(i.rarity)} • {i.price} NC</small>{i.owned ? <span>Seu item</span> : i.price===0 ? <span>Grátis</span> : <span>Bloqueado</span>}</button>)}</div></div><aside className="previewSide"><ProfilePreview user={user} override={override}/>{selected&&<div className="actionBox"><h3>{selected.name}</h3><p>{selected.description}</p><div className="row"><Pill>{selected.item_type}</Pill><Pill>{rarityLabel(selected.rarity)}</Pill><Pill>{selected.price} NC</Pill></div>{(selected.owned || selected.price===0) ? <button className="primaryBtn" onClick={()=>equip(selected)}><Wand2/> Equipar</button> : <button className="primaryBtn" onClick={()=>buy(selected)}><Coins/> Comprar</button>}</div>}</aside></div></section>;
}

function Community(){const [posts,setPosts]=useState([]), [text,setText]=useState(''), [msg,setMsg]=useState(''); async function load(){setPosts((await api('/api/posts')).posts);} useEffect(()=>{load();},[]); async function post(e){e.preventDefault(); if(!text.trim())return; try{await api('/api/posts',{method:'POST',body:JSON.stringify({content:text})}); setText(''); load();}catch(err){setMsg(err.message);}} return <section><Title title="Comunidade" sub="Feed."/>{msg&&<p className="error">{msg}</p>}<form className="composer" onSubmit={post}><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Publique algo..."/><button><Send/> Publicar</button></form><div className="feed">{posts.map(p=><article className={`postCard ${cos(p.user).theme||''} ${cos(p.user).effect||''}`} key={p.id}><div className="postUser"><Avatar user={p.user} small/><b className={`nameplate mini ${cos(p.user).nameplate||''}`}>{p.user.username}</b><small>{fmtTime(p.created_at)}</small></div><p>{p.content}</p></article>)}</div></section>;}

function Groups(){const [groups,setGroups]=useState([]),[mine,setMine]=useState([]),[selected,setSelected]=useState(null),[form,setForm]=useState({name:'',description:'',topic:'Programação'}),[msg,setMsg]=useState(''); async function load(){const a=await api('/api/groups'); const b=await api('/api/my-groups'); setGroups(a.groups); setMine(b.groups);} useEffect(()=>{load();},[]); async function create(e){e.preventDefault(); try{const d=await api('/api/groups',{method:'POST',body:JSON.stringify(form)}); setMsg(d.message); setForm({name:'',description:'',topic:'Programação'}); load(); setSelected(d.group_id);}catch(err){setMsg(err.message);}} async function join(g){await api(`/api/groups/${g.id}/join`,{method:'POST'}); load(); setSelected(g.id);} const current = groups.find(g=>g.id===selected) || mine.find(g=>g.id===selected); return <section><Title title="Nodos" sub="Grupos."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><div><form className="panelForm" onSubmit={create}><h3><Plus/> Criar Nodo</h3><input placeholder="Nome" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input placeholder="Tema" value={form.topic} onChange={e=>setForm({...form,topic:e.target.value})}/><textarea placeholder="Descrição" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><button>Criar</button></form><div className="cardGrid">{groups.map(g=><article className="softCard compact" key={g.id}><div className="cardHead"><b>{g.name}</b><Pill>{g.topic}</Pill></div><p>{g.description}</p><small>{g.members_count} membros</small><div className="row"><button onClick={()=>setSelected(g.id)}>Abrir</button>{!g.is_member&&<button className="ghostBtn" onClick={()=>join(g)}>Entrar</button>}</div></article>)}</div></div><aside className="chatSide">{current ? <ChatRoom room={`group:${current.id}`} title={current.name} sub="Chat"/> : <div className="emptyState"><Hash/><b>Escolha um Nodo</b><p>Crie ou abra um grupo.</p></div>}</aside></div></section>;}

function ChatRoom({room='global', title='Chat', sub='Comunidade'}){const [messages,setMessages]=useState([]),[text,setText]=useState(''),[error,setError]=useState(''); const bottom=useRef(null); async function load(){try{setMessages((await api(`/api/chat/history?room=${encodeURIComponent(room)}`)).messages);}catch(e){setError(e.message);}} useEffect(()=>{load(); const id=setInterval(load,3000); return()=>clearInterval(id);},[room]); useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth'});},[messages]); async function send(e){e.preventDefault(); if(!text.trim()) return; try{const d=await api('/api/chat/message',{method:'POST',body:JSON.stringify({room,content:text})}); setText(''); setMessages(m=>[...m,d.message]);}catch(err){setError(err.message);}} return <div className="chatPanel"><div className="chatHeader"><div><b>{title}</b><small>{sub}</small></div><Pill>{messages.length}</Pill></div>{error&&<p className="error">{error}</p>}<div className="messages">{messages.map(m=><div className="bubble" key={m.id}><b>{m.username}</b><p>{m.content}</p><small>{fmtTime(m.created_at)}</small></div>)}<div ref={bottom}/></div><form className="chatComposer" onSubmit={send}><button type="button" className="iconBtn"><Smile size={18}/></button><button type="button" className="iconBtn"><Paperclip size={18}/></button><input value={text} onChange={e=>setText(e.target.value)} placeholder="Mensagem..."/><button type="button" className="iconBtn"><Mic size={18}/></button><button className="sendBtn"><Send size={18}/></button></form></div>;}
function GlobalChat(){return <section><Title title="Chat" sub="Geral."/><ChatRoom room="global" title="Chat geral" sub="Todos"/></section>;}

function Friends({user}){const [q,setQ]=useState(''),[results,setResults]=useState([]),[friends,setFriends]=useState([]),[dm,setDm]=useState(null),[msg,setMsg]=useState(''); async function loadFriends(){setFriends((await api('/api/friends')).friends);} useEffect(()=>{loadFriends();},[]); async function search(e){e.preventDefault(); setResults((await api('/api/users?q='+encodeURIComponent(q))).users);} async function add(id){try{const d=await api(`/api/friends/${id}`,{method:'POST'}); setMsg(d.message); loadFriends();}catch(e){setMsg(e.message);}} return <section><Title title="Amigos" sub="DM."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><div><form className="searchBar" onSubmit={search}><Search/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar usuário"/><button>Buscar</button></form><h3>Resultados</h3>{results.map(u=><div className="userLine" key={u.id}><Avatar user={u} small/><b>{u.username}</b><button onClick={()=>add(u.id)}><UserPlus size={16}/> adicionar</button></div>)}<h3>Amigos</h3>{friends.map(f=><div className="userLine" key={f.id}><Avatar user={f} small/><b>{f.username}</b><button onClick={()=>setDm(f)}>Conversar</button></div>)}</div><aside className="chatSide">{dm ? <ChatRoom room={roomForDm(user.id,dm.id)} title={dm.username} sub="DM"/> : <div className="emptyState"><Users/><b>Escolha um amigo</b><p>Converse em privado.</p></div>}</aside></div></section>;}

function Profile({user,setUser}){const [form,setForm]=useState({username:user.username,email:user.email,phone:user.phone||'',bio:user.bio||'',avatar:user.avatar||'ND'}),[pass,setPass]=useState({current_password:'',new_password:''}),[msg,setMsg]=useState(''); function fileToAvatar(file){if(!file)return;if(file.size>180000){alert('Imagem muito pesada.');return;}const r=new FileReader();r.onload=()=>setForm({...form,avatar:r.result});r.readAsDataURL(file);} async function save(e){e.preventDefault();const d=await api('/api/me',{method:'PUT',body:JSON.stringify(form)}); saveUser(d.user); setUser(d.user); setMsg('Perfil salvo');} async function changePass(e){e.preventDefault(); await api('/api/me/password',{method:'PUT',body:JSON.stringify(pass)}); setPass({current_password:'',new_password:''}); setMsg('Senha alterada');} return <section><Title title="Perfil" sub="Conta."/>{msg&&<p className="notice">{msg}</p>}<div className="split"><div><ProfilePreview user={{...user,...form}}/><form className="panelForm" onSubmit={save}><Avatar user={user} src={form.avatar}/><label className="uploadBtn"><ImagePlus/> Escolher imagem<input type="file" accept="image/*" onChange={e=>fileToAvatar(e.target.files[0])}/></label><input value={form.username} onChange={e=>setForm({...form,username:e.target.value})} placeholder="Nome"/><input value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="Email"/><input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} placeholder="Telefone"/><textarea value={form.bio} onChange={e=>setForm({...form,bio:e.target.value})} placeholder="Bio"/><button>Salvar</button></form></div><form className="panelForm" onSubmit={changePass}><h3><Lock/> Segurança</h3><input type="password" value={pass.current_password} onChange={e=>setPass({...pass,current_password:e.target.value})} placeholder="Senha atual"/><input type="password" value={pass.new_password} onChange={e=>setPass({...pass,new_password:e.target.value})} placeholder="Nova senha"/><button>Alterar senha</button></form></div></section>;}

function Admin({setUser}){
  const [data,setData]=useState(null),[tab,setTab]=useState('users'),[msg,setMsg]=useState('');
  const [mission,setMission]=useState({title:'',description:'',category:'Programação',difficulty:'iniciante',xp_reward:30,coin_reward:1});
  const [item,setItem]=useState({name:'',description:'',icon:'badge-founder',item_type:'badge',rarity:'comum',price:25});
  async function load(){setData(await api('/api/admin/overview'));}
  useEffect(()=>{load();},[]);
  async function createMission(e){e.preventDefault();try{const d=await api('/api/admin/missions',{method:'POST',body:JSON.stringify(mission)});setMsg(d.message);setMission({...mission,title:'',description:''});load();}catch(err){setMsg(err.message);}}
  async function createItem(e){e.preventDefault();try{const d=await api('/api/admin/store',{method:'POST',body:JSON.stringify(item)});setMsg(d.message);setItem({...item,name:'',description:''});load();}catch(err){setMsg(err.message);}}
  async function del(path){if(!confirm('Apagar?'))return; try{const d=await api(path,{method:'DELETE'});setMsg(d.message);load();}catch(e){setMsg(e.message);}}
  async function patchUser(u,patch){try{const d=await api(`/api/admin/users/${u.id}`,{method:'PATCH',body:JSON.stringify(patch)}); if(d.user?.id===JSON.parse(localStorage.getItem('user')||'{}').id){saveUser(d.user); setUser(d.user);} setMsg(d.message);load();}catch(e){setMsg(e.message);}}
  const sum=data?.summary||{};
  return <section><Title title="Admin" sub="Controle."/>{msg&&<p className="notice">{msg}</p>}<div className="statsGrid"><Stat icon={<Users/>} label="Usuários" value={sum.users??'-'}/><Stat icon={<MessageCircle/>} label="Posts" value={sum.posts??'-'}/><Stat icon={<Hash/>} label="Nodos" value={sum.groups??'-'}/><Stat icon={<Store/>} label="Loja" value={sum.store_items??'-'}/></div><div className="tabs adminTabs">{['users','posts','groups','missions','store'].map(x=><button key={x} className={tab===x?'active':''} onClick={()=>setTab(x)}>{x==='users'?'Usuários':x==='posts'?'Posts':x==='groups'?'Nodos':x==='missions'?'Missões':'Loja'}</button>)}</div>
    {tab==='users'&&<div className="tableCard">{data?.users?.map(u=><div className="adminRow" key={u.id}><Avatar user={u} small/><b>{u.username}</b><small>{u.email}</small><small>{u.nodo_coins} NC</small><small>{u.xp} XP</small><button onClick={()=>patchUser(u,{nodo_coins:(u.nodo_coins||0)+10})}>+10 NC</button><button onClick={()=>patchUser(u,{xp:(u.xp||0)+50})}>+50 XP</button><button onClick={()=>patchUser(u,{is_admin:!u.is_admin})}>{u.is_admin?'Remover ADM':'Dar ADM'}</button></div>)}</div>}
    {tab==='posts'&&<div className="tableCard">{data?.posts?.map(p=><div className="adminRow" key={p.id}><b>{p.user.username}</b><span>{p.content}</span><button className="danger" onClick={()=>del(`/api/admin/posts/${p.id}`)}><Trash2 size={16}/> Apagar</button></div>)}</div>}
    {tab==='groups'&&<div className="tableCard">{data?.groups?.map(g=><div className="adminRow" key={g.id}><b>{g.name}</b><small>{g.topic}</small><small>{g.members_count} membros</small><button className="danger" onClick={()=>del(`/api/admin/groups/${g.id}`)}><Trash2 size={16}/> Apagar</button></div>)}</div>}
    {tab==='missions'&&<div className="split"><form className="panelForm" onSubmit={createMission}><h3>Nova missão</h3><input placeholder="Título" value={mission.title} onChange={e=>setMission({...mission,title:e.target.value})}/><textarea placeholder="Descrição" value={mission.description} onChange={e=>setMission({...mission,description:e.target.value})}/><input placeholder="Categoria" value={mission.category} onChange={e=>setMission({...mission,category:e.target.value})}/><input placeholder="Dificuldade" value={mission.difficulty} onChange={e=>setMission({...mission,difficulty:e.target.value})}/><input type="number" value={mission.xp_reward} onChange={e=>setMission({...mission,xp_reward:e.target.value})}/><input type="number" max="3" value={mission.coin_reward} onChange={e=>setMission({...mission,coin_reward:e.target.value})}/><button>Criar</button></form><div className="tableCard">{data?.missions?.map(m=><div className="adminRow" key={m.id}><b>{m.title}</b><small>{m.category}</small><small>+{m.coin_reward} NC</small><button className="danger" onClick={()=>del(`/api/admin/missions/${m.id}`)}>Apagar</button></div>)}</div></div>}
    {tab==='store'&&<div className="split"><form className="panelForm" onSubmit={createItem}><h3>Novo item</h3><input placeholder="Nome" value={item.name} onChange={e=>setItem({...item,name:e.target.value})}/><textarea placeholder="Descrição" value={item.description} onChange={e=>setItem({...item,description:e.target.value})}/><select value={item.item_type} onChange={e=>setItem({...item,item_type:e.target.value})}>{categories.slice(1).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select><input placeholder="Classe visual" value={item.icon} onChange={e=>setItem({...item,icon:e.target.value})}/><select value={item.rarity} onChange={e=>setItem({...item,rarity:e.target.value})}><option>comum</option><option>raro</option><option>épico</option><option>lendário</option></select><input type="number" value={item.price} onChange={e=>setItem({...item,price:e.target.value})}/><button>Criar</button></form><div className="tableCard">{data?.store_items?.map(i=><div className="adminRow" key={i.id}><CosmeticIcon slug={i.icon}/><b>{i.name}</b><small>{i.item_type}</small><small>{i.price} NC</small><button className="danger" onClick={()=>del(`/api/admin/store/${i.id}`)}>Apagar</button></div>)}</div></div>}
  </section>;
}

createRoot(document.getElementById('root')).render(<App/>);
