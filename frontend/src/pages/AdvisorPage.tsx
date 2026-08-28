import { FormEvent, useState } from 'react';
import { Send } from 'lucide-react';
import { Badge, Button, Card, ChatSuggestion, ErrorState, Input, SectionHeader } from '../components';
import { useAdvisorChat } from '../features/advisor/hooks/useAdvisorChat';
import type { AdvisorMessage } from '../features/advisor/types/advisor.types';
import { useFinancialProfile } from '../features/financial/hooks/useFinancial';
import type { ApiErrorShape } from '../services/api';

const suggestions = ['Como melhorar meu score?', 'Minha reserva está saudável?', 'Por que minha allocation mudou?'];

export function AdvisorPage() {
  const [messages, setMessages] = useState<AdvisorMessage[]>([{ role: 'assistant', text: 'Olá. Posso explicar seu diagnóstico, allocation e alertas usando o contexto real do Vinance. Não faço recomendação definitiva de compra.' }]);
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
      setMessages((current) => [...current, { role: 'assistant', text: response.response, warnings: response.warnings }]);
    } catch {
      setMessages((current) => [...current, { role: 'assistant', text: 'Não consegui acessar o Advisor agora. Verifique se a API está online e tente novamente.' }]);
    }
  }

  async function handleSend(event?: FormEvent) {
    event?.preventDefault();
    await sendMessage(input);
  }

  return (
    <section className="vn-page vn-advisor-page">
      <SectionHeader eyebrow="Advisor IA" title="Conversa financeira com contexto, sem tom de guru." description="Conectado ao endpoint real /advisor/chat. Sem streaming e sem renderização HTML perigosa." />
      {missingProfile && <Card className="vn-section-gap"><div className="vn-context-warning"><Badge tone="warning">contexto incompleto</Badge><p>Complete seu perfil financeiro para respostas mais personalizadas. O chat continua disponível, mas o Advisor terá menos contexto.</p></div></Card>}
      <Card className="vn-chat-card">
        <div className="vn-chat-suggestions" aria-label="Sugestões iniciais">
          {suggestions.map((suggestion) => <ChatSuggestion key={suggestion} text={suggestion} disabled={chat.isPending} onClick={sendMessage} />)}
        </div>
        <div className="vn-chat-window">
          {messages.map((message, index) => <div key={`${message.role}-${index}`} className={`vn-message vn-message--${message.role}`}><p>{message.text}</p>{message.warnings?.map((warning) => <small key={warning.code}>{warning.message}</small>)}</div>)}
          {chat.isPending && <div className="vn-message vn-message--assistant"><div className="vn-loading vn-loading--inline"><span /><span /><span /><p>Advisor preparando resposta...</p></div></div>}
          {error && <div className="vn-message vn-message--assistant"><ErrorState title="Advisor indisponível" description={error.message} /></div>}
        </div>
        <form className="vn-chat-input" onSubmit={handleSend}><Input placeholder="Pergunte sobre score, reserva, risco ou alocação..." value={input} onChange={(event) => setInput(event.target.value)} maxLength={2000} /><Button disabled={chat.isPending || !input.trim()}><Send size={16} /> Enviar</Button></form>
      </Card>
    </section>
  );
}
