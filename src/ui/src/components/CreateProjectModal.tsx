import React, { useState, useCallback } from 'react';
import { X, FolderPlus } from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import { useTranslation } from '../i18n/index.ts';
import './CreateProjectModal.css';

// project picker modal props
interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (path: string) => void;
  onSkip: () => void;
}

// create project modal wrapped in memo
export const CreateProjectModal = React.memo(function CreateProjectModal({ isOpen, onClose, onProjectCreated, onSkip }: CreateProjectModalProps) {
  const [selecting, setSelecting] = useState(false);
  // translations hook
  const { t } = useTranslation();

  // trigger native directory picker
  const handleAddFolder = useCallback(async () => {
    if (selecting) return;
    setSelecting(true);
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: t('project.dialog_title'),
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
  }, [selecting, t, onProjectCreated, onClose]);

  const handleSkip = useCallback(() => {
    onSkip();
    onClose();
  }, [onSkip, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="create-project-modal glass-panel">
        <div className="modal-header">
          <h2>{t('project.create_title')}</h2>
          <button className="icon-btn" onClick={onClose}><X size={24} /></button>
        </div>

        <div className="modal-body">
          <label className="input-label">{t('project.select_folder')}</label>
          <button 
            className="add-folder-btn" 
            onClick={handleAddFolder} 
            disabled={selecting}
          >
            <FolderPlus size={18} />
            + {t('project.add_folder')}
          </button>
        </div>

        <div className="modal-footer" style={{ borderTop: 'none', background: 'transparent' }}>
          <button type="button" className="btn-secondary" onClick={handleSkip}>
            {t('common.skip')}
          </button>
        </div>
      </div>
    </div>
  );
});

