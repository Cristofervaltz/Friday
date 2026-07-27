import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
});

interface ArtifactRendererProps {
  content: string;
}

export const ArtifactRenderer: React.FC<ArtifactRendererProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const lang = match ? match[1] : '';

          if (!inline && lang === 'mermaid') {
            return <Mermaid diagram={String(children).replace(/\n$/, '')} />;
          }

          return !inline && match ? (
            <SyntaxHighlighter
              {...props}
              children={String(children).replace(/\n$/, '')}
              style={vscDarkPlus}
              language={lang}
              PreTag="div"
            />
          ) : (
            <code {...props} className={className}>
              {children}
            </code>
          );
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

const Mermaid: React.FC<{ diagram: string }> = ({ diagram }) => {
  const [svg, setSvg] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const renderDiagram = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg: renderedSvg } = await mermaid.render(id, diagram);
        setSvg(renderedSvg);
      } catch (e) {
        console.error("Failed to render mermaid diagram", e);
        setSvg(`<pre>Error rendering diagram: ${e}</pre>`);
      }
    };
    renderDiagram();
  }, [diagram]);

  return <div ref={ref} dangerouslySetInnerHTML={{ __html: svg }} />;
};
