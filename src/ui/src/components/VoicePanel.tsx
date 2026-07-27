import { Mic, MicOff } from 'lucide-react';
import './VoicePanel.css';

interface VoicePanelProps {
  isListening: boolean;
  onVoiceClick: () => void;
  connected: boolean;
}

export function VoicePanel({ isListening, onVoiceClick, connected }: VoicePanelProps) {
  return (
    <div className="voice-panel glass-panel">
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

      <div className="voice-controls">
        <button 
          className={`mic-button ${isListening ? 'active' : ''}`}
          onClick={onVoiceClick}
          disabled={!connected}
          title="Start Voice Input"
        >
          {isListening ? <MicOff size={32} /> : <Mic size={32} />}
        </button>
      </div>
    </div>
  );
}
