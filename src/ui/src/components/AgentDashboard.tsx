import React from 'react';
import { useTranslation } from '../i18n/index.ts';
import './AgentDashboard.css';

// agent dashboard props
interface AgentDashboardProps {
  isThinking: boolean;
  statusText?: string;
}

// agent thinking status indicator wrapped in memo
export const AgentDashboard: React.FC<AgentDashboardProps> = React.memo(({ isThinking, statusText }) => {
  // get t helper
  const { t } = useTranslation();

  if (!isThinking && !statusText) return null;

  return (
    <div className="agent-dashboard">
      <div className="thinking-dots">
        <span className="dot"></span>
        <span className="dot"></span>
        <span className="dot"></span>
      </div>
      <div className="status-text">
        {statusText || (isThinking ? t('agent.thinking') : t('agent.idle'))}
      </div>
    </div>
  );
});

