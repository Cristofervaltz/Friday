import { useState, useRef, useEffect } from 'react';
import { Folder, FolderPlus, FolderX, ChevronDown } from 'lucide-react';
import './WorkspaceSelector.css';

interface WorkspaceSelectorProps {
  currentWorkspace: string;
  onSelectNew: () => void;
  onClearWorkspace: () => void;
}

export function WorkspaceSelector({ currentWorkspace, onSelectNew, onClearWorkspace }: WorkspaceSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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

  const getShortName = (path: string) => {
    if (!path) return 'No Project';
    if (path.length > 30) {
      return path.substring(0, 3) + '...' + path.substring(path.length - 24);
    }
    return path;
  };

  return (
    <div className="workspace-selector-container" ref={containerRef}>
      <button 
        className="workspace-trigger" 
        onClick={() => setIsOpen(!isOpen)}
        title={currentWorkspace || 'No Project'}
      >
        <Folder size={14} className="folder-icon" />
        <span className="workspace-name">{getShortName(currentWorkspace)}</span>
        <ChevronDown size={14} className="chevron-icon" />
      </button>

      {isOpen && (
        <div className="workspace-dropdown glass-panel">
          {currentWorkspace && (
            <div className="dropdown-item active">
              <Folder size={16} />
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
            <span className="dropdown-text">New Project</span>
          </button>
          
          <button 
            className="dropdown-item action"
            onClick={() => {
              setIsOpen(false);
              onClearWorkspace();
            }}
          >
            <FolderX size={16} />
            <span className="dropdown-text">No Project</span>
          </button>
        </div>
      )}
    </div>
  );
}
