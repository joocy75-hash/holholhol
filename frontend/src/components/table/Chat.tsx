import { useState, useRef, useEffect, memo } from 'react';
import { Send } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import type { ChatMessage } from '@/types/ui';

interface ChatProps {
  messages: ChatMessage[];
  onSend: (message: string) => void;
  disabled?: boolean;
}

const ChatMessageItem = memo(function ChatMessageItem({ message }: { message: ChatMessage }) {
  const isSystem = message.type === 'system';

  return (
    <div
      className={cn(
        'px-3 py-2 rounded',
        isSystem ? 'bg-surface/50 italic' : 'hover:bg-surface/30'
      )}
    >
      {!isSystem && message.sender && (
        <span className="font-medium text-primary">{message.sender}: </span>
      )}
      <span className={cn(isSystem ? 'text-text-muted text-sm' : 'text-text')}>
        {message.content}
      </span>
      <span className="text-xs text-text-muted ml-2">
        {message.timestamp.toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
        })}
      </span>
    </div>
  );
});

export function Chat({ messages, onSend, disabled = false }: ChatProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled) return;

    onSend(input.trim());
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-surface/50 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 bg-surface border-b border-bg">
        <h3 className="text-sm font-medium text-text">채팅</h3>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
        {messages.length === 0 ? (
          <p className="text-center text-text-muted text-sm py-4">
            아직 메시지가 없습니다
          </p>
        ) : (
          messages.map((message) => (
            <ChatMessageItem key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-2 border-t border-bg">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지 입력..."
            disabled={disabled}
            className="flex-1 px-3 py-2 bg-bg border border-surface rounded text-sm text-text placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
            maxLength={200}
          />
          <button
            type="submit"
            disabled={disabled || !input.trim()}
            className={cn(
              'p-2 rounded transition-colors',
              input.trim() && !disabled
                ? 'bg-primary text-white hover:bg-primary-hover'
                : 'bg-surface text-text-muted'
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
