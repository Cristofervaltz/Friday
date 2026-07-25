import { useState, useEffect, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import './App.css';

interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  
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
      };
      
      websocket.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'output') {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last && last.role === 'bot') {
                return [
                  ...prev.slice(0, -1), 
                  { ...last, content: last.content + data.content }
                ];
              } else {
                return [...prev, { id: Date.now().toString(), role: 'bot', content: data.content }];
              }
            });
          }
        } catch (e) {
          console.error('Failed to parse WS message', e);
        }
      };
      
      websocket.onclose = () => {
        if (!isMounted) return;
        setConnected(false);
        setWs(null);
        console.log('Disconnected from Friday API. Reconnecting in 2s...');
        reconnectTimeout = setTimeout(connect, 2000);
      };

      websocket.onerror = () => {
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

  const handleAction = (cmd: string) => {
    if (!ws || !connected) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: cmd };
    setMessages(prev => [...prev, userMsg]);
    ws.send(JSON.stringify({ type: 'message', content: cmd }));
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || !ws || !connected) return;
    
    // Add user message
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    
    // Send to server
    ws.send(JSON.stringify({ type: 'message', content: input }));
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="app-container">
      <Sidebar onAction={handleAction} connected={connected} />
      
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
            messages.map(msg => (
              <div key={msg.id} className={`message ${msg.role}`}>
                {msg.role === 'bot' ? (
                  <pre>{msg.content}</pre>
                ) : (
                  msg.content
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <div className="input-area">
          <form className="input-form" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={connected ? "Ask Friday to run a task... (Shift+Enter for newline)" : "Connecting to engine..."}
              disabled={!connected}
              rows={1}
            />
            <button type="submit" disabled={!connected || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      </section>

      {/* Artifacts/Context Panel */}
      <section className="artifacts-panel glass-panel">
        <header className="panel-header">
          <h2>Workspace Context</h2>
        </header>
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <p>Artifacts and visualizations will appear here.</p>
        </div>
      </section>
    </div>
  );
}

export default App;
