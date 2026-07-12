import React from 'react';
import { LoaderCircle } from 'lucide-react';

export function classNames(...parts) {
  return parts.filter(Boolean).join(' ');
}

export function time(value) {
  try {
    return new Date(value).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export function dateMini(value) {
  try {
    return new Date(value).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
  } catch {
    return '';
  }
}

export function cosmetics(user) {
  return user?.cosmetics || {};
}

export function roomForDm(first, second) {
  const ids = [Number(first), Number(second)].sort((a, b) => a - b);
  return `dm:${ids[0]}:${ids[1]}`;
}

export function safeRarity(value) {
  return String(value || 'comum')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function Badge({ children }) {
  return <span className="badge">{children}</span>;
}

export function Title({ title, subtitle, icon }) {
  return (
    <div className="pageTitle">
      <div className="titleIcon">{icon}</div>
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </div>
  );
}

export function Avatar({ user, small = false }) {
  const visual = cosmetics(user);
  const value = user?.avatar || user?.username || 'ND';
  const isImage = String(value).startsWith('data:') || /^https?:\/\//.test(String(value));
  return (
    <span className={classNames('avatar', small && 'small', visual.frame)}>
      {isImage ? <img src={value} alt={user?.username || 'Avatar'} /> : <b>{String(value).slice(0, 2).toUpperCase()}</b>}
      {visual.badge ? <i className={classNames('miniBadge', visual.badge)} /> : null}
    </span>
  );
}

export function ProfileCard({ user, compact = false, override = {} }) {
  const visual = { ...cosmetics(user), ...override };
  return (
    <article className={classNames('profileCard', compact && 'compact', visual.theme || 'theme-obsidian', visual.banner, visual.effect)}>
      <div className="profileBanner" />
      <div className="profileBody">
        <Avatar user={{ ...user, cosmetics: visual }} />
        <div className="profileText">
          <b className={classNames('nameplate', visual.nameplate)}>{user?.username || 'Usuário'}</b>
          <p>{user?.bio || 'Sem bio.'}</p>
          <div className="row">
            <Badge>Nível {user?.level || 1}</Badge>
            <Badge>{user?.xp || 0} XP</Badge>
          </div>
        </div>
      </div>
    </article>
  );
}

export function CosmeticIcon({ slug }) {
  return (
    <div className={classNames('cosIcon', slug || 'default')}>
      <span />
      <i />
    </div>
  );
}

export function Toast({ message, type = 'info', onClose }) {
  if (!message) return null;
  return (
    <button className={classNames('toast', `toast-${type}`)} onClick={onClose} type="button">
      {message}
    </button>
  );
}

export function Loading({ label = 'Carregando' }) {
  return (
    <div className="loadingState">
      <LoaderCircle className="spin" size={22} />
      <span>{label}</span>
    </div>
  );
}

export function Empty({ children = 'Nada por aqui.' }) {
  return <div className="empty">{children}</div>;
}
