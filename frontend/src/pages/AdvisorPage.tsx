import { FormEvent, useState } from 'react';
import { Send } from 'lucide-react';
import { Badge, Button, Card, ChatSuggestion, ErrorState, Input, SectionHeader } from '../components';
import { useAdvisorChat } from '../features/advisor/hooks/useAdvisorChat';
import type { AdvisorMessage } from '../features/advisor/types/advisor.types';
import { useFinancialProfile } from '../features/financial/hooks/useFinancial';
import { describeAdvisorContext, presentAdvisorWarning } from '../features/intelligence/utils/presentation';
import type { ApiErrorShape } from '../services/api';

const suggestions = ['Como melhorar minha saúde financeira?', 'Minha reserva está saudável?', 'Por que minha alocação mudou?'];

export function AdvisorPage() {
  const [messages, setMessages] = useState<AdvisorMessage[]>([{ role: 'assistant', text: 'Olá. Posso ajudar a interpretar sua situação, alocação e alertas com os dados disponíveis. Não executo operações nem substituo uma decisão profissional.' }]);
  const [input, setInput] = useState('');
  const chat = useAdvisorChat();
  const profile = useFinancialProfile();
  const error = chat.error as ApiErrorShape | null;
  const missingProfile = Boolean((profile.error as ApiErrorShape | null)?.status === 404);

  async function sendMessage(text: string) {
    const cleanText = text.trim();
    if (!cleanText || chat.isPending) return;
    setMessages((current) => [...current, { role: 'user', text: cleanText }]);
    setInput('');
    try {
      const response = await chat.mutateAsync({ message: cleanText });
      setMessages((current) => [...current, { role: 'assistant', text: response.response, warnings: response.warnings, contextUsed: response.context_used }]);
    } catch {
      setMessages((current) => [...current, { role: 'assistant', text: 'Não consegui preparar uma resposta segura agora. Tente novamente em instantes.' }]);
    }
  }

  async function handleSend(event?: FormEvent) {
    event?.preventDefault();
    await sendMessage(input);
  }

  return (
    <section className="vn-page vn-advisor-page">
      <SectionHeader eyebrow="Assistente financeiro" title="Entenda melhor suas decisões" description="Respostas explicativas com o contexto disponível, sem promessa de retorno e sem execução financeira." />
      {missingProfile && <Card className="vn-section-gap"><div className="vn-context-warning"><Badge tone="warning">Contexto incompleto</Badge><p>Complete seu perfil financeiro para respostas mais adequadas. O assistente continua disponível, mas informará suas limitações.</p></div></Card>}
      <Card className="vn-chat-card">
        <div className="vn-chat-suggestions" aria-label="Sugestões iniciais">
          {suggestions.map((suggestion) => <ChatSuggestion key={suggestion} text={suggestion} disabled={chat.isPending} onClick={sendMessage} />)}
        </div>
        <div className="vn-chat-window">
          {messages.map((message, index) => {
            const context = describeAdvisorContext(message.contextUsed);
            return <div key={`${message.role}-${index}`} className={`vn-message vn-message--${message.role}`}>
              <p>{message.text}</p>
              {context.length > 0 && <div className="vn-advisor-context" aria-label="Contexto usado nesta resposta">{context.map((item) => <span key={item}>{item}</span>)}</div>}
              {message.warnings?.map((warning) => <small key={`${warning.code}-${warning.message}`}>{presentAdvisorWarning(warning)}</small>)}
            </div>;
          })}
          {chat.isPending && <div className="vn-message vn-message--assistant"><div className="vn-loading vn-loading--inline"><span /><span /><span /><p>Preparando uma resposta com o contexto disponível...</p></div></div>}
          {error && <div className="vn-message vn-message--assistant"><ErrorState title="Assistente indisponível" description="Não foi possível consultar o assistente neste momento. Tente novamente." /></div>}
        </div>
        <form className="vn-chat-input" onSubmit={handleSend}><Input placeholder="Pergunte sobre sua situação, reserva, risco ou alocação..." value={input} onChange={(event) => setInput(event.target.value)} maxLength={2000} /><Button disabled={chat.isPending || !input.trim()}><Send size={16} /> Enviar</Button></form>
      </Card>
    </section>
  );
}
