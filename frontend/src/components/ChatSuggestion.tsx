type ChatSuggestionProps = { text: string; onClick: (text: string) => void; disabled?: boolean };

export function ChatSuggestion({ text, onClick, disabled = false }: ChatSuggestionProps) {
  return <button type="button" className="vn-chat-suggestion" disabled={disabled} onClick={() => onClick(text)}>{text}</button>;
}
