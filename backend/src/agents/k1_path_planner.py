"""K1 伴学子系统 · 路径规划生成器（纯规则，不调 LLM）。

补齐赛题「路径规划」短板：根据 Agent1 诊断出的薄弱知识点（skill_gaps），
按预置的工业机器人知识点 DAG（附录 A2）生成一条拓扑有序的学习路径。

输入: diagnosis_result（含 skill_gaps / recommended_difficulty，knowledge_map 可选）
输出: LearningPath 形状的 dict（learner_id / nodes / total_estimated_hours / created_at）

设计约束（与调度器 / 闸门 / 博弈引擎一致）：
  - 纯规则裁决，不调 LLM（避免第二层幻觉）
  - 难度序号复用 schemas.difficulty_rank（单一权威映射）
  - 输出键名与 schemas.LearningPathNode / LearningPath 完全一致
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.src.schemas import difficulty_rank

# ═══════════════════════════════════════════════════════════
# 预置知识点 DAG（附录 A2）—— 随知识库实际文档增删
# ═══════════════════════════════════════════════════════════
# resource_type 取建议资源类型的第一项（LearningPathNode.resource_type 是单值枚举，
# A2 里的 "+ 第二类" 省略，仅作生成资源时的补充建议）。

_KNOWLEDGE_POINTS: dict[str, dict[str, Any]] = {
    "kp_safety": {
        "title": "安全急停链路",
        "keywords": ["安全", "急停"],
        "depends_on": [],
        "resource_type": "guide",
        "difficulty": "beginner",
        "minutes": 30,
    },
    "kp_coord": {
        "title": "机器人坐标系（基/工具/用户/大地）",
        "keywords": ["坐标"],
        "depends_on": [],
        "resource_type": "lecture",
        "difficulty": "beginner",
        "minutes": 30,
    },
    "kp_motion": {
        "title": "运动指令（PTP/LIN/CIRC）",
        "keywords": ["运动", "指令", "PTP", "LIN", "CIRC"],
        "depends_on": ["kp_coord"],
        "resource_type": "lecture",
        "difficulty": "beginner",
        "minutes": 40,
    },
    "kp_sim": {
        "title": "离线仿真（RobotStudio / ROBOGUIDE）",
        "keywords": ["仿真", "RobotStudio", "ROBOGUIDE"],
        "depends_on": ["kp_coord"],
        "resource_type": "guide",
        "difficulty": "beginner",
        "minutes": 45,
    },
    "kp_teach": {
        "title": "示教器编程（FANUC/ABB/KUKA）",
        "keywords": ["示教"],
        "depends_on": ["kp_coord", "kp_motion"],
        "resource_type": "guide",
        "difficulty": "intermediate",
        "minutes": 60,
    },
    "kp_ros": {
        "title": "ROS2/Gazebo 仿真",
        "keywords": ["ROS", "Gazebo"],
        "depends_on": ["kp_motion", "kp_sim"],
        "resource_type": "guide",
        "difficulty": "advanced",
        "minutes": 60,
    },
    "kp_fault": {
        "title": "故障诊断（SRVO-068 等）",
        "keywords": ["故障", "SRVO"],
        "depends_on": ["kp_coord", "kp_motion", "kp_teach"],
        "resource_type": "guide",
        "difficulty": "intermediate",
        "minutes": 50,
    },
}

# 关键词匹配优先级（越具体越靠前）：
#   "ROS2/Gazebo 仿真" 同时含 "ROS" 和 "仿真"，必须先命中 kp_ros 而非 kp_sim。
_MATCH_ORDER: list[str] = [
    "kp_ros",
    "kp_fault",
    "kp_safety",
    "kp_teach",
    "kp_motion",
    "kp_sim",
    "kp_coord",
]

# 拓扑排序的确定性 tie-break 顺序（即 A2 表的展示顺序，本身已是合法拓扑序）。
_DAG_ORDER: list[str] = [
    "kp_safety",
    "kp_coord",
    "kp_motion",
    "kp_sim",
    "kp_teach",
    "kp_ros",
    "kp_fault",
]


def _match_node(topic: Any) -> str | None:
    """把 skill_gap 的 topic 映射到 node_id；无命中返回 None。"""
    if not topic:
        return None
    t = str(topic).lower()
    for node_id in _MATCH_ORDER:
        for kw in _KNOWLEDGE_POINTS[node_id]["keywords"]:
            if str(kw).lower() in t:
                return node_id
    return None


def _topo_sort(node_ids: list[str]) -> list[str]:
    """Kahn 拓扑排序：前置先排；依赖不在本次路径内则忽略。

    队列 tie-break 用 _DAG_ORDER 保证输出稳定（不随 skill_gaps 出现顺序抖动）。
    """
    path = set(node_ids)
    in_degree = {nid: 0 for nid in node_ids}
    children: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for nid in node_ids:
        for dep in _KNOWLEDGE_POINTS[nid]["depends_on"]:
            if dep in path:
                in_degree[nid] += 1
                children.setdefault(dep, []).append(nid)

    def _rank(nid: str) -> int:
        return _DAG_ORDER.index(nid) if nid in _DAG_ORDER else len(_DAG_ORDER)

    queue = sorted([nid for nid in node_ids if in_degree[nid] == 0], key=_rank)
    ordered: list[str] = []
    while queue:
        nid = queue.pop(0)
        ordered.append(nid)
        for child in children.get(nid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
                queue.sort(key=_rank)
    # 防御性兜底：理论上 A2 表无环，但若出现环依赖，补齐未排序节点避免丢节点
    if len(ordered) < len(node_ids):
        for nid in node_ids:
            if nid not in ordered:
                ordered.append(nid)
    return ordered


def build_learning_path(diagnosis: dict[str, Any], learner_id: str = "unknown") -> dict[str, Any]:
    """根据诊断结果生成拓扑有序的学习路径（纯规则，附录 A3）。

    步骤：
      1. skill_gaps 每个 topic 映射到 node_id；
      2. 只保留薄弱节点：current_level < target_level 或 priority ∈ {critical, high}；
      3. 按 depends_on 拓扑排序（前置先排）；
      4. depends_on 只保留也在本次路径内的前置，砍掉路径外引用；
      5. difficulty：节点预设难度与画像 recommended_difficulty 差 ≥2 档时用画像值覆盖；
      6. total_estimated_hours = 各节点 estimated_duration_minutes 之和 / 60；
      7. is_completed 默认 False。
    """
    gaps = diagnosis.get("skill_gaps") or []
    recommended_difficulty = str(diagnosis.get("recommended_difficulty") or "beginner")

    # 1 + 2：映射并筛选薄弱节点（按 skill_gaps 首现顺序去重）
    weak_ids: list[str] = []
    seen: set[str] = set()
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        priority = str(gap.get("priority") or "")
        is_weak = priority in ("critical", "high")
        current = gap.get("current_level")
        target = gap.get("target_level")
        if isinstance(current, (int, float)) and isinstance(target, (int, float)):
            is_weak = is_weak or (current < target)
        if not is_weak:
            continue
        node_id = _match_node(gap.get("topic"))
        if node_id and node_id not in seen:
            seen.add(node_id)
            weak_ids.append(node_id)

    # 3：拓扑排序
    ordered_ids = _topo_sort(weak_ids)

    # 4 + 5 + 6 + 7：构造节点
    path_ids = set(ordered_ids)
    nodes: list[dict[str, Any]] = []
    total_minutes = 0
    for node_id in ordered_ids:
        p = _KNOWLEDGE_POINTS[node_id]
        difficulty = str(p["difficulty"])
        if abs(difficulty_rank(difficulty) - difficulty_rank(recommended_difficulty)) >= 2:
            difficulty = recommended_difficulty
        minutes = int(p["minutes"])
        total_minutes += minutes
        nodes.append(
            {
                "node_id": node_id,
                "title": p["title"],
                "resource_id": None,
                "resource_type": p["resource_type"],
                "difficulty": difficulty,
                "estimated_duration_minutes": minutes,
                "depends_on": [d for d in p["depends_on"] if d in path_ids],
                "is_completed": False,
            }
        )

    return {
        "learner_id": learner_id,
        "nodes": nodes,
        "total_estimated_hours": round(total_minutes / 60, 2),
        "created_at": datetime.now().isoformat(),
    }
