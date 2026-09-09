export type ResourceMatchPoint = {
  resource_type?: string;
  title?: string;
  learner_difficulty?: string;
  resource_difficulty?: string;
  difficulty_match?: number;
  matched?: boolean;
};
const levels = ["beginner", "intermediate", "advanced"];
const labels = ["入门", "进阶", "高级"];
const clamp = (value: number) => Math.max(0, Math.min(1, value));

export function KnowledgeRadarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data ?? {}).filter(([, value]) => Number.isFinite(value));
  const center = 120, radius = 86;
  const point = (i: number, value: number) => {
    const angle = i * 2 * Math.PI / entries.length - Math.PI / 2;
    return [center + radius * value * Math.cos(angle), center + radius * value * Math.sin(angle)];
  };
  return <section className="min-w-0" aria-label="知识掌握度">
    <h4 className="mb-3 text-sm font-semibold text-white/85">知识雷达图</h4>
    {!entries.length ? <p className="text-sm text-white/55">暂无知识掌握度数据</p> : <>
      {entries.length >= 3 && <svg role="img" aria-label="知识掌握度雷达图，编号对应下方知识点" viewBox="0 0 240 240" className="mx-auto w-full max-w-[280px]">
        <title>知识掌握度，范围 0% 至 100%</title>
        {[0.25, 0.5, 0.75, 1].map((scale) => <polygon key={scale} points={entries.map((_, i) => point(i, scale).join(",")).join(" ")} fill="none" stroke="rgba(255,255,255,0.18)" />)}
        {entries.map(([topic], i) => { const [x, y] = point(i, 1); const [tx, ty] = point(i, 1.19); return <g key={topic}><line x1={center} y1={center} x2={x} y2={y} stroke="rgba(255,255,255,0.16)" /><text x={tx} y={ty} textAnchor="middle" dominantBaseline="middle" fill="#9BE8D4" fontSize="10">{i + 1}</text></g>; })}
        <polygon points={entries.map(([, value], i) => point(i, clamp(value)).join(",")).join(" ")} fill="rgba(30,110,100,0.3)" stroke="#4FD6B4" strokeWidth="2" />
        {entries.map(([topic, value], i) => { const [x, y] = point(i, clamp(value)); return <circle key={topic} cx={x} cy={y} r="3" fill="#4FD6B4"><title>{topic}：{Math.round(clamp(value) * 100)}%</title></circle>; })}
      </svg>}
      <ol className="grid gap-2 text-xs text-white/70">{entries.map(([topic, value], i) => <li key={topic} className="flex items-start justify-between gap-3"><span className="min-w-0 break-words">{i + 1}. {topic}</span><span className="shrink-0">{Math.round(clamp(value) * 100)}%</span></li>)}</ol>
    </>}
  </section>;
}

export function DifficultyMatchCurve({ data }: { data: ResourceMatchPoint[] }) {
  const points = data ?? [];
  const x = (i: number) => points.length === 1 ? 180 : 45 + i * 270 / (points.length - 1);
  const y = (level: string | undefined) => 132 - levels.indexOf(level ?? "") * 48;
  const valid = (level?: string) => levels.includes(level ?? "");
  const color = (item: ResourceMatchPoint) => {
    if (!valid(item.resource_difficulty) || !valid(item.learner_difficulty)) return "#94A3B8";
    const gap = Math.abs(levels.indexOf(item.resource_difficulty!) - levels.indexOf(item.learner_difficulty!));
    return ["#34D399", "#FBBF24", "#F87171"][gap];
  };
  return <section className="min-w-0" aria-label="资源难度匹配">
    <h4 className="mb-3 text-sm font-semibold text-white/85">资源难度匹配曲线</h4>
    {!points.length ? <p className="text-sm text-white/55">暂无资源难度信息</p> : <>
      <svg role="img" aria-label="资源序号与难度，紫色虚线为学习者推荐难度" viewBox="0 0 350 170" className="w-full">
        <title>资源难度与学习者推荐难度对比</title>
        {levels.map((level, i) => <g key={level}><line x1="45" y1={y(level)} x2="315" y2={y(level)} stroke="rgba(255,255,255,0.15)" /><text x="5" y={y(level) + 4} fill="#CBD5E1" fontSize="10">{labels[i]}</text></g>)}
        {points.map((item, i) => <g key={i}>
          {i > 0 && valid(item.resource_difficulty) && valid(points[i - 1].resource_difficulty) && <line x1={x(i - 1)} y1={y(points[i - 1].resource_difficulty)} x2={x(i)} y2={y(item.resource_difficulty)} stroke="#CBD5E1" />}
          {i > 0 && valid(item.learner_difficulty) && valid(points[i - 1].learner_difficulty) && <line x1={x(i - 1)} y1={y(points[i - 1].learner_difficulty)} x2={x(i)} y2={y(item.learner_difficulty)} stroke="#4FD6B4" strokeWidth="2" strokeDasharray="4 4" />}
          {valid(item.learner_difficulty) && <circle cx={x(i)} cy={y(item.learner_difficulty)} r="6" fill="none" stroke="#4FD6B4" />}
          {valid(item.resource_difficulty) && <circle cx={x(i)} cy={y(item.resource_difficulty)} r="3.5" fill={color(item)}><title>{item.title || item.resource_type}：{labels[levels.indexOf(item.resource_difficulty!)]}</title></circle>}
          <text x={x(i)} y="156" textAnchor="middle" fill="#CBD5E1" fontSize="10">{i + 1}</text>
        </g>)}
      </svg>
      <p className="mb-3 text-xs leading-6 text-white/60">青绿虚线：推荐难度 · 绿：匹配 · 黄：差 1 档 · 红：差 2 档</p>
      <ol className="grid gap-2 text-xs text-white/70">{points.map((item, i) => <li key={i} className="break-words">{i + 1}. {item.title || item.resource_type || "未命名资源"} <span style={{ color: color(item) }}>（{valid(item.resource_difficulty) ? labels[levels.indexOf(item.resource_difficulty!)] : "难度未知"}）</span></li>)}</ol>
    </>}
  </section>;
}
