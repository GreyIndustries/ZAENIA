import { useState } from "react";
import { openLink } from "../../core/openLink";
import "./ClarifyCard.css";

type Question = { question: string; options: string[] };

/** ZAE's quick questions before she makes something for you: tap an answer (or type your own), then send. */
export function ClarifyCard({ original, questions, onSend, onCancel }: { original: string; questions: Question[]; onSend: (text: string) => void; onCancel: () => void }) {
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ""));
  const set = (index: number, value: string) => setAnswers(current => current.map((answer, i) => i === index ? value : answer));
  const send = () => onSend(`${original}\n\nMy answers to your questions:\n${questions.map((q, i) => `- ${q.question} ${answers[i].trim() || "(no preference)"}`).join("\n")}`);
  // Opens ChatGPT in your browser with the question and the request filled in, for a second opinion.
  const askChatGpt = (q: Question) => openLink(`https://chatgpt.com/?q=${encodeURIComponent(`${q.question}\n\nContext: ${original.slice(0, 1200)}`)}`);
  return <div className="clarify" role="dialog" aria-label="ZAE's questions">
    <header><strong>A few quick questions</strong><button type="button" className="clarify__close" onClick={onCancel} aria-label="Close">✕</button></header>
    {questions.map((q, i) => <fieldset key={i}>
      <legend>{q.question}</legend>
      <div className="clarify__options">{q.options.map(option => <button type="button" key={option} aria-pressed={answers[i] === option}
        className={answers[i] === option ? "clarify__option clarify__option--on" : "clarify__option"} onClick={() => set(i, answers[i] === option ? "" : option)}>{option}</button>)}</div>
      <div className="clarify__row">
        <input value={q.options.includes(answers[i]) ? "" : answers[i]} maxLength={300} placeholder="Or type your own answer…" aria-label={`Your answer: ${q.question}`} onChange={event => set(i, event.target.value)}/>
        <button type="button" className="clarify__gpt" title="Open ChatGPT in your browser with this question" onClick={() => askChatGpt(q)}>Ask ChatGPT</button>
      </div>
    </fieldset>)}
    <footer>
      <button type="button" onClick={() => onSend(`${original}\n\nMy answers to your questions:\n- Use your best judgement.`)}>Skip, just do it</button>
      <button type="button" className="clarify__send" onClick={send}>Send answers</button>
    </footer>
  </div>;
}
