import {useMemo,useState,useRef,useEffect} from 'react';
import {useQuery,useMutation} from '@tanstack/react-query';
import {api} from '../services/api';
import {Brain, Send, Sparkles, ShieldCheck, AlertTriangle, CheckCircle2, MessageCircle, Clock, DatabaseZap, LockKeyhole, ThumbsUp, ThumbsDown} from 'lucide-react';

function money(value:number){return new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(value||0)}

type Msg={role:'user'|'advisor',text:string,cards?:any[],disclaimer?:string,premium?:any,rag?:any[],analytics?:any};

export default function Advisor(){
  const [question,setQuestion]=useState('');
  const [messages,setMessages]=useState<Msg[]>([]);
  const endRef=useRef<HTMLDivElement|null>(null);
  const {data,isLoading}=useQuery({queryKey:['conversational-advisor-dashboard'],queryFn:async()=>{const {data}=await api.get('/intelligence/conversational-advisor/dashboard');return data}});
  const chat=useMutation({mutationFn:async(q:string)=>{const {data}=await api.post('/intelligence/advisor/chat',{question:q});return data},onSuccess:(data,question)=>{setMessages(prev=>[...prev,{role:'user',text:question},{role:'advisor',text:data.answer,cards:data.context_cards,disclaimer:data.disclaimer,premium:data.premium_advisor,rag:data.rag_context,analytics:data.ai_analytics}]);setQuestion('')}});
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:'smooth',block:'end'});},[messages,chat.isPending]);
  const suggestions=useMemo(()=>data?.suggested_questions||['Quanto posso investir este mês?','Vale quitar dívida ou investir?','Qual meu próximo passo financeiro?'],[data]);
  const ctx=data?.context_summary||{}; const health=ctx.health||{}; const situation=ctx.current_financial_situation||{};
  function ask(q:string){if(!q.trim()||chat.isPending)return;chat.mutate(q.trim())}
  const hasContext=Boolean(situation.monthly_income||situation.total_expenses||ctx.recommended_model);
  return <section className="page advisor-page">
    <div className="hero-card premium-card advisor-hero">
      <div>
        <span className="eyebrow">Advisor Financeiro Premium</span>
        <h1>{data?.main_message||'Converse com seu copiloto financeiro Vinance'}</h1>
        <p>O advisor usa seus dados reais do ERP, memória de conversa, alertas, metas, comportamento e safety financeiro para responder com clareza.</p>
      </div>
      <div className="advisor-status-card">
        <span className="pill"><ShieldCheck size={15}/> Safety ativo</span>
        <span className="pill"><DatabaseZap size={15}/> Contexto ERP</span>
        <span className="pill"><LockKeyhole size={15}/> Multi-tenant</span>
      </div>
      <div className="hero-actions"><span className="pill">Score: {health.health_score||0}/100</span><span className="pill">Fase: {ctx.financial_phase||'em análise'}</span><span className="pill">Sobra segura: {money(ctx.investment_capacity||0)}</span></div>
    </div>

    <div className="advisor-layout">
      <aside className="advisor-side premium-card">
        <h2><Brain size={18}/> Contexto financeiro</h2>
        {isLoading?<div className="skeleton-line"/>:<ul className="clean-list">
          <li>Renda do mês: <strong>{money(situation.monthly_income)}</strong></li>
          <li>Despesas: <strong>{money(situation.total_expenses)}</strong></li>
          <li>Modelo recomendado: <strong>{ctx.recommended_model||'em análise'}</strong></li>
          <li>Capacidade segura: <strong>{money(ctx.investment_capacity)}</strong></li>
        </ul>}
        <div className="advisor-mini-panel">
          <strong>Próximo passo</strong>
          <p>{data?.next_step||'Atualize seus dados financeiros para receber orientação contextual.'}</p>
        </div>
        <h3><Sparkles size={16}/> Perguntas inteligentes</h3>
        <div className="quick-grid advisor-suggestions">{suggestions.map((s:string)=><button key={s} className="button secondary" onClick={()=>ask(s)}>{s}</button>)}</div>
      </aside>

      <div className="premium-card chat-card advisor-chat-card">
        <div className="chat-title-row">
          <div><h2><MessageCircle size={18}/> Conversa consultiva</h2><p className="muted">Pergunte livremente. O Vinance responde com contexto, continuidade e guardrails.</p></div>
          <span className="pill"><Clock size={15}/> {messages.length/2|0} conversas</span>
        </div>
        <div className="chat-window premium-chat-window">
          {messages.length===0&&<div className="empty-state advisor-empty"><ShieldCheck size={24}/><h3>Seu advisor está pronto</h3><p>{hasContext?'Experimente perguntar: “qual meu maior problema financeiro hoje?” ou “posso aumentar meu aporte?”':'Cadastre renda, despesas e metas para o advisor ganhar mais contexto.'}</p></div>}
          {messages.map((m,i)=><div key={i} className={`chat-bubble ${m.role} advisor-bubble`}>
            <p>{m.text}</p>
            {(m.cards?.length ?? 0) > 0 && (
              <div className="hero-actions">
                {(m.cards ?? []).map((c: any) => (
                  <span className="pill" key={c.label}>{c.label}: {c.value}</span>
                ))}
              </div>
            )}
            {m.premium&&<div className="premium-answer-grid">
              <div><strong>Diagnóstico</strong><small>{m.premium.diagnosis}</small></div>
              <div><strong>Decisão</strong><small>{m.premium.recommended_decision}</small></div>
              <div><strong>Alternativa segura</strong><small>{m.premium.alternatives?.conservative}</small></div>
            </div>}
            {(m.rag?.length ?? 0) > 0 && (
              <small className="muted">
                Contexto recuperado: {(m.rag ?? []).map((r: any) => r.title).slice(0, 3).join(' · ')}
              </small>
            )}
            {m.analytics?.latency_ms!==undefined&&<small className="muted">Resposta em {m.analytics.latency_ms}ms · {m.analytics.topic}</small>}
            {m.disclaimer&&<small className="muted">{m.disclaimer}</small>}
            {m.role==='advisor'&&<div className="feedback-row"><button className="button secondary" type="button"><ThumbsUp size={14}/> Útil</button><button className="button secondary" type="button"><ThumbsDown size={14}/> Ajustar</button></div>}
          </div>)}
          {chat.isPending&&<div className="chat-bubble advisor advisor-bubble typing"><span></span><span></span><span></span><p>Estou cruzando contexto, memória e safety financeiro...</p></div>}
          <div ref={endRef}/>
        </div>
        {chat.isError&&<div className="advisor-error"><AlertTriangle size={16}/> Não consegui responder agora. Tente novamente ou atualize o plano financeiro.</div>}
        <form className="chat-input premium-chat-input" onSubmit={e=>{e.preventDefault();ask(question)}}>
          <input value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Pergunte ao Advisor Financeiro..." />
          <button className="button" disabled={chat.isPending}><Send size={16}/> {chat.isPending?'Analisando':'Enviar'}</button>
        </form>
      </div>
    </div>

    {data?.copilot_events?.length>0&&<div className="premium-card warning"><h2><AlertTriangle size={18}/> Eventos do copiloto</h2><ul className="clean-list">{data.copilot_events.slice(0,5).map((ev:any)=><li key={ev.type+ev.message}><CheckCircle2 size={16}/><span><strong>{ev.severity}</strong>: {ev.message}<br/><small>{ev.suggested_action}</small></span></li>)}</ul></div>}
    <p className="muted">{data?.disclaimer}</p>
  </section>
}
