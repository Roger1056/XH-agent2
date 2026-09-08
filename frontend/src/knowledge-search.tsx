import { getApiBase } from "./workflow-stream";

export type KnowledgeHit = { doc_id?: string; doc_title?: string; content: string };

export async function searchKnowledge(question: string): Promise<KnowledgeHit[]> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${getApiBase()}/api/knowledge/search?q=${encodeURIComponent(question)}&top_k=5`, { signal: controller.signal });
    if (!response.ok) throw new Error("知识检索暂不可用，请重试。");
    const payload = await response.json();
    if (!payload || !Array.isArray(payload.results) || !payload.results.every((hit: unknown) => {
      if (!hit || typeof hit !== "object") return false;
      const item = hit as Record<string, unknown>;
      return typeof item.content === "string" && (item.doc_id == null || typeof item.doc_id === "string")
        && (item.doc_title == null || typeof item.doc_title === "string");
    })) throw new Error("知识检索返回的数据不完整，请重试。");
    return payload.results;
  } catch (error) {
    if (controller.signal.aborted) throw new Error("知识检索超时，请重试。");
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

// Shared with the existing global knowledge search panel.
export function KnowledgeResults({ results, onOpen }: { results: KnowledgeHit[]; onOpen?: (hit: KnowledgeHit) => void }) {
  return <>{results.map((hit, index) => onOpen ? (
    <button key={index} onClick={() => onOpen(hit)} className="block w-full rounded-xl px-3 py-2 text-left transition hover:bg-[#192837]/[0.06]" type="button">
      <span className="block truncate text-sm font-semibold text-[#192837]">{hit.doc_title || hit.doc_id || "知识文档"}</span>
      <span className="block truncate text-xs text-[#192837]/55">{hit.content}</span>
    </button>
  ) : (
    <article key={index} className="mt-3 rounded-xl bg-black/20 p-3">
      <h6 className="break-words font-semibold">{hit.doc_title || hit.doc_id || "知识文档"}</h6>
      <p className="mt-2 whitespace-pre-wrap break-words">{hit.content || "该结果未提供正文片段。"}</p>
      <p className="mt-2 break-all text-xs text-white/60">来源：{hit.doc_id || hit.doc_title || "知识库（未提供文档标识）"}</p>
    </article>
  ))}</>;
}
