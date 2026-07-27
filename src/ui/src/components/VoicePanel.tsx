import { ChevronRight } from 'lucide-react';
import './VoicePanel.css';

interface VoicePanelProps {
  isOpen: boolean;
  onClose: () => void;
  isListening: boolean;
  connected: boolean;
}

export function VoicePanel({ isOpen, onClose, isListening, connected }: VoicePanelProps) {
  return (
    <div className={`voice-panel-container ${isOpen ? 'open' : ''}`}>
      <div className="voice-panel glass-panel">
        <button className="voice-close-btn" onClick={onClose} title="Close Voice Panel">
          <ChevronRight size={24} />
        </button>
        
        <div className="voice-header">
          <h3>Voice Interface</h3>
        </div>
        
        <div className="visualizer-container">
          <div className={`orb ${isListening ? 'listening' : 'idle'}`}>
            <div className="orb-core"></div>
            <div className="orb-ring ring-1"></div>
            <div className="orb-ring ring-2"></div>
            <div className="orb-ring ring-3"></div>
          </div>
          <p className="voice-status">
            {isListening ? 'Listening...' : connected ? 'Ready' : 'Offline'}
          </p>
        </div>
      </div>
    </div>
  );
}
