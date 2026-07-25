import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import './SettingsModal.css';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
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

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
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
      setSuccess('Settings saved and applied successfully!');
      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Error saving settings');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel">
        <div className="modal-header">
          <h2>Configuration</h2>
          <button className="icon-btn" onClick={onClose}><X size={24} /></button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="loading-state">Loading settings...</div>
          ) : (
            <form onSubmit={handleSave} className="settings-form">
              <div className="form-group">
                <label>Provider</label>
                <select 
                  value={settings.llm_provider || 'openai'}
                  onChange={e => setSettings({...settings, llm_provider: e.target.value})}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
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
                <label>Base URL (Optional)</label>
                <input 
                  type="text"
                  placeholder="e.g. https://api.openai.com/v1"
                  value={settings.llm_base_url || ''}
                  onChange={e => setSettings({...settings, llm_base_url: e.target.value})}
                />
              </div>

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

              {error && <div className="alert error">{error}</div>}
              {success && <div className="alert success">{success}</div>}

              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  <Save size={18} />
                  {saving ? 'Saving...' : 'Save & Apply'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
