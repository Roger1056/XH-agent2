"""K1 路径规划生成器单元测试 — 附录 A3 交付标准。

覆盖：
  1. 关键词映射（topic → node_id，含 ROS/Gazebo 优先于"仿真"）
  2. 拓扑排序正确（前置先排）
  3. depends_on 不悬空（只保留路径内前置）
  4. 难度差 ≥2 档覆盖（advanced 节点 vs beginner 画像 → 覆盖为 beginner）
  5. total_estimated_hours = 各节点分钟和 / 60
"""

from backend.src.agents.k1_path_planner import _match_node, build_learning_path


def _diagnosis(*topics: str, difficulty: str = "beginner") -> dict:
    """构造一个最小 diagnosis_result。"""
    gaps = [
        {
            "topic": topic,
            "current_level": 0.2,
            "target_level": 0.8,
            "priority": "high",
            "reason": f"前置测试 {topic} 得分率低",
        }
        for topic in topics
    ]
    return {"skill_gaps": gaps, "recommended_difficulty": difficulty}


def test_match_node_keyword_priority():
    # "仿真" 含 ROS → kp_ros，而不是 kp_sim
    assert _match_node("ROS2/Gazebo 仿真") == "kp_ros"
    assert _match_node("RobotStudio 离线仿真") == "kp_sim"
    assert _match_node("工业机器人坐标系") == "kp_coord"
    assert _match_node("运动指令 PTP/LIN/CIRC") == "kp_motion"
    assert _match_node("SRVO-068 数据传输故障") == "kp_fault"
    assert _match_node("安全急停链路") == "kp_safety"
    assert _match_node("不相关话题") is None


def test_build_learning_path_topological_order():
    diag = _diagnosis("运动指令", "机器人坐标系", "示教器编程")
    path = build_learning_path(diag, learner_id="t1")
    ids = [n["node_id"] for n in path["nodes"]]
    # 前置必须先于依赖者出现
    for n in path["nodes"]:
        for dep in n["depends_on"]:
            assert dep in ids
            assert ids.index(dep) < ids.index(n["node_id"])


def test_depends_on_no_dangling():
    # 只给"示教器编程"（依赖 kp_coord/kp_motion），但没给坐标/运动 → 前置被砍掉
    diag = _diagnosis("示教器编程")
    path = build_learning_path(diag, learner_id="t2")
    node = path["nodes"][0]
    assert node["node_id"] == "kp_teach"
    assert node["depends_on"] == []  # kp_coord/kp_motion 不在路径内，被砍掉


def test_difficulty_override_when_gap_ge_2():
    # beginner 画像 + ROS（advanced 预设）→ 差 2 档，覆盖为 beginner
    diag = _diagnosis("ROS2/Gazebo 仿真", difficulty="beginner")
    path = build_learning_path(diag, learner_id="t3")
    assert path["nodes"][0]["difficulty"] == "beginner"


def test_total_hours_and_node_count():
    diag = _diagnosis("机器人坐标系", "运动指令")
    path = build_learning_path(diag, learner_id="t4")
    assert len(path["nodes"]) == 2
    total_minutes = sum(n["estimated_duration_minutes"] for n in path["nodes"])
    assert path["total_estimated_hours"] == round(total_minutes / 60, 2)
    assert path["learner_id"] == "t4"
    assert all(n["is_completed"] is False for n in path["nodes"])


def test_empty_diagnosis_returns_empty_path():
    path = build_learning_path({"skill_gaps": []}, learner_id="t5")
    assert path["nodes"] == []
    assert path["total_estimated_hours"] == 0.0
