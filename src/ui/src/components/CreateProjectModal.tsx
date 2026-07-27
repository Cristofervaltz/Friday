import { useState } from 'react';
import { X, FolderPlus } from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import './CreateProjectModal.css';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (path: string) => void;
  onSkip: () => void;
}

export function CreateProjectModal({ isOpen, onClose, onProjectCreated, onSkip }: CreateProjectModalProps) {
  const [selecting, setSelecting] = useState(false);

  const handleAddFolder = async () => {
    if (selecting) return;
    setSelecting(true);
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: 'Select Workspace Folder',
      });
      if (selected) {
        onProjectCreated(selected as string);
        onClose();
      }
    } catch (err) {
      console.error('Failed to open dialog:', err);
    } finally {
      setSelecting(false);
    }
  };

  const handleSkip = () => {
    onSkip();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="create-project-modal glass-panel">
        <div className="modal-header">
          <h2>Create Project</h2>
          <button className="icon-btn" onClick={onClose}><X size={24} /></button>
        </div>

        <div className="modal-body">
          <label className="input-label">Select Folder(s)</label>
          <button 
            className="add-folder-btn" 
            onClick={handleAddFolder} 
            disabled={selecting}
          >
            <FolderPlus size={18} />
            + Add Folder
          </button>
        </div>

        <div className="modal-footer" style={{ borderTop: 'none', background: 'transparent' }}>
          <button type="button" className="btn-secondary" onClick={handleSkip}>
            Skip
          </button>
        </div>
      </div>
    </div>
  );
}
