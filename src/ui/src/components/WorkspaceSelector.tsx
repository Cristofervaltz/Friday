import React, { useState, useRef, useEffect, useCallback } from 'react';
import { FolderPlus, FolderX } from 'lucide-react';
import { useTranslation } from '../i18n/index.ts';
import './WorkspaceSelector.css';

// workspace selector props
interface WorkspaceSelectorProps {
  currentWorkspace: string;
  onSelectNew: () => void;
  onClearWorkspace: () => void;
}

// workspace selector dropdown memoized for performance
export const WorkspaceSelector = React.memo(function WorkspaceSelector({ currentWorkspace, onSelectNew, onClearWorkspace }: WorkspaceSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // shorten long workspace path for display
  const getShortName = useCallback((path: string) => {
    if (!path) return t('workspace.no_project');
    if (path.length > 30) {
      return path.substring(0, 3) + '...' + path.substring(path.length - 24);
    }
    return path;
  }, [t]);

  return (
    <div className="workspace-selector-container" ref={containerRef}>
      <button 
        className="ws-selector" 
        onClick={() => setIsOpen(!isOpen)}
        title={currentWorkspace || t('workspace.no_project')}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <span className="workspace-name">{getShortName(currentWorkspace)}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6"/></svg>
      </button>

      {isOpen && (
        <div className="workspace-dropdown glass-panel">
          {currentWorkspace && (
            <div className="dropdown-item active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              <span className="dropdown-text" title={currentWorkspace}>
                {currentWorkspace.length > 40 ? '...' + currentWorkspace.slice(-37) : currentWorkspace}
              </span>
            </div>
          )}
          
          <button 
            className="dropdown-item action"
            onClick={() => {
              setIsOpen(false);
              onSelectNew();
            }}
          >
            <FolderPlus size={16} />
            <span className="dropdown-text">{t('workspace.new_project')}</span>
          </button>
          
          <button 
            className="dropdown-item action"
            onClick={() => {
              setIsOpen(false);
              onClearWorkspace();
            }}
          >
            <FolderX size={16} />
            <span className="dropdown-text">{t('workspace.clear_project')}</span>
          </button>
        </div>
      )}
    </div>
  );
});
