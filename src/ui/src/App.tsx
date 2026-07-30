import { useState, useEffect, useRef } from 'react';
import { Zap, Pencil, Trash2, Mic, ArrowRight, StopCircle } from 'lucide-react';
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

function App() {
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
  
  const currentChatIdRef = useRef<string>('');
  const pendingChatIdRef = useRef<string | null>(null);

  useEffect(() => {
    currentChatIdRef.current = currentChatId;
  }, [currentChatId]);
  
  interface QueuedMessage {
    id: string;
    text: string;
  }
  const [messageQueue, setMessageQueue] = useState<QueuedMessage[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const [isListening, setIsListening] = useState(false);
  const [isTtsPlaying, setIsTtsPlaying] = useState(false);
  const [voiceAutoSend, setVoiceAutoSend] = useState(() => {
    return localStorage.getItem('friday_voice_auto_send') === 'true';
  });
  const [isVoicePanelOpen, setIsVoicePanelOpen] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/settings')
      .then(res => res.json())
      .then(data => {
        applyTheme(data.theme, data.accent_color);
        if (data.voice_auto_send !== undefined) {
          setVoiceAutoSend(data.voice_auto_send === 'true');
        }
      })
      .catch(err => console.error("Failed to load initial settings", err));
  }, []);

  const applyTheme = (theme?: string, accentColor?: string) => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('theme-light');
    } else {
      root.classList.remove('theme-light');
    }
    
    if (accentColor) {
      root.style.setProperty('--accent-primary', accentColor);
      // We can optionally generate a hover color or just let it be slightly transparent, 
      // but for now setting primary is good enough for custom accent.
    } else {
      root.style.removeProperty('--accent-primary');
    }
  };

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let websocket: WebSocket | null = null;
    let isMounted = true;

    const connect = () => {
      websocket = new WebSocket('ws://127.0.0.1:8000/ws/chat');
      
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
              return; // Don't show these as chat messages
            }
            if (content.includes('Finished listening') || content.includes('Voice captured:')) {
              setIsListening(false);
              return; // Don't show these either — voice_result will follow
            }
            let cleanContent = content;
            if (cleanContent.startsWith('\nFriday: ')) {
              cleanContent = cleanContent.substring(9);
            } else if (cleanContent.startsWith('Friday: ')) {
              cleanContent = cleanContent.substring(8);
            }

            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'bot') {
                // If it's a new message that started with \nFriday:, the first chunk was cleaned.
                // Subsequent chunks don't have it at the start.
                return [
                  ...prev.slice(0, -1), 
                  { ...last, content: last.content + cleanContent }
                ];
              } else {
                return [...prev, { id: Date.now().toString(), role: 'bot', content: cleanContent }];
              }
            });
          } else if (data.type === 'voice_result') {
            setIsListening(false);
            const transcribedText = data.text;
            
            // Check current setting from localStorage (closure-safe)
            const autoSend = localStorage.getItem('friday_voice_auto_send') !== 'false';
            
            if (autoSend && websocket && websocket.readyState === WebSocket.OPEN) {
              // Auto-send: show as user message and send to backend
              setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'user',
                content: `🎤 ${transcribedText}`
              }]);
              setIsThinking(true);
              websocket.send(JSON.stringify({ type: 'message', content: transcribedText }));
            } else {
              // Manual mode: insert into input field for review
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
            
            // Trigger voice recording
            setIsListening(true);
            setIsThinking(true);
            websocket?.send(JSON.stringify({ type: 'message', content: '/voice' }));
          } else if (data.type === 'voice_error') {
            setIsListening(false);
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              role: 'bot',
              content: `🎤 Voice error: ${data.error}`
            }]);
          } else if (data.type === 'done') {
            setIsListening(false);
            if (data.command === '/voice') {
              const autoSend = localStorage.getItem('friday_voice_auto_send') !== 'false';
              if (!autoSend) {
                setIsThinking(false);
              }
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
              if (pendingChatIdRef.current === data.chat_id) {
                pendingChatIdRef.current = null;
              }
            }
          } else if (data.type === 'workspace_set') {
            console.log("Received workspace_set:", data, "currentChatId:", currentChatIdRef.current, "pendingChatId:", pendingChatIdRef.current);
            if (!data.chat_id || pendingChatIdRef.current === data.chat_id || currentChatIdRef.current === data.chat_id || currentChatIdRef.current === '') {
              console.log("Setting workspace to:", data.path);
              setCurrentWorkspace(data.path);
            } else {
              console.log("Ignoring workspace_set because chat_id mismatch");
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
        console.log('Disconnected from Friday API. Reconnecting in 2s...');
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
        websocket.onclose = null; // prevent reconnect on unmount
        websocket.close();
      }
    };
  }, []);

  // Process queue automatically when done thinking
  useEffect(() => {
    if (!isThinking && messageQueue.length > 0 && ws && connected) {
      const nextMsg = messageQueue[0];
      setMessageQueue(prev => prev.slice(1));
      
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: nextMsg.text };
      setMessages(prev => [...prev, userMsg]);
      setIsThinking(true);
      ws.send(JSON.stringify({ type: 'message', content: nextMsg.text }));
    }
  }, [isThinking, messageQueue, ws, connected]);

  const HIDDEN_COMMANDS = ['/voice', '/clear', '/settings'];

  const handleAction = (cmd: string, payload?: string) => {
    if (cmd === '/settings') {
      setIsSettingsOpen(true);
      return;
    }
    if (!ws || !connected) return;
    
    if (cmd === '/voice') {
      setIsListening(true);
    }

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
  };

  const handlePermission = (approved: boolean) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'permission_response', approved }));
    }
    setPermissionRequest(null);
  };

  const handleSubmit = (e?: React.FormEvent, forceInstant: boolean = false) => {
    if (e) e.preventDefault();
    if (!input.trim() || !ws || !connected) return;
    
    const text = input.trim();
    setInput('');
    
    if (isThinking && !forceInstant) {
      setMessageQueue(prev => [...prev, { id: Date.now().toString(), text }]);
      return;
    }
    
    // Add user message unless it's a hidden command
    if (!HIDDEN_COMMANDS.includes(text)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
      setMessages(prev => [...prev, userMsg]);
    }
    
    // Send to server
    setIsThinking(true);
    ws.send(JSON.stringify({ type: 'message', content: text }));
  };
  
  const handleInstantSend = (msgId: string) => {
    const msg = messageQueue.find(m => m.id === msgId);
    if (!msg || !ws || !connected) return;
    
    // Remove from current position
    setMessageQueue(prev => prev.filter(m => m.id !== msgId));
    
    if (isThinking) {
      // Put at the very front of the queue to execute next
      setMessageQueue(prev => [msg, ...prev]);
      return;
    }

    if (!HIDDEN_COMMANDS.includes(msg.text)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: msg.text };
      setMessages(prev => [...prev, userMsg]);
    }
    setIsThinking(true);
    ws.send(JSON.stringify({ type: 'message', content: msg.text }));
  };

  const handleEditQueue = (msgId: string) => {
    const msg = messageQueue.find(m => m.id === msgId);
    if (!msg) return;
    setInput(msg.text);
    setMessageQueue(prev => prev.filter(m => m.id !== msgId));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="app-container">
      <Sidebar 
        onAction={handleAction} 
        connected={connected} 
        chats={chats}
        currentChatId={currentChatId}
      />
      
      {/* Chat Panel */}
      <section className="chat-panel glass-panel">
        <header className="panel-header">
          <h2>
            <div className={`status-indicator ${connected ? 'connected' : ''}`} />
            Friday AI
          </h2>
        </header>
        
        <div className="message-list">
          {messages.length === 0 ? (
            <div className="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 16v-4"></path>
                <path d="M12 8h.01"></path>
              </svg>
              <p>{connected ? "How can I help you today?" : "Starting background AI engine... (takes a few seconds)"}</p>
            </div>
          ) : (
            <>
              {messages.filter(m => m.role !== 'system' && m.content && m.content.trim().length > 0).map((msg, idx) => {
                if (msg.role === 'tool') {
                  return (
                    <div key={idx} className="message-wrapper tool-output">
                      <details className="tool-details">
                        <summary>🛠️ Показать вывод системы</summary>
                        <div className="tool-content">
                          <ArtifactRenderer content={msg.content || ""} />
                        </div>
                      </details>
                    </div>
                  );
                }
                return (
                  <div key={idx} className={`message-wrapper ${msg.role === 'assistant' ? 'bot' : msg.role}`}>
                    <div className="message-content">
                      <ArtifactRenderer content={msg.content || ""} />
                    </div>
                  </div>
                );
              })}
              
              <AgentDashboard isThinking={isThinking} />

              <div ref={messagesEndRef} />
            </>
          )}
        </div>
        
        {messageQueue.length > 0 && (
          <div className="queue-container">
            <div className="queue-header">В очереди ({messageQueue.length})</div>
            {messageQueue.map(msg => (
              <div key={msg.id} className="queue-item">
                <span className="queue-text truncate">{msg.text}</span>
                <div className="queue-actions">
                  <button onClick={() => handleInstantSend(msg.id)} title="Send Immediately" className="instant-btn"><Zap size={14} /></button>
                  <button onClick={() => handleEditQueue(msg.id)} title="Edit" className="edit-btn"><Pencil size={14} /></button>
                  <button onClick={() => setMessageQueue(prev => prev.filter(m => m.id !== msg.id))} title="Delete" className="del-btn"><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="input-area">
          <WorkspaceSelector 
            currentWorkspace={currentWorkspace}
            onSelectNew={() => setIsCreateProjectOpen(true)}
            onClearWorkspace={() => handleAction('set_workspace', '')}
          />
          <form className="input-form" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={connected ? (isThinking ? "Add task to queue... (Shift+Enter for newline)" : "Ask Friday to run a task... (Shift+Enter for newline)") : "Connecting to engine..."}
              disabled={!connected}
              rows={1}
            />
            {isThinking && input.trim() && (
              <button type="button" onClick={(e) => handleSubmit(e, true)} title="Send Immediately" className="instant-send-btn">
                <Zap size={20} />
              </button>
            )}
            <button 
              type="button" 
              className="inline-mic-btn"
              onClick={() => {
                setIsVoicePanelOpen(true);
                handleAction('/voice');
              }}
              title="Start Voice Input"
            >
              <Mic size={20} />
            </button>
            {isTtsPlaying && (
              <button 
                type="button" 
                className="inline-mic-btn"
                onClick={() => {
                  if (ws && connected) {
                    ws.send(JSON.stringify({ type: 'stop_tts' }));
                    setIsTtsPlaying(false);
                  }
                }}
                title="Stop TTS Audio"
                style={{ color: '#ef4444' }}
              >
                <StopCircle size={20} />
              </button>
            )}
            <button type="submit" className="send-btn" disabled={!connected || (!input.trim() && !isListening)}>
              {isThinking ? 'Queue' : <ArrowRight size={20} />}
            </button>
          </form>
        </div>
      </section>

      <VoicePanel 
        isOpen={isVoicePanelOpen}
        onClose={() => setIsVoicePanelOpen(false)}
        isListening={isListening} 
        connected={connected} 
      />

      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)}
        voiceAutoSend={voiceAutoSend}
        onVoiceAutoSendChange={(val: boolean) => {
          setVoiceAutoSend(val);
          localStorage.setItem('friday_voice_auto_send', val.toString());
        }}
        onSettingsChanged={(newSettings) => {
          applyTheme(newSettings.theme, newSettings.accent_color);
        }}
      />
      <CreateProjectModal 
        isOpen={isCreateProjectOpen}
        onClose={() => setIsCreateProjectOpen(false)}
        onProjectCreated={(path) => handleAction('set_workspace', path)}
        onSkip={() => handleAction('set_workspace', '')}
      />

      {permissionRequest && (
        <div className="modal-overlay">
          <div className="modal-content permission-modal">
            <h2>⚠️ Permission Request</h2>
            <p>Friday wants to execute the following command:</p>
            <pre className="command-preview">{permissionRequest}</pre>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => handlePermission(false)}>Deny</button>
              <button className="btn-primary danger" onClick={() => handlePermission(true)}>Allow</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
