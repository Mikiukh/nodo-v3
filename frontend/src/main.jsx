import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {
  Bell, Bot, CheckCircle2, Code2, Coins, Crown, Flame, Gem, GraduationCap,
  Hash, Heart, Home, ImagePlus, Lock, LogOut, MessageCircle, MoreHorizontal,
  Palette, Plus, Search, Send, Settings, Shield, ShoppingBag, Smile, Sparkles,
  Store, Trash2, Trophy, User, UserPlus, Users, Wand2, Zap, Flag
} from 'lucide-react';
import './style.css';
import nodoLogo from './assets/nodo-logo.jpg';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const APP = 'Nodo';

const pages = [
  ['dashboard','Início',Home], ['community','Comunidade',MessageCircle], ['chat','Chat',Send],
  ['groups','Nodos',Hash], ['friends','Amigos',Users], ['missions','Missões',Code2],
  ['achievements','Conquistas',Trophy], ['store','Loja',Store], ['customize','Personalizar',Palette],
  ['ranking','Ranking',Crown], ['courses','Cursos',GraduationCap], ['profile','Perfil',User]
];
const categories = [['all','Todos'],['frame','Moldura'],['banner','Banner'],['effect','Efeito'],['badge','Selo'],['nameplate','Nome'],['theme','Tema']];

function token(){return localStorage.getItem('token')||''}
function saveUser(u){localStorage.setItem('user',JSON.stringify(u))}
function clearSession(){localStorage.removeItem('token');localStorage.removeItem('user')}
async function api(path, opts={}){
  const headers={'Content-Type':'application/json',...(opts.headers||{})};
  if(token()) headers.Authorization='Bearer '+token();
  const res=await fetch(API_URL+path,{...opts,headers});
  let data={}; try{data=await res.json()}catch{data={}}
  if(!res.ok) throw new Error(data.error||data.detail||'Erro');
  return data;
}
function time(v){try{return new Date(v).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}catch{return ''}}
function dateMini(v){try{return new Date(v).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}catch{return ''}}
function cos(u){return u?.cosmetics||{}}
function roomForDm(a,b){const x=Math.min(a,b),y=Math.max(a,b);return `dm:${x}:${y}`}
function safeRarity(r){return String(r||'comum').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()}

function App(){
  const [user,setUser]=useState(()=>JSON.parse(localStorage.getItem('user')||'null'));
  useEffect(()=>{if(token())api('/api/me').then(d=>{saveUser(d.user);setUser(d.user)}).catch(()=>{clearSession();setUser(null)})},[]);
  return user?<Shell user={user} setUser={setUser}/>:<Auth onLogin={setUser}/>;
}

function Auth({onLogin}){
  const [mode,setMode]=useState('login');
  const [form,setForm]=useState({username:'',email:'',password:''});
  const [error,setError]=useState(''); const [loading,setLoading]=useState(false);
  async function submit(e){e.preventDefault();setError('');setLoading(true);try{const d=await api('/api/auth/'+mode,{method:'POST',body:JSON.stringify(form)});localStorage.setItem('token',d.token);saveUser(d.user);onLogin(d.user)}catch(err){setError(err.message)}finally{setLoading(false)}}
  return <main className="loginScreen">
    <section className="loginBrand">
      <img src={nodoLogo} alt="Nodo"/><p>Nodo</p><h1>Comunidade para evoluir como dev.</h1>
      <div className="loginChips"><span>Missões</span><span>Chat</span><span>Nodos</span><span>Perfil</span></div>
    </section>
    <form className="loginPanel" onSubmit={submit}>
      <div className="loginTop"><img src={nodoLogo} alt="Nodo"/><div><b>{mode==='login'?'Entrar':'Criar conta'}</b><small>{APP}</small></div></div>
      {mode==='register'&&<label>Nome<input value={form.username} onChange={e=>setForm({...form,username:e.target.value})} placeholder="PedroDev"/></label>}
      <label>Email<input value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="seu@email.com"/></label>
      <label>Senha<input type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="mínimo 8 caracteres"/></label>
      {error&&<p className="error">{error}</p>}
      <button className="primary" disabled={loading}>{loading?'Carregando...':mode==='login'?'Entrar':'Criar conta'}</button>
      <button className="ghost" type="button" onClick={()=>{setMode(mode==='login'?'register':'login');setError('')}}>{mode==='login'?'Criar conta':'Entrar'}</button>
    </form>
  </main>
}

function Shell({user,setUser}){
  const [page,setPage]=useState('dashboard');
  const [notif,setNotif]=useState({unread:0,notifications:[]});
  const nav=useMemo(()=>user.is_admin?[...pages,['admin','Admin',Shield]]:pages,[user.is_admin]);
  useEffect(()=>{api('/api/notifications').then(setNotif).catch(()=>{})},[page]);
  function logout(){clearSession();location.reload()}
  const Current={dashboard:Dashboard,community:Community,chat:GlobalChat,groups:Groups,friends:Friends,missions:Missions,achievements:Achievements,store:StorePage,customize:Customize,ranking:Ranking,courses:Courses,profile:Profile,admin:Admin}[page]||Dashboard;
  return <div className="discordShell">
    <aside className="serverRail">
      <button className="serverIcon active" onClick={()=>setPage('dashboard')}><img src={nodoLogo} alt="Nodo"/></button>
      <button className="serverIcon" onClick={()=>setPage('groups')}><Hash size={22}/></button>
      <button className="serverIcon" onClick={()=>setPage('chat')}><MessageCircle size={22}/></button>
      <button className="serverIcon add" onClick={()=>setPage('customize')}><Plus size={23}/></button>
    </aside>
    <aside className="channelPanel">
      <div className="guildHead"><b>Nodo</b><small>Dev social</small></div>
      <div className="channelGroup"><p>Canais</p>{nav.map(([id,label,Icon])=><button key={id} onClick={()=>setPage(id)} className={page===id?'active':''}><Icon size={17}/><span>{label}</span>{id==='notifications'&&notif.unread>0?<i>{notif.unread}</i>:null}</button>)}</div>
      <div className="miniProfile"><Avatar user={user} small/><div><b>{user.username}</b><small>{user.level||1} nível • {user.nodo_coins||0} NC</small></div><button onClick={logout}><LogOut size={17}/></button></div>
    </aside>
    <main className="mainPanel">
      <Topbar user={user} notif={notif} setPage={setPage}/>
      <Current user={user} setUser={setUser}/>
    </main>
    <RightBar user={user}/>
  </div>
}

function Topbar({user,notif,setPage}){return <header className="top"><div><p>Nodo</p><h2>{user.username}</h2></div><div className="topActions"><Badge>{user.level||1} nível</Badge><Badge>{user.xp||0} XP</Badge><Badge>{user.nodo_coins||0} NC</Badge><button className="icon" onClick={()=>setPage('notifications')}><Bell size={18}/>{notif.unread>0&&<i>{notif.unread}</i>}</button><Avatar user={user}/></div></header>}
function RightBar({user}){const[act,setAct]=useState([]);useEffect(()=>{api('/api/activity').then(d=>setAct(d.activity||[])).catch(()=>{})},[]);return <aside className="memberPanel"><h3>Atividade</h3><ProfileCard user={user} compact/><div className="activityList">{act.map(a=><div className="activity" key={a.id}><span></span><p>{a.text}</p><small>{dateMini(a.created_at)}</small></div>)}{!act.length&&<p className="muted">Sem atividade ainda.</p>}</div></aside>}
function Badge({children}){return <span className="badge">{children}</span>}
function Title({title,sub,icon}){return <div className="pageTitle"><div>{icon}</div><section><h1>{title}</h1>{sub&&<p>{sub}</p>}</section></div>}
function Avatar({user,small=false}){const c=cos(user);const v=user?.avatar||'ND';return <span className={`avatar ${small?'small':''} ${c.frame||''}`}>{String(v).startsWith('data:')?<img src={v}/>:<b>{String(v).slice(0,2)}</b>}{c.badge&&<i className={`miniBadge ${c.badge}`}></i>}</span>}
function ProfileCard({user,compact=false,override={}}){const c={...cos(user),...override};return <article className={`profileCard ${compact?'compact':''} ${c.theme||'theme-obsidian'} ${c.banner||''} ${c.effect||''}`}><div className="profileBanner"></div><div className="profileBody"><Avatar user={{...user,cosmetics:c}}/><div><b className={`nameplate ${c.nameplate||''}`}>{user.username}</b><p>{user.bio||'Sem bio.'}</p><div className="row"><Badge>Level {user.level||1}</Badge><Badge>{user.xp||0} XP</Badge></div></div></div></article>}
function CosmeticIcon({slug}){return <div className={`cosIcon ${slug||'default'}`}><span></span><i></i></div>}
function Toast({msg}){return msg?<p className="notice">{msg}</p>:null}

function Dashboard({user,setUser}){const[dash,setDash]=useState(null);const[msg,setMsg]=useState('');async function load(){setDash(await api('/api/dashboard'))}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function check(){try{const d=await api('/api/streak/checkin',{method:'POST'});saveUser(d.user);setUser(d.user);setMsg(d.message);load()}catch(e){setMsg(e.message)}}return <section><Title title="Início" sub="Seu painel" icon={<Home/>}/><Toast msg={msg}/><div className="hero"><div><h1>Evolua todos os dias.</h1><p>Missões, comunidade, Nodos e personalização.</p><button className="primary" onClick={check}><Flame/> Check-in</button></div><ProfileCard user={user}/></div><div className="stats"><Stat icon={<Code2/>} label="Missões" value={`${dash?.stats?.completed_missions??'-'} / ${dash?.stats?.total_missions??'-'}`}/><Stat icon={<Trophy/>} label="Ranking" value={dash?.stats?.ranking_position??'-'}/><Stat icon={<MessageCircle/>} label="Posts" value={dash?.stats?.posts??'-'}/><Stat icon={<Gem/>} label="Conquistas" value={dash?.stats?.achievements??'-'}/></div><Notifications/></section>}
function Stat({icon,label,value}){return <article className="stat">{icon}<small>{label}</small><b>{value}</b></article>}

function Community(){const[posts,setPosts]=useState([]);const[text,setText]=useState('');const[comment,setComment]=useState({});const[msg,setMsg]=useState('');async function load(){setPosts((await api('/api/posts')).posts||[])}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function send(){try{await api('/api/posts',{method:'POST',body:JSON.stringify({content:text})});setText('');load()}catch(e){setMsg(e.message)}}async function like(id){try{await api(`/api/posts/${id}/like`,{method:'POST'});load()}catch(e){setMsg(e.message)}}async function addComment(id){try{await api(`/api/posts/${id}/comments`,{method:'POST',body:JSON.stringify({content:comment[id]||''})});setComment({...comment,[id]:''});load()}catch(e){setMsg(e.message)}}async function report(p){try{await api('/api/reports',{method:'POST',body:JSON.stringify({target_type:'post',target_id:p.id,reason:'Post denunciado'})});setMsg('Denúncia enviada')}catch(e){setMsg(e.message)}}return <section><Title title="Comunidade" sub="Feed" icon={<MessageCircle/>}/><Toast msg={msg}/><div className="composer"><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Compartilhe algo..."/><button className="primary" onClick={send}><Send/> Publicar</button></div><div className="feed">{posts.map(p=><article className="post" key={p.id}><div className="postTop"><Avatar user={p.user} small/><div><b>{p.user.username}</b><small>{time(p.created_at)}</small></div><button className="icon" onClick={()=>report(p)}><Flag size={15}/></button></div><p>{p.content}</p><div className="postActions"><button onClick={()=>like(p.id)} className={p.liked?'liked':''}><Heart size={17}/>{p.likes_count}</button><button><MessageCircle size={17}/>{p.comments_count}</button></div><div className="comments">{(p.comments||[]).map(c=><div key={c.id}><b>{c.user.username}</b><span>{c.content}</span></div>)}<div className="commentBox"><input value={comment[p.id]||''} onChange={e=>setComment({...comment,[p.id]:e.target.value})} placeholder="Comentar"/><button onClick={()=>addComment(p.id)}><Send size={15}/></button></div></div></article>)}</div></section>}

function ChatBox({room='global',title='Chat',sub='Sala'}){const[messages,setMessages]=useState([]);const[text,setText]=useState('');const[msg,setMsg]=useState('');const ref=useRef(null);async function load(){setMessages((await api('/api/chat/history?room='+encodeURIComponent(room))).messages||[])}useEffect(()=>{load().catch(e=>setMsg(e.message));const t=setInterval(()=>load().catch(()=>{}),3000);return()=>clearInterval(t)},[room]);useEffect(()=>{ref.current?.scrollTo({top:ref.current.scrollHeight})},[messages]);async function send(){try{await api('/api/chat/message',{method:'POST',body:JSON.stringify({room,content:text})});setText('');load()}catch(e){setMsg(e.message)}}return <div className="chatBox"><div className="chatHead"><Hash size={18}/><div><b>{title}</b><small>{sub}</small></div></div><Toast msg={msg}/><div className="messages" ref={ref}>{messages.map(m=><div className="msg" key={m.id}><Avatar user={{username:m.username,avatar:m.username}} small/><div><div><b>{m.username}</b><small>{time(m.created_at)}</small></div><p>{m.content}</p></div></div>)}</div><div className="chatInput"><button><Plus size={18}/></button><input value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')send()}} placeholder={`Conversar em ${title}`}/><button><Smile size={18}/></button><button className="send" onClick={send}><Send size={18}/></button></div></div>}
function GlobalChat(){return <section><Title title="Chat" sub="Geral" icon={<Send/>}/><ChatBox room="global" title="geral" sub="Comunidade"/></section>}

function Groups(){const[groups,setGroups]=useState([]);const[form,setForm]=useState({name:'',description:'',topic:''});const[active,setActive]=useState(null);const[msg,setMsg]=useState('');async function load(){setGroups((await api('/api/groups')).groups||[])}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function create(){try{await api('/api/groups',{method:'POST',body:JSON.stringify(form)});setForm({name:'',description:'',topic:''});load()}catch(e){setMsg(e.message)}}async function join(id){try{await api(`/api/groups/${id}/join`,{method:'POST'});setMsg('Entrou no Nodo');load()}catch(e){setMsg(e.message)}}return <section><Title title="Nodos" sub="Grupos" icon={<Hash/>}/><Toast msg={msg}/><div className="split"><div><div className="miniForm"><input placeholder="Nome" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/><input placeholder="Tema" value={form.topic} onChange={e=>setForm({...form,topic:e.target.value})}/><button className="primary" onClick={create}><Plus/> Criar</button></div><div className="grid">{groups.map(g=><article className="card" key={g.id}><div className="cardTop"><Hash/><div><b>{g.name}</b><small>{g.topic} • nível {g.level}</small></div></div><p>{g.description||'Sem descrição.'}</p><div className="row"><Badge>{g.members_count} membros</Badge><button onClick={()=>setActive(g)}>Chat</button><button onClick={()=>join(g.id)}>{g.is_member?'Entrou':'Entrar'}</button></div></article>)}</div></div><aside>{active?<ChatBox room={`group:${active.id}`} title={active.name} sub="Nodo"/>:<div className="empty">Escolha um Nodo.</div>}</aside></div></section>}

function Friends(){const[q,setQ]=useState('');const[users,setUsers]=useState([]);const[data,setData]=useState({friends:[],pending:[]});const[dm,setDm]=useState(null);const[msg,setMsg]=useState('');async function load(){setData(await api('/api/friends'))}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function search(){setUsers((await api('/api/users?q='+encodeURIComponent(q))).users||[])}async function add(id){try{await api(`/api/friends/${id}`,{method:'POST'});setMsg('Pedido enviado');load()}catch(e){setMsg(e.message)}}async function accept(id){try{await api(`/api/friends/${id}/accept`,{method:'POST'});load()}catch(e){setMsg(e.message)}}return <section><Title title="Amigos" sub="Pedidos e DM" icon={<Users/>}/><Toast msg={msg}/><div className="split"><div><div className="search"><Search size={18}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar usuário"/><button onClick={search}>Buscar</button></div>{data.pending?.length>0&&<div className="panel"><h3>Pedidos</h3>{data.pending.map(p=><div className="userLine" key={p.id}><Avatar user={p.user} small/><b>{p.user.username}</b><button onClick={()=>accept(p.id)}>Aceitar</button></div>)}</div>}<div className="panel"><h3>Amigos</h3>{data.friends?.map(f=><div className="userLine" key={f.id}><Avatar user={f} small/><b>{f.username}</b><button onClick={()=>setDm(f)}>DM</button></div>)}{!data.friends?.length&&<p className="muted">Nenhum amigo ainda.</p>}</div><div className="panel"><h3>Busca</h3>{users.map(u=><div className="userLine" key={u.id}><Avatar user={u} small/><b>{u.username}</b><button onClick={()=>add(u.id)}><UserPlus size={16}/></button></div>)}</div></div><aside>{dm?<ChatBox room={roomForDm(JSON.parse(localStorage.getItem('user')).id,dm.id)} title={dm.username} sub="DM"/>:<div className="empty">Abra uma DM.</div>}</aside></div></section>}

function Missions({setUser}){const[rows,setRows]=useState([]);const[ans,setAns]=useState({});const[msg,setMsg]=useState('');async function load(){setRows((await api('/api/missions')).missions||[])}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function submit(id){try{const d=await api(`/api/missions/${id}/submit`,{method:'POST',body:JSON.stringify({answer:ans[id]||''})});if(d.user){saveUser(d.user);setUser(d.user)}setMsg(d.message);load()}catch(e){setMsg(e.message)}}return <section><Title title="Missões" sub="Desafios" icon={<Code2/>}/><Toast msg={msg}/><div className="grid">{rows.map(m=><article className="card mission" key={m.id}><div className="cardTop"><Code2/><div><b>{m.title}</b><small>{m.category} • {m.difficulty}</small></div></div><p>{m.description}</p><Badge>+{m.xp_reward} XP • +{m.coin_reward} NC</Badge><textarea disabled={m.completed} value={ans[m.id]||''} onChange={e=>setAns({...ans,[m.id]:e.target.value})} placeholder="Resposta"/><button disabled={m.completed} onClick={()=>submit(m.id)}>{m.completed?'Concluída':'Enviar'}</button></article>)}</div></section>}
function Courses(){const[rows,setRows]=useState([]);useEffect(()=>{api('/api/courses').then(d=>setRows(d.courses||[])).catch(()=>{})},[]);return <section><Title title="Cursos" sub="Trilhas" icon={<GraduationCap/>}/><div className="grid">{rows.map(c=><article className="card" key={c.id}><GraduationCap/><h3>{c.title}</h3><p>{c.description}</p><Badge>{c.category} • {c.level}</Badge></article>)}</div></section>}
function Ranking(){const[rows,setRows]=useState([]);useEffect(()=>{api('/api/ranking').then(d=>setRows(d.ranking||[])).catch(()=>{})},[]);return <section><Title title="Ranking" sub="Top devs" icon={<Trophy/>}/><div className="panel table">{rows.map((u,i)=><div className="rank" key={u.id}><b>#{i+1}</b><Avatar user={u} small/><span>{u.username}</span><Badge>{u.level} nível</Badge><Badge>{u.xp} XP</Badge><Badge>{u.nodo_coins} NC</Badge></div>)}</div></section>}
function Achievements(){const[rows,setRows]=useState([]);useEffect(()=>{api('/api/achievements').then(d=>setRows(d.achievements||[])).catch(()=>{})},[]);return <section><Title title="Conquistas" sub="Troféus" icon={<Trophy/>}/><div className="grid">{rows.map(a=><article className={`card achievement ${a.unlocked?'on':'off'}`} key={a.id}><Trophy/><h3>{a.title}</h3><p>{a.description}</p><Badge>{a.unlocked?'Desbloqueada':'Bloqueada'}</Badge></article>)}</div></section>}

function StorePage({setUser}){const[items,setItems]=useState([]);const[cat,setCat]=useState('all');const[msg,setMsg]=useState('');async function load(){setItems((await api('/api/store')).items||[])}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function buy(id){try{const d=await api(`/api/store/${id}/purchase`,{method:'POST'});if(d.user){saveUser(d.user);setUser(d.user)}setMsg(d.message);load()}catch(e){setMsg(e.message)}}const list=items.filter(i=>cat==='all'||i.item_type===cat);return <section><Title title="Loja" sub="Cosméticos" icon={<ShoppingBag/>}/><Toast msg={msg}/><Tabs value={cat} setValue={setCat} rows={categories}/><div className="shopGrid">{list.map(i=><article className={`shopItem rarity-${safeRarity(i.rarity)}`} key={i.id}><CosmeticIcon slug={i.icon}/><h3>{i.name}</h3><p>{i.description}</p><div className="row"><Badge>{i.rarity}</Badge><Badge>{i.price} NC</Badge></div><button disabled={i.owned} onClick={()=>buy(i.id)}>{i.owned?'Comprado':'Comprar'}</button></article>)}</div></section>}
function Tabs({rows,value,setValue}){return <div className="tabs">{rows.map(([id,label])=><button key={id} onClick={()=>setValue(id)} className={value===id?'active':''}>{label}</button>)}</div>}

function Customize({user,setUser}){const[items,setItems]=useState([]);const[cat,setCat]=useState('frame');const[preview,setPreview]=useState({});const[msg,setMsg]=useState('');async function load(){setItems((await api('/api/store')).items||[])}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function equip(item){try{const d=await api('/api/me/equip',{method:'POST',body:JSON.stringify({slot:item.item_type,item_id:item.id})});saveUser(d.user);setUser(d.user);setMsg('Equipado')}catch(e){setMsg(e.message)}}const list=items.filter(i=>i.item_type===cat);return <section><Title title="Personalizar" sub="Perfil" icon={<Palette/>}/><Toast msg={msg}/><div className="customLayout"><div><Tabs value={cat} setValue={setCat} rows={categories.filter(c=>c[0]!=='all')}/><div className="customGrid">{list.map(i=><button className={`customItem ${i.owned?'owned':'locked'}`} key={i.id} onMouseEnter={()=>setPreview({[i.item_type]:i.icon})} onClick={()=>i.owned||i.price===0?equip(i):setMsg('Compre esse item na loja')}><CosmeticIcon slug={i.icon}/><b>{i.name}</b><span>{i.owned||i.price===0?'Equipar':`${i.price} NC`}</span></button>)}</div></div><aside><ProfileCard user={user} override={preview}/><div className="panel"><h3>Preview</h3><p className="muted">Passe o mouse em um item e veja no perfil.</p><button onClick={()=>setPreview({})}>Limpar preview</button></div></aside></div></section>}

function Profile({user,setUser}){const[form,setForm]=useState({username:user.username,email:user.email,bio:user.bio||'',avatar:user.avatar||''});const[msg,setMsg]=useState('');async function save(){try{const d=await api('/api/me',{method:'PUT',body:JSON.stringify(form)});saveUser(d.user);setUser(d.user);setMsg('Salvo')}catch(e){setMsg(e.message)}}function upload(e){const file=e.target.files?.[0];if(!file)return;const r=new FileReader();r.onload=()=>setForm({...form,avatar:r.result});r.readAsDataURL(file)}return <section><Title title="Perfil" sub="Conta" icon={<User/>}/><Toast msg={msg}/><div className="split"><div className="panel form"><label>Nome<input value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label><label>Email<input value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Bio<textarea value={form.bio} onChange={e=>setForm({...form,bio:e.target.value})}/></label><label className="upload"><ImagePlus/> Avatar<input type="file" accept="image/*" onChange={upload}/></label><button className="primary" onClick={save}>Salvar</button></div><ProfileCard user={{...user,...form}}/></div></section>}

function Notifications(){const[data,setData]=useState({notifications:[]});useEffect(()=>{api('/api/notifications').then(setData).catch(()=>{})},[]);return <div className="panel"><h3>Notificações</h3>{data.notifications?.slice(0,5).map(n=><div className="notif" key={n.id}><Bell size={16}/><div><b>{n.title}</b><p>{n.body}</p></div></div>)}{!data.notifications?.length&&<p className="muted">Nada novo.</p>}</div>}

function Admin(){const[d,setD]=useState(null);const[msg,setMsg]=useState('');async function load(){setD(await api('/api/admin/overview'))}useEffect(()=>{load().catch(e=>setMsg(e.message))},[]);async function patchUser(id,obj){try{await api(`/api/admin/users/${id}`,{method:'PATCH',body:JSON.stringify(obj)});load()}catch(e){setMsg(e.message)}}async function del(path){try{await api(path,{method:'DELETE'});load()}catch(e){setMsg(e.message)}}return <section><Title title="Admin" sub="Controle" icon={<Shield/>}/><Toast msg={msg}/>{d&&<><div className="stats"><Stat icon={<Users/>} label="Usuários" value={d.summary.users}/><Stat icon={<MessageCircle/>} label="Posts" value={d.summary.posts}/><Stat icon={<Hash/>} label="Nodos" value={d.summary.groups}/><Stat icon={<Flag/>} label="Denúncias" value={d.summary.reports}/></div><div className="panel table"><h3>Usuários</h3>{d.users.map(u=><div className="adminRow" key={u.id}><Avatar user={u} small/><span>{u.username}</span><span>{u.email}</span><button onClick={()=>patchUser(u.id,{is_admin:!u.is_admin})}>{u.is_admin?'Rem ADM':'Dar ADM'}</button><button onClick={()=>patchUser(u.id,{is_banned:!u.is_banned})}>{u.is_banned?'Desbanir':'Banir'}</button></div>)}</div><div className="panel table"><h3>Posts</h3>{d.posts.map(p=><div className="adminRow" key={p.id}><span>{p.user.username}</span><span>{p.content}</span><button className="danger" onClick={()=>del(`/api/admin/posts/${p.id}`)}><Trash2 size={15}/></button></div>)}</div></>}</section>}

createRoot(document.getElementById('root')).render(<App/>);
