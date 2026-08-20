import React, { useEffect, useRef, useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from 'mermaid';
import { useTranslation } from '../i18n/index.ts';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
});

// static remark plugins list to avoid rebuilding markdown ast on every render
const REMARK_PLUGINS = [remarkGfm];

// mermaid renderer with fallback wrapped in memo
const Mermaid: React.FC<{ diagram: string }> = React.memo(({ diagram }) => {
  const [svg, setSvg] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  useEffect(() => {
    let isMounted = true;
    const renderDiagram = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg: renderedSvg } = await mermaid.render(id, diagram);
        if (isMounted) setSvg(renderedSvg);
      } catch (e) {
        console.error("Failed to render mermaid diagram", e);
        if (isMounted) setSvg(`<pre>${t('artifact.mermaid_error')} ${e}</pre>`);
      }
    };
    renderDiagram();
    return () => {
      isMounted = false;
    };
  }, [diagram, t]);

  return <div ref={ref} dangerouslySetInnerHTML={{ __html: svg }} />;
});

// artifact renderer props
interface ArtifactRendererProps {
  content: string;
}

// markdown and code syntax highlighter renderer memoized
export const ArtifactRenderer: React.FC<ArtifactRendererProps> = React.memo(({ content }) => {
  // memoize custom code block components mapping
  const components = useMemo(() => ({
    code({ node: _node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      const lang = match ? match[1] : '';
      const codeString = String(children).replace(/\n$/, '');

      if (!inline && lang === 'mermaid') {
        return <Mermaid diagram={codeString} />;
      }

      if (!inline && match) {
        return (
          <div style={{ position: 'relative', margin: '1em 0' }}>
            <div style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              zIndex: 1,
            }}>
              <button
                onClick={() => navigator.clipboard.writeText(codeString)}
                title="Copy code"
                style={{
                  background: 'rgba(255,255,255,0.1)',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'var(--text-low)',
                  padding: '4px 8px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--text-low)'}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                Copy
              </button>
            </div>
            <SyntaxHighlighter
              {...props}
              style={vscDarkPlus}
              language={lang}
              PreTag="div"
              customStyle={{ margin: 0, padding: '16px', borderRadius: '8px' }}
            >
              {codeString}
            </SyntaxHighlighter>
          </div>
        );
      }

      return (
        <code {...props} className={className}>
          {children}
        </code>
      );
    }
  }), []);

  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      components={components}
    >
      {content}
    </ReactMarkdown>
  );
});

