import React, { useState, useEffect } from 'react';
import { X, Save, Palette, Bot, Monitor } from 'lucide-react';
import './SettingsModal.css';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  voiceAutoSend?: boolean;
  onVoiceAutoSendChange?: (val: boolean) => void;
  onSettingsChanged?: (settings: Record<string, string>) => void;
}

type TabId = 'appearance' | 'agent' | 'app';

export function SettingsModal({ isOpen, onClose, voiceAutoSend = true, onVoiceAutoSendChange, onSettingsChanged }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>('appearance');
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/settings');
      if (!response.ok) throw new Error('Failed to load settings');
      const data = await response.json();
      setSettings(data);
    } catch (err: any) {
      setError(err.message || 'Error loading settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (!response.ok) throw new Error('Failed to save settings');
      setSuccess('Settings saved successfully!');
      
      if (onSettingsChanged) {
        onSettingsChanged(settings);
      }
      
      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Error saving settings');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="settings-modal-container glass-panel">
        <div className="settings-sidebar">
          <div className="settings-header-title">Settings</div>
          <div className="settings-nav">
            <button 
              className={`nav-item ${activeTab === 'appearance' ? 'active' : ''}`}
              onClick={() => setActiveTab('appearance')}
            >
              <Palette size={16} /> Appearance
            </button>
            <button 
              className={`nav-item ${activeTab === 'agent' ? 'active' : ''}`}
              onClick={() => setActiveTab('agent')}
            >
              <Bot size={16} /> Agent
            </button>
            <button 
              className={`nav-item ${activeTab === 'app' ? 'active' : ''}`}
              onClick={() => setActiveTab('app')}
            >
              <Monitor size={16} /> App
            </button>
          </div>
        </div>

        <div className="settings-content-wrapper">
          <div className="modal-header">
            <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Settings</h2>
            <button className="icon-btn" onClick={onClose}><X size={24} /></button>
          </div>

          <div className="modal-body">
            {loading ? (
              <div className="loading-state">Loading settings...</div>
            ) : (
              <form id="settings-form" onSubmit={handleSave} className="settings-form">
                
                {/* APPEARANCE TAB */}
                {activeTab === 'appearance' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>Theme</label>
                      <select 
                        value={settings.theme || 'dark'}
                        onChange={e => setSettings({...settings, theme: e.target.value})}
                      >
                        <option value="dark">Dark (Midnight Aurora)</option>
                        <option value="light">Light (Daylight)</option>
                      </select>
                    </div>
                    
                    <div className="form-group">
                      <label>Accent Color</label>
                      <div className="color-picker-group">
                        <input 
                          type="color" 
                          value={settings.accent_color || '#6366F1'}
                          onChange={e => setSettings({...settings, accent_color: e.target.value})}
                          className="color-picker-input"
                        />
                        <span className="color-hex">{settings.accent_color || '#6366F1'}</span>
                      </div>
                      <p className="form-hint">Choose your preferred accent color for buttons and highlights.</p>
                    </div>
                  </div>
                )}

                {/* AGENT TAB */}
                {activeTab === 'agent' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>Provider</label>
                      <select 
                        value={settings.llm_provider || 'openai'}
                        onChange={e => setSettings({...settings, llm_provider: e.target.value})}
                      >
                        <option value="openai">OpenAI</option>
                        <option value="gemini">Gemini (Google AI Studio)</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="ollama">Ollama (Local)</option>
                        <option value="openrouter">OpenRouter</option>
                      </select>
                      {settings.llm_provider === 'ollama' && (
                        <div className="settings-warning" style={{ color: '#ff9800', fontSize: '0.85em', marginTop: '5px' }}>
                          ⚠️ Note: Ollama does not fully support Function Calling yet. Friday's autonomous actions (reading/writing files) may not work correctly with local models.
                        </div>
                      )}
                    </div>

                    <div className="form-group">
                      <label>API Key</label>
                      <input 
                        type="password"
                        placeholder="sk-..."
                        value={settings.llm_api_key || ''}
                        onChange={e => setSettings({...settings, llm_api_key: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>Model</label>
                      <input 
                        type="text"
                        placeholder="e.g. gpt-4o"
                        value={settings.llm_model || ''}
                        onChange={e => setSettings({...settings, llm_model: e.target.value})}
                      />
                    </div>
                    
                    <div className="form-group">
                      <label>Max Tool Iterations</label>
                      <input 
                        type="number"
                        min="1"
                        max="100"
                        placeholder="10"
                        value={settings.max_iterations || '10'}
                        onChange={e => setSettings({...settings, max_iterations: e.target.value})}
                      />
                      <p className="form-hint">How many consecutive tool calls the agent can make before pausing.</p>
                    </div>

                    <div className="form-group">
                      <label>Base URL (Optional)</label>
                      <input 
                        type="text"
                        placeholder="e.g. https://api.openai.com/v1"
                        value={settings.llm_base_url || ''}
                        onChange={e => setSettings({...settings, llm_base_url: e.target.value})}
                      />
                    </div>
                    
                    <div className="form-group">
                      <label>System Prompt (Optional)</label>
                      <textarea 
                        className="system-prompt-textarea"
                        placeholder="You are a helpful AI assistant..."
                        value={settings.system_prompt || ''}
                        onChange={e => setSettings({...settings, system_prompt: e.target.value})}
                        rows={4}
                      />
                      <p className="form-hint">Custom instructions that the agent should follow for every response.</p>
                    </div>
                  </div>
                )}

                {/* APP TAB */}
                {activeTab === 'app' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>Speech Language</label>
                      <select 
                        value={settings.speech_language || 'ru-RU'}
                        onChange={e => setSettings({...settings, speech_language: e.target.value})}
                      >
                        <option value="ru-RU">Русский (Russian)</option>
                        <option value="en-US">English (US)</option>
                        <option value="fr-FR">Français (French)</option>
                        <option value="de-DE">Deutsch (German)</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Voice Mode</label>
                      <div className="toggle-group">
                        <label className="toggle-label">
                          <input
                            type="checkbox"
                            checked={voiceAutoSend}
                            onChange={e => {
                              onVoiceAutoSendChange?.(e.target.checked);
                              setSettings({...settings, voice_auto_send: e.target.checked ? 'true' : 'false'});
                            }}
                          />
                          <span className="toggle-slider"></span>
                          <span className="toggle-text">
                            {voiceAutoSend ? 'Auto-send (hands-free)' : 'Manual review'}
                          </span>
                        </label>
                        <p className="form-hint">
                          {voiceAutoSend
                            ? 'Voice input is sent to the AI immediately after capture.'
                            : 'Voice input appears in the text field for review before sending.'}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {error && <div className="alert error">{error}</div>}
                {success && <div className="alert success">{success}</div>}

              </form>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>Close</button>
            <button form="settings-form" type="submit" className="btn-primary" disabled={saving}>
              <Save size={18} />
              {saving ? 'Saving...' : 'Save & Apply'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
