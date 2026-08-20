// lowercase casual comment for react ui root
import React, { useState, useEffect, useRef, useCallback, useMemo, memo } from 'react';
import { Zap, Pencil, Trash2, Mic, ArrowRight, StopCircle, Paperclip, Shield, X, Check, ChevronRight, ChevronDown, Code2, Square, AlertTriangle } from 'lucide-react';
import { useTranslation } from './i18n/index.ts';
import { Sidebar } from './components/Sidebar';
import { SettingsModal } from './components/SettingsModal';
import { VoicePanel } from './components/VoicePanel';
import { WorkspaceSelector } from './components/WorkspaceSelector';
import { CreateProjectModal } from './components/CreateProjectModal';
import { AgentDashboard } from './components/AgentDashboard';
import { ArtifactRenderer } from './components/ArtifactRenderer';
import './App.css';

interface Message {
  id: string;
  role: 'user' | 'bot' | 'system' | 'tool' | 'assistant';
  content: string;
}

interface QueuedMessage {
  id: string;
  text: string;
}

interface ToolBlockProps {
  msg: Message;
  t: (key: string, params?: any) => string;
}

// collapsible tool block for tool call outputs
const ToolBlock = memo(function ToolBlock({ msg, t }: ToolBlockProps) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className={`tool-block ${isOpen ? 'open' : ''}`}>
      <div className="tool-head" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Code2 size={14} />
        {t('chat.show_system_output')}
      </div>
      {isOpen && (
        <div className="tool-body">
          <ArtifactRenderer content={msg.content || ""} />
        </div>
      )}
    </div>
  );
});

// handy helper to render attachments cleanly
const renderUserContent = (content: string) => {
  const parts = content.split(/\[Attached File: (.*?)\]/g);
  if (parts.length === 1) return <ArtifactRenderer content={content} />;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {parts.map((part, i) => {
        if (i % 2 === 1) {
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(0,0,0,0.2)', padding: '8px 12px', borderRadius: '8px', border: '1px solid var(--border)', alignSelf: 'flex-start' }}>
              <div style={{ background: 'var(--accent)', color: 'white', borderRadius: '4px', padding: '4px', display: 'flex' }}><Paperclip size={14} /></div>
              <span style={{ fontSize: '12px', fontFamily: 'var(--mono)', color: 'var(--text-hi)' }}>{part.split(/[/\\]/).pop()}</span>
            </div>
          );
        } else if (part.trim()) {
          return <ArtifactRenderer key={i} content={part.trim()} />;
        }
        return null;
      })}
    </div>
  );
};

interface ChatMessageItemProps {
  msg: Message;
  t: (key: string, params?: any) => string;
}

// memoized message item prevents full chat tree thrashing on token stream
const ChatMessageItem = memo(function ChatMessageItem({ msg, t }: ChatMessageItemProps) {
  if (msg.role === 'tool') {
    return <ToolBlock msg={msg} t={t} />;
  }
  
  const isError = msg.content && (msg.content.startsWith('⚠️') || msg.content.includes('Error:') || msg.content.includes('ОШИБКА'));
  
  return (
    <div className={`msg ${msg.role === 'user' ? 'user' : ''}`}>
      <div className="avatar" style={isError ? { background: 'var(--red)', color: '#fff' } : undefined}>
        {isError ? (
          <AlertTriangle size={18} />
        ) : msg.role === 'user' ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg>
        )}
      </div>
      <div className="bubble">
        <div className="meta">
          <span className="who">{msg.role === 'user' ? 'You' : isError ? 'System' : 'Friday'}</span>
        </div>
        <div className="message-content" style={isError ? { color: 'var(--red)', background: 'rgba(255, 60, 60, 0.1)', padding: '12px', borderRadius: '8px', borderLeft: '3px solid var(--red)' } : undefined}>
          {msg.role === 'user' ? renderUserContent(msg.content || "") : <ArtifactRenderer content={isError ? msg.content.replace(/^⚠️\s*/, '') : (msg.content || "")} />}
        </div>
      </div>
    </div>
  );
});

// hidden commands constant for filtering
const HIDDEN_COMMANDS = ['/voice', '/clear', '/settings'];

function App() {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [permissionRequest, setPermissionRequest] = useState<string | null>(null);
  
  const [chats, setChats] = useState<Array<{id: string, title: string}>>([]);
  const [currentChatId, setCurrentChatId] = useState<string>('');
  const [currentWorkspace, setCurrentWorkspace] = useState<string>('');
  const [currentModel, setCurrentModel] = useState<string>('Default');
  const [currentProvider, setCurrentProvider] = useState<string>('provider');
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  
  const currentChatIdRef = useRef<string>('');
  const pendingChatIdRef = useRef<string | null>(null);

  useEffect(() => {
    currentChatIdRef.current = currentChatId;
  }, [currentChatId]);
  
  const [messageQueue, setMessageQueue] = useState<QueuedMessage[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, permissionRequest, scrollToBottom]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const [isListening, setIsListening] = useState(false);
  const [isTtsPlaying, setIsTtsPlaying] = useState(false);
  const [voiceAutoSend, setVoiceAutoSend] = useState(() => {
    return localStorage.getItem('friday_voice_auto_send') === 'true';
  });
  const [isVoicePanelOpen, setIsVoicePanelOpen] = useState(false);
  const [apiPort, setApiPort] = useState<number | null>(null);

  useEffect(() => {
    const fetchPort = async () => {
      try {
        const isTauri = '__TAURI_INTERNALS__' in window || '__TAURI__' in window || window.location.hostname === 'tauri.localhost';
        if (isTauri) {
          const { invoke } = await import('@tauri-apps/api/core');
          const port = await invoke('get_runtime_port');
          setApiPort(port as number);
        } else {
          setApiPort(8000);
        }
      } catch {
        setApiPort(8000);
      }
    };
    fetchPort();
  }, []);

  const applyTheme = useCallback((theme?: string, accentColor?: string) => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('theme-light');
    } else {
      root.classList.remove('theme-light');
    }
    if (accentColor) {
      root.style.setProperty('--accent-primary', accentColor);
    } else {
      root.style.removeProperty('--accent-primary');
    }
  }, []);

  useEffect(() => {
    if (apiPort === null) return;
    const isTauri = '__TAURI_INTERNALS__' in window || '__TAURI__' in window || window.location.hostname === 'tauri.localhost';
    const apiHost = isTauri ? `127.0.0.1:${apiPort}` : (window.location.host || '127.0.0.1:8000');
    fetch(`http://${apiHost}/api/settings`)
      .then(res => res.json())
      .then(data => {
        applyTheme(data.theme, data.accent_color);
        if (data.voice_auto_send !== undefined) {
          setVoiceAutoSend(data.voice_auto_send === 'true');
        }
        if (data.llm_model) setCurrentModel(data.llm_model);
        if (data.llm_provider) setCurrentProvider(data.llm_provider);
      })
      .catch(err => console.error("Failed to load initial settings", err));
  }, [apiPort, applyTheme]);

  useEffect(() => {
    if (apiPort === null) return;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let websocket: WebSocket | null = null;
    let isMounted = true;

    const connect = () => {
      const isTauri = '__TAURI_INTERNALS__' in window || '__TAURI__' in window || window.location.hostname === 'tauri.localhost';
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = isTauri ? `127.0.0.1:${apiPort}` : (window.location.host || '127.0.0.1:8000');
      websocket = new WebSocket(`${wsProtocol}//${wsHost}/ws/chat`);
      
      websocket.onopen = () => {
        if (!isMounted) return;
        setConnected(true);
        setWs(websocket);
        console.log('Connected to Friday API');
        websocket?.send(JSON.stringify({ type: 'get_chats' }));
        websocket?.send(JSON.stringify({ type: 'get_workspaces' }));
      };
      
      websocket.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'output') {
            setIsThinking(false);
            const content = data.content;
            if (content.includes('Initializing microphone') || content.includes('Listening...')) {
              setIsListening(true);
              return;
            }
            if (content.includes('Finished listening') || content.includes('Voice captured:')) {
              setIsListening(false);
              return;
            }
            let cleanContent = content;
            if (cleanContent.startsWith('\nFriday: ')) cleanContent = cleanContent.substring(9);
            else if (cleanContent.startsWith('Friday: ')) cleanContent = cleanContent.substring(8);

            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'bot') {
                return [...prev.slice(0, -1), { ...last, content: last.content + cleanContent }];
              } else {
                return [...prev, { id: Date.now().toString(), role: 'bot', content: cleanContent }];
              }
            });
          } else if (data.type === 'voice_result') {
            setIsListening(false);
            const transcribedText = data.text;
            const autoSend = localStorage.getItem('friday_voice_auto_send') !== 'false';
            
            if (autoSend && websocket && websocket.readyState === WebSocket.OPEN) {
              setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: `🎤 ${transcribedText}` }]);
              setIsThinking(true);
              websocket.send(JSON.stringify({ type: 'message', content: transcribedText }));
            } else {
              setInput(prev => prev ? prev + ' ' + transcribedText : transcribedText);
            }
          } else if (data.type === 'tts_state') {
            setIsTtsPlaying(data.playing);
          } else if (data.type === 'wake_word') {
            import('@tauri-apps/api/window').then(({ getCurrentWindow }) => {
              const win = getCurrentWindow();
              win.show();
              win.setFocus();
            }).catch(err => console.error("Tauri window API not available", err));
            setIsListening(true);
            setIsThinking(true);
            websocket?.send(JSON.stringify({ type: 'message', content: '/voice' }));
          } else if (data.type === 'voice_error') {
            setIsListening(false);
            setMessages(prev => [...prev, { id: Date.now().toString(), role: 'bot', content: t('chat.voice_error', { error: data.error }) }]);
          } else if (data.type === 'done') {
            setIsListening(false);
            if (data.command === '/voice') {
              const autoSend = localStorage.getItem('friday_voice_auto_send') !== 'false';
              if (!autoSend) setIsThinking(false);
            } else {
              setIsThinking(false);
            }
          } else if (data.type === 'chats_list') {
            setChats(data.chats || []);
          } else if (data.type === 'chat_history') {
            if (pendingChatIdRef.current === data.chat_id || currentChatIdRef.current === data.chat_id || currentChatIdRef.current === '') {
              setCurrentChatId(data.chat_id);
              currentChatIdRef.current = data.chat_id;
              setMessages(data.messages || []);
              if (pendingChatIdRef.current === data.chat_id) pendingChatIdRef.current = null;
            }
          } else if (data.type === 'workspace_set') {
            if (!data.chat_id || pendingChatIdRef.current === data.chat_id || currentChatIdRef.current === data.chat_id || currentChatIdRef.current === '') {
              setCurrentWorkspace(data.path);
            }
          } else if (data.type === 'permission_request') {
            setPermissionRequest(data.action);
          }
        } catch (e) {
          console.error('Failed to parse WS message', e);
        }
      };
      
      websocket.onclose = () => {
        if (!isMounted) return;
        setConnected(false);
        setIsThinking(false);
        setWs(null);
        reconnectTimeout = setTimeout(connect, 2000);
      };
      
      websocket.onerror = () => {
        setIsThinking(false);
        websocket?.close();
      };
    };

    connect();
    
    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      if (websocket) {
        websocket.onclose = null;
        websocket.close();
      }
    };
  }, [apiPort, t]);

  useEffect(() => {
    if (!isThinking && messageQueue.length > 0 && ws && connected && !permissionRequest) {
      const nextMsg = messageQueue[0];
      setMessageQueue(prev => prev.slice(1));
      
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: nextMsg.text };
      setMessages(prev => [...prev, userMsg]);
      setIsThinking(true);
      ws.send(JSON.stringify({ type: 'message', content: nextMsg.text }));
    }
  }, [isThinking, messageQueue, ws, connected, permissionRequest]);

  // dispatch actions over websocket
  const handleAction = useCallback((cmd: string, payload?: string) => {
    if (cmd === '/settings') {
      setIsSettingsOpen(true);
      return;
    }
    if (!ws || !connected) return;
    
    if (cmd === '/voice') setIsListening(true);

    if (cmd === 'new_chat') {
      const newId = Date.now().toString();
      pendingChatIdRef.current = newId;
      ws.send(JSON.stringify({ type: 'switch_chat', chat_id: newId }));
      ws.send(JSON.stringify({ type: 'get_chats' }));
      return;
    }
    if (cmd === 'switch_chat' && payload) {
      pendingChatIdRef.current = payload;
      ws.send(JSON.stringify({ type: 'switch_chat', chat_id: payload }));
      return;
    }
    if (cmd === 'set_workspace' && payload !== undefined) {
      ws.send(JSON.stringify({ type: 'set_workspace', path: payload }));
      return;
    }
    if (cmd === 'rename_chat' && payload) {
      ws.send(JSON.stringify({ type: 'rename_chat', payload }));
      return;
    }
    if (cmd === 'delete_chat' && payload) {
      ws.send(JSON.stringify({ type: 'delete_chat', chat_id: payload }));
      return;
    }
    
    if (!HIDDEN_COMMANDS.includes(cmd)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: cmd };
      setMessages(prev => [...prev, userMsg]);
    }
    setIsThinking(true);
    ws.send(JSON.stringify({ type: 'message', content: cmd }));
  }, [ws, connected]);

  const handlePermission = useCallback((approved: boolean) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'permission_response', approved }));
    }
    setPermissionRequest(null);
  }, [ws]);

  // send message or queue if assistant is busy
  const handleSubmit = useCallback((e?: React.FormEvent, forceInstant: boolean = false) => {
    if (e) e.preventDefault();
    if (!input.trim() || !ws || !connected) return;
    
    const text = input.trim();
    let finalContent = text;
    if (attachedFiles.length > 0) {
      const attachmentsString = attachedFiles.map(f => `[Attached File: ${f}]`).join('\n');
      finalContent = `${text}\n\n${attachmentsString}`.trim();
    }
    
    setInput('');
    setAttachedFiles([]);
    
    if ((isThinking || permissionRequest) && !forceInstant) {
      setMessageQueue(prev => [...prev, { id: Date.now().toString(), text: finalContent }]);
      return;
    }
    
    if (!HIDDEN_COMMANDS.includes(text)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: finalContent };
      setMessages(prev => [...prev, userMsg]);
    }
    
    setIsThinking(true);
    // send payload to websocket
    ws.send(JSON.stringify({ type: 'message', content: finalContent }));
  }, [input, attachedFiles, isThinking, permissionRequest, ws, connected]);
  
  // instant send right away to backend bypass queue
  const handleInstantSend = (msgId: string) => {
    // grab queued message by id
    const msg = messageQueue.find(m => m.id === msgId);
    if (!msg || !ws || !connected) return;
    
    // pop item from queue
    setMessageQueue(prev => prev.filter(m => m.id !== msgId));
    
    if (!HIDDEN_COMMANDS.includes(msg.text)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: msg.text };
      setMessages(prev => [...prev, userMsg]);
    }
    
    setIsThinking(true);
    // send instant message to ws
    ws.send(JSON.stringify({ type: 'message', content: msg.text }));
  };

  // pop from queue and put back in input
  const handleEditQueue = useCallback((msgId: string) => {
    const msg = messageQueue.find(m => m.id === msgId);
    if (!msg) return;
    setInput(msg.text);
    setMessageQueue(prev => prev.filter(m => m.id !== msgId));
  }, [messageQueue]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  // grab attached files from dialog or web file input
  const handleAttachFile = useCallback(async () => {
    try {
      if ((window as any).__TAURI_INTERNALS__) {
        const { open } = await import('@tauri-apps/plugin-dialog');
        const selected = await open({
          multiple: false,
        });
        if (selected) {
          const path = Array.isArray(selected) ? selected[0] : selected;
          setAttachedFiles(prev => [...prev, path]);
        }
      } else {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.onchange = (e: any) => {
          const file = e.target.files?.[0];
          if (file) {
            setAttachedFiles(prev => [...prev, file.name]);
          }
        };
        fileInput.click();
      }
    } catch (err) {
      console.error("Failed to open file dialog", err);
    }
  }, []);

  const handleClearWorkspace = useCallback(() => {
    handleAction('set_workspace', '');
  }, [handleAction]);

  const handleOpenCreateProject = useCallback(() => {
    setIsCreateProjectOpen(true);
  }, []);

  const handleCloseCreateProject = useCallback(() => {
    setIsCreateProjectOpen(false);
  }, []);

  const handleProjectCreated = useCallback((path: string) => {
    handleAction('set_workspace', path);
  }, [handleAction]);

  const handleProjectSkip = useCallback(() => {
    handleAction('set_workspace', '');
  }, [handleAction]);

  const handleOpenVoice = useCallback(() => {
    setIsVoicePanelOpen(true);
    handleAction('/voice');
  }, [handleAction]);

  const handleCloseVoice = useCallback(() => {
    setIsVoicePanelOpen(false);
    if (isListening && ws && connected) {
      ws.send(JSON.stringify({ type: 'stop_voice' }));
      setIsListening(false);
    }
  }, [isListening, ws, connected]);

  const handleCloseSettings = useCallback(() => {
    setIsSettingsOpen(false);
  }, []);

  const handleVoiceAutoSendChange = useCallback((val: boolean) => {
    setVoiceAutoSend(val);
    localStorage.setItem('friday_voice_auto_send', val.toString());
  }, []);

  const handleSettingsChanged = useCallback((newSettings: Record<string, string>) => {
    applyTheme(newSettings.theme, newSettings.accent_color);
    if (newSettings.llm_model) setCurrentModel(newSettings.llm_model);
    if (newSettings.llm_provider) setCurrentProvider(newSettings.llm_provider);
  }, [applyTheme]);

  const handleStopTts = useCallback(() => {
    if (ws && connected) {
      ws.send(JSON.stringify({ type: 'stop_tts' }));
      setIsTtsPlaying(false);
    }
  }, [ws, connected]);

  const handleStopGeneration = useCallback(() => {
    if (ws && connected) {
      ws.send(JSON.stringify({ type: 'stop_generation' }));
      setIsThinking(false);
    }
  }, [ws, connected]);


  const handleDeleteQueued = useCallback((msgId: string) => {
    setMessageQueue(prev => prev.filter(m => m.id !== msgId));
  }, []);

  const handleRemoveAttachment = useCallback((idx: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== idx));
  }, []);

  // filter out system msgs and empty content
  const visibleMessages = useMemo(() => {
    return messages.filter(m => m.role !== 'system' && m.content && m.content.trim().length > 0);
  }, [messages]);

  const slashCommands = useMemo(() => [
    { cmd: '/clear', desc: t('commands.clear_desc') || 'Clear current chat history', icon: <Trash2 size={16} /> },
    { cmd: '/goal', desc: t('commands.goal_desc') || 'Start a long-running autonomous goal', icon: <Zap size={16} /> },
    { cmd: '/schedule', desc: t('commands.schedule_desc') || 'Schedule a background task', icon: <Check size={16} /> }
  ], [t]);

  const showSlashMenu = input.startsWith('/') && !input.includes(' ');
  const filteredCommands = showSlashMenu 
    ? slashCommands.filter(c => c.cmd.toLowerCase().startsWith(input.toLowerCase()))
    : [];

  const handleCommandSelect = useCallback((cmd: string) => {
    setInput(cmd + ' ');
    textareaRef.current?.focus();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files).map((f: any) => f.path || f.name);
      setAttachedFiles(prev => [...prev, ...newFiles]);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  return (
    <div className="app" onDrop={handleDrop} onDragOver={handleDragOver}>
      <Sidebar 
        onAction={handleAction} 
        connected={connected} 
        chats={chats}
        currentChatId={currentChatId}
      />
      
      <main className="workspace">
        <header className="topbar">
          <WorkspaceSelector 
            currentWorkspace={currentWorkspace}
            onSelectNew={handleOpenCreateProject}
            onClearWorkspace={handleClearWorkspace}
          />
          <div className="model-pill">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>
            {currentModel} <span className="prov">· {currentProvider}</span>
          </div>
          <div className="top-actions">
            <button className="icon-btn" title="Voice input" onClick={handleOpenVoice}>
              <Mic size={17} />
            </button>
          </div>
        </header>

        <div className="chat">
          {messages.length === 0 ? (
            <div className="hero">
              <h1>{t('chat.empty_connected')}</h1>
              {!connected && <p className="sub">{t('chat.empty_connecting')}</p>}
              <div className="chips">
                <div className="chip" onClick={() => { setInput("Open browser"); textareaRef.current?.focus(); }}>
                  Open browser
                </div>
                <div className="chip" onClick={() => { setInput("Minimize window"); textareaRef.current?.focus(); }}>
                  Minimize window
                </div>
              </div>
            </div>
          ) : (
            <>
              {visibleMessages.map((msg, idx) => (
                <ChatMessageItem key={msg.id || idx} msg={msg} t={t} />
              ))}
              
              <AgentDashboard isThinking={isThinking} />

              {/* Inline Permission Component */}
              {permissionRequest && (
                <div className="permission">
                  <div className="p-head">
                    <div className="shield">
                      <Shield size={16} />
                    </div>
                    <div>
                      <div className="p-title">{t('permission.title')}</div>
                      <div className="p-sub">{t('permission.description')}</div>
                    </div>
                  </div>
                  <div className="cmd">{permissionRequest}</div>
                  <div className="p-actions">
                    <button className="btn btn-approve" onClick={() => handlePermission(true)}>
                      <Check size={14} />
                      {t('permission.allow')}
                    </button>
                    <button className="btn btn-deny" onClick={() => handlePermission(false)}>
                      <X size={14} />
                      {t('permission.deny')}
                    </button>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Floating Queue Widget */}
        {messageQueue.length > 0 && (
          <div className="queue">
            <div className="queue-head">
              <span><b>Queue</b> · {messageQueue.length} pending</span>
              {isThinking && <span style={{ color: 'var(--accent)' }}>1 running</span>}
            </div>
            {messageQueue.map(msg => (
              <div key={msg.id} className="q-item">
                <div className="qt">{msg.text}</div>
                <div className="qmeta">
                  <span>queued</span>
                </div>
                <div className="q-actions">
                  <button onClick={() => handleInstantSend(msg.id)} title={t('chat.send_immediately')} className="q-btn instant">
                    <Zap size={12} /> Instant
                  </button>
                  <button onClick={() => handleEditQueue(msg.id)} title={t('common.edit')} className="q-btn">
                    <Pencil size={12} />
                  </button>
                  <button onClick={() => handleDeleteQueued(msg.id)} title={t('common.delete')} className="q-btn">
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="composer">
          <div className="composer-box">
            {attachedFiles.length > 0 && (
              <div className="attachments-bar" style={{ display: 'flex', gap: '8px', padding: '8px 14px', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
                {attachedFiles.map((file, idx) => (
                  <div key={idx} className="attachment-chip" style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-hover)', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}>
                    <Paperclip size={12} />
                    <span className="truncate" style={{ maxWidth: '150px' }}>{file.split(/[/\\]/).pop()}</span>
                    <button onClick={() => handleRemoveAttachment(idx)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-low)', padding: 0, display: 'flex', alignItems: 'center' }}><X size={12} /></button>
                  </div>
                ))}
              </div>
            )}
            {showSlashMenu && filteredCommands.length > 0 && (
              <div className="slash-menu" style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                width: '100%',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                marginBottom: '8px',
                overflow: 'hidden',
                zIndex: 10,
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
              }}>
                {filteredCommands.map((c, i) => (
                  <div 
                    key={c.cmd} 
                    className="slash-item"
                    onClick={() => handleCommandSelect(c.cmd)}
                    style={{
                      padding: '10px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      cursor: 'pointer',
                      borderBottom: i < filteredCommands.length - 1 ? '1px solid var(--border)' : 'none',
                    }}
                  >
                    <div style={{ color: 'var(--accent)' }}>{c.icon}</div>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '14px' }}>{c.cmd}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-low)' }}>{c.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={connected ? (isThinking ? t('chat.placeholder_thinking') : t('chat.placeholder_idle')) : t('chat.placeholder_offline')}
              disabled={!connected}
              rows={1}
            />
            <div className="composer-foot">
              <div className="tools">
                <button type="button" className="tool-btn" title="Attach" onClick={handleAttachFile}>
                  <Paperclip size={18} />
                </button>
                <button 
                  type="button" 
                  className={`tool-btn ${isListening ? 'rec' : ''}`}
                  onClick={handleOpenVoice}
                  title={t('chat.start_voice')}
                >
                  <Mic size={18} />
                </button>
                {isTtsPlaying && (
                  <button 
                    type="button" 
                    className="tool-btn"
                    onClick={handleStopTts}
                    title={t('chat.stop_tts')}
                    style={{ color: 'var(--red)' }}
                  >
                    <StopCircle size={18} />
                  </button>
                )}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                {isThinking && (
                  <button 
                    className="send-btn" 
                    onClick={handleStopGeneration}
                    style={{ background: 'var(--red)', color: 'white' }}
                  >
                    <Square size={14} fill="currentColor" />
                    Stop
                  </button>
                )}
                <button 
                  className="send-btn" 
                  onClick={(e) => handleSubmit(e)}
                  disabled={!connected || (!input.trim() && !isListening)}
                >
                  {isThinking ? t('chat.queue_btn') : 'Send'}
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
          <div className="hint"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> to send &nbsp;·&nbsp; <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Space</kbd> voice</div>
        </div>
      </main>

      <VoicePanel 
        isOpen={isVoicePanelOpen}
        onClose={handleCloseVoice}
        isListening={isListening} 
        connected={connected} 
      />

      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={handleCloseSettings}
        voiceAutoSend={voiceAutoSend}
        apiPort={apiPort}
        onVoiceAutoSendChange={handleVoiceAutoSendChange}
        onSettingsChanged={handleSettingsChanged}
      />
      
      <CreateProjectModal 
        isOpen={isCreateProjectOpen}
        onClose={handleCloseCreateProject}
        onProjectCreated={handleProjectCreated}
        onSkip={handleProjectSkip}
      />
    </div>
  );
}

export default App;
