import React from 'react';
import './AgentDashboard.css';

interface AgentDashboardProps {
  isThinking: boolean;
  statusText?: string;
}

export const AgentDashboard: React.FC<AgentDashboardProps> = ({ isThinking, statusText }) => {
  if (!isThinking && !statusText) return null;

  return (
    <div className="agent-dashboard">
      <div className="thinking-dots">
        <span className="dot"></span>
        <span className="dot"></span>
        <span className="dot"></span>
      </div>
      <div className="status-text">
        {statusText || (isThinking ? 'Friday is thinking...' : 'Idle')}
      </div>
    </div>
  );
};
