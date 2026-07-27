import { Settings, Plus, MessageSquare, Bot, Pencil, Trash2 } from 'lucide-react';
import './Sidebar.css';

interface SidebarProps {
  onAction: (action: string, payload?: string) => void;
  connected: boolean;
  chats: Array<{id: string, title: string}>;
  currentChatId: string;
}

export function Sidebar({ onAction, connected, chats, currentChatId }: SidebarProps) {
  return (
    <div className="sidebar glass-panel">
      <div className="sidebar-header">
        <img src="/app-icon.png" alt="Friday Logo" className="logo-image" />
      </div>

      <div className="sidebar-section flex-grow">
        <div className="section-title">
          <span>Chats</span>
          <button className="icon-btn" onClick={() => onAction('new_chat')} disabled={!connected}>
            <Plus size={16} />
          </button>
        </div>
        <div className="chats-list">
          {chats.map(chat => {
            const isSubAgent = chat.title.startsWith('[Sub-Agent]');
            const displayTitle = isSubAgent ? chat.title.replace('[Sub-Agent]', '').trim() : chat.title;
            
            return (
              <div key={chat.id} className={`chat-item-wrapper ${chat.id === currentChatId ? 'active' : ''}`}>
                <button 
                  className="chat-item"
                  onClick={() => onAction('switch_chat', chat.id)}
                >
                  {isSubAgent ? <Bot size={14} className="subagent-icon" /> : <MessageSquare size={14} />}
                  <span className="truncate">{displayTitle}</span>
                </button>
                <div className="chat-actions">
                  <button className="icon-btn-small" title="Rename Chat" onClick={(e) => {
                    e.stopPropagation();
                    const newTitle = prompt('Enter new chat name:', chat.title);
                    if (newTitle && newTitle.trim()) onAction('rename_chat', JSON.stringify({id: chat.id, title: newTitle.trim()}));
                  }}>
                    <Pencil size={12} />
                  </button>
                  <button className="icon-btn-small delete-btn" title="Delete Chat" onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Delete this chat?')) onAction('delete_chat', chat.id);
                  }}>
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="sidebar-footer">
        <button 
          className="action-btn" 
          title="Settings" 
          onClick={() => onAction('/settings')}
        >
          <Settings size={20} />
          <span>Settings</span>
        </button>
      </div>
    </div>
  );
}
