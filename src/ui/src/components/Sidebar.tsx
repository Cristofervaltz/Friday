import { Mic, Trash2, Settings } from 'lucide-react';
import './Sidebar.css';

interface SidebarProps {
  onAction: (action: string) => void;
  connected: boolean;
}

export function Sidebar({ onAction, connected }: SidebarProps) {
  return (
    <div className="sidebar glass-panel">
      <div className="sidebar-header">
        <div className="logo-placeholder">F</div>
      </div>
      
      <div className="sidebar-actions">
        <button 
          className="action-btn primary"
          onClick={() => onAction('/voice')}
          disabled={!connected}
          title="Start Voice Input (/voice)"
        >
          <Mic size={20} />
          <span>Voice</span>
        </button>

        <button 
          className="action-btn"
          onClick={() => onAction('/clear')}
          disabled={!connected}
          title="Clear Conversation (/clear)"
        >
          <Trash2 size={20} />
          <span>Clear</span>
        </button>
      </div>

      <div className="sidebar-footer">
        <button 
          className="action-btn icon-only" 
          title="Settings" 
          onClick={() => onAction('/settings')}
        >
          <Settings size={20} />
        </button>
      </div>
    </div>
  );
}
