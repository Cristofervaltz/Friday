import { useState, useEffect, useRef } from 'react';
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Connect to local FastAPI server
    const websocket = new WebSocket('ws://127.0.0.1:8000/ws/chat');
    
    websocket.onopen = () => {
      setConnected(true);
      console.log('Connected to Friday API');
    };
    
    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'output') {
          // Append to the last bot message or create a new one
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'bot') {
              // Update last message
              return [
                ...prev.slice(0, -1), 
                { ...last, content: last.content + data.content }
              ];
            } else {
              // Create new bot message
              return [...prev, { id: Date.now().toString(), role: 'bot', content: data.content }];
            }
          });
        }
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };
    
    websocket.onclose = () => {
      setConnected(false);
      console.log('Disconnected from Friday API');
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !ws || !connected) return;
    
    // Add user message
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    
    // Send to server
    ws.send(JSON.stringify({ type: 'message', content: input }));
    setInput('');
  };

  return (
    <div className="app-container">
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
              <p>How can I help you today?</p>
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
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask Friday to run a task..."
              disabled={!connected}
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
