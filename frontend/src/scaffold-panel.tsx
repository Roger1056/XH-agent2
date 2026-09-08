import { useEffect, useRef, useState } from "react";
import { askStudyQuestion, requestScaffold, type LearnerQuestionResponse, type ScaffoldResponse } from "./learning-session";

export function ScaffoldPanel({ topic, context, skillGaps, onApplyRevision }: {
  topic: string;
  context: string;
  skillGaps?: Array<{ topic?: string; current_level?: number; target_level?: number; priority?: string }>;
  onApplyRevision: (answer: LearnerQuestionResponse) => void;
}) {
  const [question, setQuestion] = useState("");
  const [activeQuestion, setActiveQuestion] = useState("");
  const [reply, setReply] = useState("");
  const [steps, setSteps] = useState<ScaffoldResponse[]>([]);
  const [direct, setDirect] = useState<LearnerQuestionResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState(false);
  const sequence = useRef(0);
  const pending = useRef(false);
  useEffect(() => () => { sequence.current += 1; }, []);
  const latest = steps[steps.length - 1];
  const ask = async (continuing = false, studentAnswer = "") => {
    const original = continuing ? activeQuestion : question.trim();
    if (!original || pending.current) return;
    pending.current = true;
    const id = ++sequence.current;
    setBusy(true); setError("");
    if (!continuing) { setSteps([]); setDirect(null); setActiveQuestion(original); setApplied(false); }
    try {
      const response = await requestScaffold(original, continuing ? latest?.tier ?? 0 : 0, studentAnswer, skillGaps);
      if (id !== sequence.current) return;
      if (response.mode === "direct") {
        const answer = await askStudyQuestion(original, topic.slice(0, 500), context.slice(0, 12000));
        if (id !== sequence.current) return;
        setDirect(answer);
      } else {
        setSteps((previous) => [...previous.filter((step) => step.tier !== response.tier), response]);
      }
      setReply("");
    } catch (cause) {
      if (id === sequence.current) setError(cause instanceof Error ? cause.message : "请求失败，请重试。");
    } finally {
      if (id === sequence.current) { pending.current = false; setBusy(false); }
    }
  };
  const finalAnswer: LearnerQuestionResponse | null = direct ?? (latest?.revealed_answer ? {
    answer: latest.content,
    suggestions: [],
    revisionTitle: `学习答疑 · ${latest.knowledge_point}`,
    revisionContent: latest.content + (latest.kb_source ? `\n\n来源：${latest.kb_source}` : ""),
  } : null);
  return <section aria-label="分步学习答疑" className="rounded-2xl bg-white/[0.07] p-5">
    <h5 className="text-lg font-semibold text-white">学习答疑 · 先思考，再看答案</h5>
    <p className="mt-2 text-xs leading-6 text-white/60">支持的知识点将提供分步提示，其他问题使用普通答疑。</p>
    <form className="mt-4 grid gap-3" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
      <textarea aria-label="学习问题" maxLength={1500} disabled={busy} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="例如：机器人坐标系如何选择？" className="min-h-24 w-full rounded-xl bg-black/20 p-3 text-sm text-white focus:ring-2 focus:ring-[#B99DFF]" />
      <button type="submit" disabled={busy || !question.trim()} className="rounded-full bg-white px-4 py-3 text-sm font-semibold text-[#192837] disabled:opacity-50">{busy ? "正在获取回答…" : "开始提问"}</button>
    </form>
    <div aria-live="polite" aria-busy={busy} className="mt-4 grid gap-3">
      {steps.length > 0 && <p className="break-words text-xs text-white/60">当前问题：{activeQuestion}</p>}
      {steps.map((step) => <article key={step.tier} className="rounded-xl bg-[#0B1D2A] p-4">
        <h6 className="text-sm font-semibold text-[#C7B3F5]">L{step.tier} · {step.tier === 1 ? "引导思考" : step.tier === 2 ? "给出线索" : "完整答案"}</h6>
        <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-white/85">{step.content}</p>
        {step.revealed_answer && step.kb_source && <p className="mt-3 break-all text-xs text-white/60">知识库来源：{step.kb_source}</p>}
      </article>)}
      {direct && <article className="rounded-xl bg-[#0B1D2A] p-4 text-sm leading-7 text-white/85"><h6 className="font-semibold">针对你的问题</h6><p className="mt-2 whitespace-pre-wrap">{direct.answer}</p>{direct.suggestions.map((item, i) => <p key={i}>{item}</p>)}</article>}
    </div>
    {latest && !latest.revealed_answer && !direct && <form className="mt-4 grid gap-3" onSubmit={(event) => { event.preventDefault(); void ask(true, reply.trim()); }}>
      <textarea aria-label="我的思考" maxLength={4000} value={reply} disabled={busy} onChange={(event) => setReply(event.target.value)} placeholder="写下你的判断，或点击下方按钮继续" className="min-h-20 rounded-xl bg-black/20 p-3 text-sm text-white" />
      <div className="flex flex-wrap gap-2">
        <button disabled={busy} type="submit" className="rounded-full bg-[#7342E2] px-4 py-2 text-sm text-white disabled:opacity-50">{latest.tier === 1 ? "下一步提示" : "查看完整答案"}</button>
        <button disabled={busy} type="button" onClick={() => void ask(true, "不知道，卡住了")} className="rounded-full bg-white/10 px-4 py-2 text-sm text-white disabled:opacity-50">我不知道，查看答案</button>
      </div>
    </form>}
    {error && <p role="alert" className="mt-3 text-sm text-red-200">{error} 请点击原按钮重试。</p>}
    {finalAnswer && <button type="button" disabled={applied || busy} onClick={() => { onApplyRevision(finalAnswer); setApplied(true); }} className="mt-4 rounded-full bg-[#7342E2] px-4 py-2 text-xs text-white disabled:opacity-50">{applied ? "补充已加入当前资源" : "将补充内容加入当前资源"}</button>}
  </section>;
}
