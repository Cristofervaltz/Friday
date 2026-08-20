import React from 'react';
import { ChevronRight } from 'lucide-react';
import { useTranslation } from '../i18n/index.ts';
import './VoicePanel.css';

// props for voice panel side drawer
interface VoicePanelProps {
  isOpen: boolean;
  onClose: () => void;
  isListening: boolean;
  connected: boolean;
}

// voice panel drawer component memoized to avoid heavy visualizer rerenders
export const VoicePanel = React.memo(function VoicePanel({ isOpen, onClose, isListening, connected }: VoicePanelProps) {
  // translation helper
  const { t } = useTranslation();

  return (
    <div className={`voice-panel-container ${isOpen ? 'open' : ''}`}>
      <div className="voice-panel glass-panel">
        <button className="voice-close-btn" onClick={onClose} title={t('voice.close_tooltip')}>
          <ChevronRight size={24} />
        </button>
        
        <div className="voice-header">
          <h3>{t('voice.title')}</h3>
        </div>
        
        <div className="visualizer-container">
          <div className={`orb ${isListening ? 'listening' : 'idle'}`}>
            <div className="orb-core"></div>
            <div className="orb-ring ring-1"></div>
            <div className="orb-ring ring-2"></div>
            <div className="orb-ring ring-3"></div>
          </div>
          <p className="voice-status">
            {isListening ? t('voice.listening') : connected ? t('voice.ready') : t('voice.offline')}
          </p>
          {isListening && (
            <button 
              onClick={onClose}
              style={{
                marginTop: '16px',
                padding: '8px 16px',
                background: 'var(--red)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500
              }}
            >
              Cancel Recording
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

