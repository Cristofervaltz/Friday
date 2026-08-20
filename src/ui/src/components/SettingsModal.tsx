import React, { useState, useEffect, useCallback } from 'react';
import { X, Save, Palette, Bot, Monitor, Shield, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { useTranslation, type Language } from '../i18n/index.ts';
import './SettingsModal.css';

// props for settings modal component
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  voiceAutoSend?: boolean;
  onVoiceAutoSendChange?: (val: boolean) => void;
  onSettingsChanged?: (settings: Record<string, string>) => void;
  apiPort?: number | null;
}

type TabId = 'appearance' | 'agent' | 'security' | 'app';

// settings modal wrapped in memo to prevent heavy form tree re-evaluation
export const SettingsModal = React.memo(function SettingsModal({ isOpen, onClose, voiceAutoSend = true, onVoiceAutoSendChange, onSettingsChanged, apiPort }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>('appearance');
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // hook translation helper and language selector
  const { t, language, setLanguage } = useTranslation();

  // load settings from fastapi backend
  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const port = apiPort || 8000;
      const isTauri = '__TAURI_INTERNALS__' in window || '__TAURI__' in window || window.location.hostname === 'tauri.localhost';
      const apiHost = isTauri ? `127.0.0.1:${port}` : (window.location.host || '127.0.0.1:8000');
      const response = await fetch(`http://${apiHost}/api/settings`);
      if (!response.ok) throw new Error(t('settings.error_load'));
      const data = await response.json();
      setSettings(data);
    } catch (err: any) {
      setError(err.message || t('settings.error_loading'));
    } finally {
      setLoading(false);
    }
  }, [apiPort, t]);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen, loadSettings]);

  // persist settings wrapped in useCallback
  const handleSave = useCallback(async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const port = apiPort || 8000;
      const isTauri = '__TAURI_INTERNALS__' in window || '__TAURI__' in window || window.location.hostname === 'tauri.localhost';
      const apiHost = isTauri ? `127.0.0.1:${port}` : (window.location.host || '127.0.0.1:8000');
      const response = await fetch(`http://${apiHost}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (!response.ok) throw new Error(t('settings.error_save'));
      setSuccess(t('settings.save_success'));
      
      if (onSettingsChanged) {
        onSettingsChanged(settings);
      }
      
      setTimeout(() => {
        setSuccess(null);
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || t('settings.error_saving'));
    } finally {
      setSaving(false);
    }
  }, [apiPort, settings, t, onSettingsChanged, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="settings-modal-container glass-panel">
        <div className="settings-sidebar">
          <div className="settings-header-title">{t('settings.title')}</div>
          <div className="settings-nav">
            <button 
              className={`nav-item ${activeTab === 'appearance' ? 'active' : ''}`}
              onClick={() => setActiveTab('appearance')}
            >
              <Palette size={16} /> {t('settings.tab_appearance')}
            </button>
            <button 
              className={`nav-item ${activeTab === 'agent' ? 'active' : ''}`}
              onClick={() => setActiveTab('agent')}
            >
              <Bot size={16} /> {t('settings.tab_agent')}
            </button>
            <button 
              className={`nav-item ${activeTab === 'security' ? 'active' : ''}`}
              onClick={() => setActiveTab('security')}
            >
              <Shield size={16} /> {t('settings.tab_security')}
            </button>
            <button 
              className={`nav-item ${activeTab === 'app' ? 'active' : ''}`}
              onClick={() => setActiveTab('app')}
            >
              <Monitor size={16} /> {t('settings.tab_app')}
            </button>
          </div>
        </div>

        <div className="settings-content-wrapper">
          <div className="modal-header">
            <h2>{t('settings.tab_title', { tab: t(`settings.tab_${activeTab}`) })}</h2>
            <button className="icon-btn" onClick={onClose}><X size={24} /></button>
          </div>

          <div className="modal-body">
            {loading ? (
              <div className="loading-state">{t('settings.loading')}</div>
            ) : (
              <form id="settings-form" onSubmit={handleSave} className="settings-form">
                
                {/* APPEARANCE TAB */}
                {activeTab === 'appearance' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>{t('settings.theme')}</label>
                      <select 
                        value={settings.theme || 'dark'}
                        onChange={e => setSettings({...settings, theme: e.target.value})}
                      >
                        <option value="dark">{t('settings.theme_dark')}</option>
                        <option value="light">{t('settings.theme_light')}</option>
                      </select>
                    </div>
                    
                    <div className="form-group">
                      <label>{t('settings.accent_color')}</label>
                      <div className="color-picker-group">
                        <input 
                          type="color" 
                          value={settings.accent_color || '#6366F1'}
                          onChange={e => setSettings({...settings, accent_color: e.target.value})}
                          className="color-picker-input"
                        />
                        <span className="color-hex">{settings.accent_color || '#6366F1'}</span>
                      </div>
                      <p className="form-hint">{t('settings.accent_color_hint')}</p>
                    </div>

                    {/* language switcher dropdown */}
                    <div className="form-group">
                      <label>{t('settings.language')}</label>
                      <select 
                        value={language}
                        onChange={e => setLanguage(e.target.value as Language)}
                      >
                        <option value="en">{t('settings.lang_en')}</option>
                        <option value="ru">{t('settings.lang_ru')}</option>
                      </select>
                      <p className="form-hint">{t('settings.language_hint')}</p>
                    </div>
                  </div>
                )}

                {/* AGENT TAB */}
                {activeTab === 'agent' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>OpenAI API Key</label>
                      <input 
                        type="password"
                        placeholder="sk-proj-..."
                        value={settings.openai_api_key || settings.llm_api_key || ''}
                        onChange={e => setSettings({...settings, openai_api_key: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>Anthropic API Key</label>
                      <input 
                        type="password"
                        placeholder="sk-ant-..."
                        value={settings.anthropic_api_key || ''}
                        onChange={e => setSettings({...settings, anthropic_api_key: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>Gemini API Key</label>
                      <input 
                        type="password"
                        placeholder="AIza..."
                        value={settings.gemini_api_key || ''}
                        onChange={e => setSettings({...settings, gemini_api_key: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>OpenRouter API Key</label>
                      <input 
                        type="password"
                        placeholder="sk-or-v1-..."
                        value={settings.openrouter_api_key || ''}
                        onChange={e => setSettings({...settings, openrouter_api_key: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>Ollama Base URL</label>
                      <input 
                        type="text"
                        placeholder="http://localhost:11434"
                        value={settings.ollama_base_url || 'http://localhost:11434'}
                        onChange={e => setSettings({...settings, ollama_base_url: e.target.value})}
                      />
                    </div>

                    <div className="form-group">
                      <label>Custom Base URL (OpenAI Compatible)</label>
                      <input 
                        type="text"
                        placeholder="e.g. https://api.openai.com/v1"
                        value={settings.openai_base_url || settings.llm_base_url || ''}
                        onChange={e => setSettings({...settings, openai_base_url: e.target.value})}
                      />
                    </div>

                    
                    <div className="form-group">
                      <label>{t('settings.max_iterations')}</label>
                      <input 
                        type="number"
                        min="1"
                        max="100"
                        placeholder="10"
                        value={settings.max_iterations || '10'}
                        onChange={e => setSettings({...settings, max_iterations: e.target.value})}
                      />
                      <p className="form-hint">{t('settings.max_iterations_hint')}</p>
                    </div>

                    <div className="form-group">
                      <label>{t('settings.system_prompt')}</label>
                      <textarea 
                        className="system-prompt-textarea"
                        placeholder={t('settings.system_prompt_placeholder')}
                        value={settings.system_prompt || ''}
                        onChange={e => setSettings({...settings, system_prompt: e.target.value})}
                        rows={4}
                      />
                      <p className="form-hint">{t('settings.system_prompt_hint')}</p>
                    </div>
                  </div>
                )}

                {/* SECURITY TAB */}
                {activeTab === 'security' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>{t('settings.permission_mode')}</label>
                      <select 
                        value={settings.permission_mode || 'default'}
                        onChange={e => setSettings({...settings, permission_mode: e.target.value})}
                      >
                        <option value="default">{t('settings.mode_default')}</option>
                        <option value="turbo">{t('settings.mode_turbo')}</option>
                        <option value="custom">{t('settings.mode_custom')}</option>
                      </select>
                      <p className="form-hint">
                        {settings.permission_mode === 'turbo' 
                          ? <><AlertTriangle size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }}/> {t('settings.turbo_hint')}</>
                          : settings.permission_mode === 'custom'
                          ? t('settings.custom_hint')
                          : t('settings.default_hint')}
                      </p>
                    </div>

                    {settings.permission_mode === 'turbo' && (
                      <div className="settings-warning" style={{ color: '#ff5252', fontSize: '0.85em', padding: '10px', background: 'rgba(255,82,82,0.1)', borderRadius: '8px', border: '1px solid rgba(255,82,82,0.3)', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                        <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                        <div>
                          <strong>{t('settings.warning_label')}:</strong> {t('settings.turbo_warning')}
                        </div>
                      </div>
                    )}

                    {settings.permission_mode === 'custom' && (
                      <>
                        <div className="form-group">
                          <label><CheckCircle size={14} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px', color: '#10b981' }}/> {t('settings.auto_allow')}</label>
                          <textarea
                            className="system-prompt-textarea"
                            placeholder="git, npm, python, pip, ls, dir, cd, echo"
                            value={settings.perm_allow || ''}
                            onChange={e => setSettings({...settings, perm_allow: e.target.value})}
                            rows={2}
                          />
                          <p className="form-hint">{t('settings.auto_allow_hint')}</p>
                        </div>

                        <div className="form-group">
                          <label><XCircle size={14} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px', color: '#ef4444' }}/> {t('settings.always_deny')}</label>
                          <textarea
                            className="system-prompt-textarea"
                            placeholder="rm -rf /, format, shutdown, del /f"
                            value={settings.perm_deny || ''}
                            onChange={e => setSettings({...settings, perm_deny: e.target.value})}
                            rows={2}
                          />
                          <p className="form-hint">{t('settings.always_deny_hint')}</p>
                        </div>

                        <div className="form-group">
                          <label><HelpCircle size={14} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px', color: '#eab308' }}/> {t('settings.ask_permission')}</label>
                          <textarea
                            className="system-prompt-textarea"
                            placeholder="rm, del, move, ren"
                            value={settings.perm_ask || ''}
                            onChange={e => setSettings({...settings, perm_ask: e.target.value})}
                            rows={2}
                          />
                          <p className="form-hint">{t('settings.ask_permission_hint')}</p>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* APP TAB */}
                {activeTab === 'app' && (
                  <div className="tab-content">
                    <div className="form-group">
                      <label>{t('settings.speech_language')}</label>
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
                      <label>{t('settings.enable_tts')}</label>
                      <div className="toggle-group">
                        <label className="toggle-label">
                          <input
                            type="checkbox"
                            checked={settings.tts_enabled !== 'false'}
                            onChange={e => setSettings({...settings, tts_enabled: e.target.checked ? 'true' : 'false'})}
                          />
                          <span className="toggle-slider"></span>
                          <span className="toggle-text">
                            {settings.tts_enabled !== 'false' ? t('common.enabled') : t('common.disabled')}
                          </span>
                        </label>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>{t('settings.tts_voice')}</label>
                      <select 
                        value={settings.tts_voice || 'ru-RU-SvetlanaNeural'}
                        onChange={e => setSettings({...settings, tts_voice: e.target.value})}
                      >
                        <option value="ru-RU-SvetlanaNeural">ru-RU-SvetlanaNeural (Female)</option>
                        <option value="ru-RU-DmitryNeural">ru-RU-DmitryNeural (Male)</option>
                        <option value="en-US-AriaNeural">en-US-AriaNeural (Female)</option>
                        <option value="en-US-GuyNeural">en-US-GuyNeural (Male)</option>
                        <option value="en-US-JennyNeural">en-US-JennyNeural (Female)</option>
                      </select>
                      <p className="form-hint">{t('settings.tts_voice_hint')}</p>
                    </div>

                    <div className="form-group">
                      <label>{t('settings.voice_mode')}</label>
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
                            {voiceAutoSend ? t('settings.voice_mode_auto') : t('settings.voice_mode_manual')}
                          </span>
                        </label>
                        <p className="form-hint">
                          {voiceAutoSend
                            ? t('settings.voice_mode_auto_hint')
                            : t('settings.voice_mode_manual_hint')}
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
            <button type="button" className="btn-secondary" onClick={onClose}>{t('common.close')}</button>
            <button form="settings-form" type="submit" className="btn-primary" disabled={saving}>
              <Save size={18} />
              {saving ? t('common.saving') : t('settings.save_apply')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});

