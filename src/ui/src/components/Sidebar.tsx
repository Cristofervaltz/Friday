import React, { useState } from 'react';
import { Settings, MessageSquare, Bot, Trash2, Pencil } from 'lucide-react';
import { useTranslation } from '../i18n/index.ts';
import './Sidebar.css';

// sidebar props interface
interface SidebarProps {
  onAction: (action: string, payload?: string) => void;
  connected: boolean;
  chats: Array<{id: string, title: string, updated_at?: number}>;
  currentChatId: string;
}

// helper to group chats by date
const groupChats = (chats: SidebarProps['chats'], t: any) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  const lastWeek = new Date(today);
  lastWeek.setDate(lastWeek.getDate() - 7);

  const groups: { label: string; chats: typeof chats }[] = [
    { label: t('sidebar.today') || 'Today', chats: [] },
    { label: t('sidebar.yesterday') || 'Yesterday', chats: [] },
    { label: t('sidebar.previous_7_days') || 'Previous 7 Days', chats: [] },
    { label: t('sidebar.older') || 'Older', chats: [] }
  ];

  chats.forEach(c => {
    if (!c.updated_at) {
      groups[3].chats.push(c);
      return;
    }
    const d = new Date(c.updated_at * 1000);
    if (d >= today) {
      groups[0].chats.push(c);
    } else if (d >= yesterday) {
      groups[1].chats.push(c);
    } else if (d >= lastWeek) {
      groups[2].chats.push(c);
    } else {
      groups[3].chats.push(c);
    }
  });

  return groups.filter(g => g.chats.length > 0);
};

// sidebar navigation component wrapped in memo to prevent rerenders during chat streaming
export const Sidebar = React.memo(function Sidebar({ onAction, connected, chats, currentChatId }: SidebarProps) {
  const { t } = useTranslation();
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const [chatToDelete, setChatToDelete] = useState<string | null>(null);

  const filteredChats = chats.filter(c => c.title.toLowerCase().includes(searchQuery.toLowerCase()));
  const grouped = groupChats(filteredChats, t);

  return (
    <aside className="sidebar">
      {/* Custom Delete Modal */}
      {chatToDelete && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
          <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '20px', width: '300px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--text)' }}>{t('sidebar.delete_confirm')}</h3>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => setChatToDelete(null)}>{t('common.cancel') || 'Cancel'}</button>
              <button className="btn" style={{ background: 'var(--red)', color: 'white', border: 'none' }} onClick={() => {
                onAction('delete_chat', chatToDelete);
                setChatToDelete(null);
              }}>{t('common.delete') || 'Delete'}</button>
            </div>
          </div>
        </div>
      )}

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

      <div className="sidebar-search" style={{ margin: '12px 16px 0', padding: '0' }}>
        <input 
          type="text" 
          placeholder={t('sidebar.search_chats') || 'Search chats...'}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          style={{ width: '100%', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text)', fontSize: '13px' }}
        />
      </div>

      <div className="chats-list flex-grow">
        {grouped.map((group, idx) => (
          <div key={idx} className="chat-group">
            <div className="side-label" style={{ marginTop: idx === 0 ? '12px' : '20px' }}>{group.label}</div>
            {group.chats.map(chat => {
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
                    setChatToDelete(chat.id);
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          );
        })}
        </div>
        ))}
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
