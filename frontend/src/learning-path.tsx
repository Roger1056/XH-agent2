export type LearningPath = {
  learner_id: string;
  total_estimated_hours: number;
  created_at?: string;
  nodes: Array<{
    node_id: string;
    title: string;
    resource_id?: string | null;
    resource_type?: string | null;
    difficulty: string;
    estimated_duration_minutes: number;
    depends_on: string[];
    is_completed: boolean;
  }>;
};

export function PlannedLearningPath({ path, resources = [], onSelectResource }: {
  path: LearningPath;
  resources?: Array<{ resource_id?: string; resource_type: string }>;
  onSelectResource?: (type: string) => void;
}) {
  const names = new Map(path.nodes.map((node) => [node.node_id, node.title]));
  return <section aria-label="个性化学习路径" className="learning-path mt-6 rounded-2xl border border-white/10 bg-white/[0.04] p-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-white">个性化学习路径</h4>
      <span className="text-xs text-white/60">{path.nodes.length} 个节点 · 预计 {path.total_estimated_hours} 小时</span>
    </div>
    {!path.nodes.length ? <p className="mt-3 text-sm text-white/60">本次诊断暂无需要补强的路径节点。</p> : <ol className="mt-4 grid gap-3">
      {path.nodes.map((node, index) => {
        // A resource ID is authoritative; type matching is only a fallback when no ID exists.
        const resource = node.resource_id
          ? resources.find((item) => item.resource_id === node.resource_id)
          : resources.find((item) => item.resource_type === node.resource_type);
        return <li key={node.node_id} className="rounded-xl bg-white/[0.06] p-4">
          <div className="flex items-start gap-3">
            <span className="rounded-full bg-[#7342E2]/30 px-2 py-1 text-xs text-[#C7B3F5]">{index + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="break-words text-sm font-semibold text-white/90">{node.title}</p>
              <p className="mt-1 text-xs text-white/60">{({ beginner: "入门", intermediate: "进阶", advanced: "高级" } as Record<string, string>)[node.difficulty] ?? node.difficulty} · {node.estimated_duration_minutes} 分钟 · {node.is_completed ? "已完成" : "待学习"}</p>
              <p className="mt-2 break-words text-xs leading-5 text-white/60">前置：{node.depends_on.length ? node.depends_on.map((id) => names.get(id) ?? id).join("、") : "无，可直接开始"}</p>
              {resource && onSelectResource ? <button type="button" onClick={() => onSelectResource(resource.resource_type)} className="mt-3 rounded-full bg-[#7342E2] px-3 py-1.5 text-xs text-white">查看配套资源</button> : <p className="mt-2 text-xs text-white/45">配套资源待生成</p>}
            </div>
          </div>
        </li>;
      })}
    </ol>}
  </section>;
}
