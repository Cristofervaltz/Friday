import React, { useState } from 'react';
import { Settings, MessageSquare, Bot, Trash2, Pencil } from 'lucide-react';
import { useTranslation } from '../i18n/index.ts';
import './Sidebar.css';

// sidebar props interface
interface SidebarProps {
  onAction: (action: string, payload?: string) => void;
  connected: boolean;
  chats: Array<{id: string, title: string}>;
  currentChatId: string;
}

// sidebar navigation component wrapped in memo to prevent rerenders during chat streaming
export const Sidebar = React.memo(function Sidebar({ onAction, connected, chats, currentChatId }: SidebarProps) {
  const { t } = useTranslation();
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">
          <img src="/app-icon.png" alt="Friday" />
        </div>
        <span className="brand-name">Friday</span>
        <span className="brand-status">
          {connected ? <><span className="dot" style={{backgroundColor: 'var(--green)', boxShadow: '0 0 8px var(--green)'}}></span>Online</> : <><span className="dot" style={{backgroundColor: 'var(--text-low)', boxShadow: 'none'}}></span>Offline</>}
        </span>
      </div>

      <button className="btn-new" onClick={() => onAction('new_chat')} disabled={!connected}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
        {t('sidebar.new_chat')}
      </button>

      <div className="side-label">{t('sidebar.chats')}</div>
      <div className="chats-list flex-grow">
        {chats.map(chat => {
          const isSubAgent = chat.title.startsWith('[Sub-Agent]');
          const displayTitle = isSubAgent ? chat.title.replace('[Sub-Agent]', '').trim() : chat.title;
          
          return (
            <div 
              key={chat.id} 
              className={`nav-item ${chat.id === currentChatId ? 'active' : ''}`}
              onClick={() => onAction('switch_chat', chat.id)}
            >
              {isSubAgent ? <Bot size={15} /> : <MessageSquare size={15} />}
              {editingChatId === chat.id ? (
                <input 
                  autoFocus
                  style={{ background: 'transparent', border: 'none', color: 'inherit', outline: 'none', flexGrow: 1, fontFamily: 'inherit', fontSize: 'inherit', padding: 0 }}
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={() => {
                    if (editTitle.trim() && editTitle !== chat.title) {
                      onAction('rename_chat', JSON.stringify({id: chat.id, title: editTitle.trim()}));
                    }
                    setEditingChatId(null);
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.currentTarget.blur();
                    } else if (e.key === 'Escape') {
                      setEditingChatId(null);
                    }
                  }}
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <span className="truncate">{displayTitle}</span>
              )}
              
              <div className="chat-actions">
                <button 
                  className="icon-btn-small" 
                  title={t('sidebar.rename_chat')} 
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingChatId(chat.id);
                    setEditTitle(chat.title);
                  }}
                >
                  <Pencil size={12} />
                </button>
                <button 
                  className="icon-btn-small delete-btn" 
                  title={t('sidebar.delete_chat')} 
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(t('sidebar.delete_confirm'))) onAction('delete_chat', chat.id);
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="sidebar-footer">
        <div className="side-row" onClick={() => onAction('/settings')}>
          <Settings size={15} />
          {t('sidebar.settings')}
        </div>
      </div>
    </aside>
  );
});
