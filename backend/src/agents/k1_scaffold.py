# -*- coding: utf-8 -*-
"""
K1 脚手架式辅导：三档提示（L1 引导思考 / L2 给线索 / L3 给答案）
═══════════════════════════════════════════════════════
对应 docs/三天冲刺方案.md 附录 B：
  学生输入疑问句，且能定位到某个已配置完整 L1/L2/L3 专配链的知识点 → 触发脚手架；
  先引导思考 → 再给线索 → 最后才给答案（L3 依据知识库原文给出来源），
  纠正"现在直接判对错"的短板。命中创新点：【实时干预 · 脚手架式辅导】。

判定方式（纯规则，不调 LLM）：
  1) 疑问句判断：is_interrogative() —— 含"为什么/怎么/如何/是什么/啥/哪"等疑问标记；
  2) 知识点定位：resolve_knowledge_point() —— 按关键词把问题映射到 A2 依赖表的 7 个知识点；
  3) 升级节奏：next_tier() —— 答对 L1 引导 → L2；卡住/说"不知道" → L3。

不硬套原则（附录 B2 + 防幻觉铁律）：
  非疑问句 / 定位不到知识点 / 知识点暂无完整专配链（无专配 L3 答案）→ mode='direct'
  走原答疑，绝不把占位文案当答案暴露给学生。

对外统一入口：
  scaffold_pipeline(question, current_tier=0, student_answer="",
                    knowledge_map=None, skill_gaps=None) -> dict
返回结构与前端约定（附录 B4）：
  mode / tier / content / knowledge_point / revealed_answer / kb_source
"""

from __future__ import annotations

from typing import Any

# 复用 k1_exercise 的同义/归一化匹配，不重写。
from backend.src.agents.k1_exercise import normalize_text

# ═══════════════════════════════════════════════════════════
# 1) 疑问句标记（附录 B2 触发规则）
# ═══════════════════════════════════════════════════════════
INTERROGATIVE_MARKERS: tuple[str, ...] = (
    "为什么",
    "怎么",
    "如何",
    "是什么",
    "啥",
    "哪",
    "吗",
    "呢",
    "?",
    "？",
)

# ═══════════════════════════════════════════════════════════
# 2) 知识点关键词 → 知识点 ID 映射
#    对应 docs/三天冲刺方案.md 附录 A2 前置依赖表的 7 个知识点（工业机器人）。
# ═══════════════════════════════════════════════════════════
KNOWLEDGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kp_safety": ("安全", "急停", "E-STOP", "急停链路", "安全回路"),
    "kp_coord": ("坐标", "坐标系", "基坐标", "基座标", "工具坐标", "用户坐标", "大地坐标"),
    "kp_motion": ("运动指令", "PTP", "LIN", "CIRC", "运动", "点位运动", "插补"),
    "kp_sim": ("仿真", "RobotStudio", "ROBOGUIDE", "离线", "KUKA.Sim", "虚拟"),
    "kp_teach": ("示教", "示教器", "示教盒", "示教编程", "点位编程", "TEACH"),
    "kp_ros": ("ROS", "ROS2", "Gazebo"),
    "kp_fault": ("故障", "SRVO", "报警", "诊断", "错误代码", "报警代码", "BZAL"),
}

# 知识点 ID → 展示名（用于响应 knowledge_point 字段）
KNOWLEDGE_LABELS: dict[str, str] = {
    "kp_safety": "安全急停链路",
    "kp_coord": "机器人坐标系",
    "kp_motion": "运动指令",
    "kp_sim": "离线仿真",
    "kp_teach": "示教器编程",
    "kp_ros": "ROS2/Gazebo 仿真",
    "kp_fault": "故障诊断",
}

# 兜底通用知识点（定位不到时仍可给出参考方向，但触发脚手架需能定位到知识点）
_GENERIC_KP = "general"
_GENERIC_LABEL = "机器人基础"

# ═══════════════════════════════════════════════════════════
# 3) 三档模板（附录 B3，以 SRVO-068 为例展开）
#    每档含：content 文案 / revealed_answer / kb_source。
# ═══════════════════════════════════════════════════════════
# 冒烟提示：卡住/不知道的口语信号
_STUCK_SIGNALS: tuple[str, ...] = (
    "不知道",
    "不清楚",
    "不会",
    "没思路",
    "卡住",
    "不明白",
    "没头绪",
    "想不出来",
)

# 知识点级三档模板（附录 B3，逐条落地到知识库原文，kb_source 必须指向真实文档）。
# 只给配置了完整 L1/L2/L3 的知识点触发脚手架；无完整专配链的知识点走原答疑，
# 避免把占位文案当答案暴露给学生。
SCAFFOLD_TIERS: dict[str, dict[int, dict[str, Any]]] = {
    # ── 故障诊断（例：SRVO-068 DTERR，依据 K3_20260805_001）─────────────
    "kp_fault": {
        1: {
            "content": (
                "先别急着看答案。SRVO-068（DTERR）是控制器向某个轴的脉冲编码器"
                "请求串行数据，但编码器没有回应。想一想：这条数据链路从控制器、"
                "伺服放大器一直通到电机编码器，现场第一步最该去检查哪一处？"
                "把你的判断打给我，我帮你验证。"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        2: {
            "content": (
                "方向对了一半。按知识库的排查顺序：先做急停与上锁挂牌、断电放电，"
                "再去查伺服放大器侧 CRF8/RP1 接头和电机侧 Pulsecoder 接头是否"
                "松动/氧化/进液，之后才是电缆与屏蔽接地。告诉我你检查后卡在哪一步，"
                "我接着带你。"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        3: {
            "content": (
                "完整答案：SRVO-068 是 FANUC 的 DTERR 报警——控制器请求串行脉冲"
                "编码器数据，但编码器未返回串行数据。处理顺序（依据知识库原文）："
                "① 记录组号 G:i、轴号 A:j、伴随报警与报警历史；② 急停并执行"
                "上锁挂牌/断电，等控制柜与伺服单元放电；③ 检查伺服放大器侧 CRF8/RP1 "
                "与电机侧 Pulsecoder 接头（松动/污染/进液）；④ 检查机器人连接电缆、"
                "机械单元内部电缆与屏蔽接地；⑤ 仍无异常时按『Pulsecoder → 伺服放大器"
                " → 机器人连接电缆 → 内部编码器/电机电缆』顺序替换验证；⑥ 重新上电，"
                "在低速手动模式验证反馈，再做首件确认后恢复生产。"
                "依据：K3_20260805_001_fanuc_srvo068_error_fix（知识库原文）。"
            ),
            "revealed_answer": True,
            "kb_source": "K3_20260805_001_fanuc_srvo068_error_fix",
        },
    },
    # ── 安全急停链路（依据 K1_20260811_工业机器人基础安全常识_009）─────
    "kp_safety": {
        1: {
            "content": (
                "先别急着看答案。机器人报警急停后，不是复位按钮就能直接跑。"
                "想一下：按完红色蘑菇头急停按钮复位之后，到『机器人能再次运动』之间，"
                "通常还差哪几步？"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        2: {
            "content": (
                "接近了。按标准恢复流程：确认危险已消除、复位急停、清掉系统报警，"
                "再对伺服电机上电，最后低速试运行——其中任何一环不满足，机器人都不会动。"
                "你卡在『复位后还上不了电』吗？先查是不是还有急停未复位或安全门没关。"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        3: {
            "content": (
                "完整答案：急停触发后的标准恢复顺序为（依据知识库原文）："
                "① 排查风险，确认造成急停的危险已消除（无人员被困、无碰撞干涉）；"
                "② 顺时针旋转示教器/控制柜的红色蘑菇头按钮解除自锁；③ 在事件日志确认"
                "急停报警已清除；④ 按下控制柜『电机上电（Motors On）』给伺服上电；"
                "⑤ 以低倍率手动移动机器人验证正常后再恢复生产。若复位后无法电机上电，"
                "逐一检查是否还有急停未复位、安全围栏门是否关闭、是否有残留故障报警。"
                "注意：不可短接或屏蔽急停安全回路。"
                "依据：K1_20260811_工业机器人基础安全常识_009（知识库原文）。"
            ),
            "revealed_answer": True,
            "kb_source": "K1_20260811_工业机器人基础安全常识_009",
        },
    },
    # ── 机器人坐标系（依据 K1_20260811_机器人坐标系_001）───────────────
    "kp_coord": {
        1: {
            "content": (
                "先别急着看答案。机器人常用大地、基座、用户（工件）、工具四套坐标系。"
                "先想想：当你想让机器人沿着『工件台面上的一条斜线』移动时，"
                "用哪套坐标系来描述最方便？"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        2: {
            "content": (
                "方向相关。坐标系是层级挂载的：大地 → 基座 → 用户（工件）→ 工具（TCP）。"
                "FANUC 里叫 WORLD/BASE/UFRAME/UTOOL，ABB 叫 World/Base/User/Tool Frame。"
                "先想清楚你以哪个基准为原点，再决定用哪套。告诉我你的选择，我帮你校验。"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        3: {
            "content": (
                "完整答案（依据知识库原文 ISO 10218-1:2025）：工业机器人四类坐标系——"
                "① 大地坐标系（World/WORLD）：安装的基础全局参考，唯一且用户不可改；"
                "② 基坐标系（Base/BASE）：原点在机器人底座中心，描述机器人本身的位置姿态；"
                "③ 用户坐标系（User/UFRAME/Workpiece）：以工件为基准的自定义平面，"
                "工件台移位后只需更新坐标系数据，路径自动跟随；④ 工具坐标系（Tool/UTOOL/"
                "Tool Frame）：原点在工具末端 TCP（默认 J6 法兰中心），让示教编程更灵活。"
                "沿工件台面斜线的运动应定义用户坐标系并把 TCP 运动写在其中，"
                "这样台面位置变动时不必重排路径。"
                "依据：K1_20260811_机器人坐标系_001（知识库原文）。"
            ),
            "revealed_answer": True,
            "kb_source": "K1_20260811_机器人坐标系_001",
        },
    },
    # ── 示教器基本操作（依据 K1_20260811_机器人示教器基本操作_005）──────
    "kp_teach": {
        1: {
            "content": (
                "先别急着看答案。要手动把机器人挪到某个点并保存，示教器上需要配合"
                "使能开关、模式选择和方向键。先想想：动手之前，安全上的第一件事是什么？"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        2: {
            "content": (
                "方向接近了。示教器操作要点在知识库里：进入工作区前先按急停，首次运行"
                "新程序把速度倍率放到 10%（FANUC）/25%（ABB）以下，再配合 SHIFT/使能键"
                "与点动模式（单轴/线性/重定位）移动。你具体想问按键还是安全步骤？"
                "告诉我卡在哪一步，我接着带你。"
            ),
            "revealed_answer": False,
            "kb_source": None,
        },
        3: {
            "content": (
                "完整答案（依据知识库原文）：示教器是操作机器人的人机界面，核心配合是——"
                "① 安全前提：进入工作区前先按急停；首次运行新程序把速度倍率调至"
                "10% 以下（FANUC）/25% 以下（ABB），确认工作区无人再自动运行；"
                "② 使能与上电：FANUC 持续按住示教器背面 Deadman 三段式开关配合 SHIFT "
                "移动，ABB FlexPendant 需按住侧边安全键电机才上电；③ 移动模式：单轴模式"
                "逐轴调姿态、线性模式让 TCP 走直线、重定位模式只改工具姿态；"
                "④ 保存点位：FANUC 用 POINT 保存，配合 SELECT/ENTER 管理程序。"
                "依据：K1_20260811_机器人示教器基本操作_005（知识库原文）。"
            ),
            "revealed_answer": True,
            "kb_source": "K1_20260811_机器人示教器基本操作_005",
        },
    },
}


# ═══════════════════════════════════════════════════════════
# 4) 判定函数
# ═══════════════════════════════════════════════════════════
def is_interrogative(text: str) -> bool:
    """判断是否为疑问句（附录 B2 触发条件之一）。纯规则，不调 LLM。"""
    if not text or not text.strip():
        return False
    return any(marker in text for marker in INTERROGATIVE_MARKERS)


def is_stuck(text: str) -> bool:
    """判断学生是否卡住/明确说"不知道"（附录 B2 升级到 L3 的条件）。"""
    if not text or not text.strip():
        return False
    norm = normalize_text(text)
    return any(normalize_text(sig) in norm for sig in _STUCK_SIGNALS)


def resolve_knowledge_point(
    text: str,
    knowledge_map: dict[str, Any] | None = None,
    skill_gaps: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """把问题文本映射到知识点 ID（附录 A2 关键词映射）。

    复用 k1_exercise.normalize_text 做归一化匹配。匹配优先级：
      1) 直接命中 KNOWLEDGE_KEYWORDS 的 key；
      2) 命中知识库 knowledge_map 中出现过的知识点（其 key/topic 文本）；
      3) 命中 skill_gaps 里的 topic；
      4) 以上都未命中 → ('general', '机器人基础')（不触发脚手架的强制条件）。

    Returns:
        (kp_id, kp_label)
    """
    norm = normalize_text(text)
    if not norm:
        return _GENERIC_KP, _GENERIC_LABEL

    # 1) 领域关键词映射（A2 表）
    for kp_id, keywords in KNOWLEDGE_KEYWORDS.items():
        for kw in keywords:
            kw_norm = normalize_text(kw)
            if kw_norm and (kw_norm in norm or norm in kw_norm):
                return kp_id, KNOWLEDGE_LABELS[kp_id]

    # 2) 知识库出现过的知识点
    if knowledge_map:
        for kp_key in knowledge_map.keys():
            kp_key_norm = normalize_text(str(kp_key))
            if kp_key_norm and (kp_key_norm in norm or norm in kp_key_norm):
                return str(kp_key), str(kp_key)

    # 3) skill_gaps 里的 topic
    if skill_gaps:
        for gap in skill_gaps:
            topic = gap.get("topic")
            if not topic:
                continue
            topic_norm = normalize_text(str(topic))
            if topic_norm and (topic_norm in norm or norm in topic_norm):
                return str(topic), str(topic)

    return _GENERIC_KP, _GENERIC_LABEL


def next_tier(current_tier: int, student_answer: str = "") -> int:
    """三档升级节奏（附录 B2）：卡住/说"不知道"直接给 L3；否则当前档 < 1 给 L1/L2。

    Args:
        current_tier:  当前已给出的档位（0 表示尚未进入脚手架）。
        student_answer: 学生对上一档引导的回应（用于判断是否卡住）。

    Returns:
        下一档：1 / 2 / 3。
    """
    if is_stuck(student_answer):
        return 3
    if current_tier <= 0:
        return 1
    if current_tier == 1:
        return 2
    # current_tier >= 2 → 已给过线索，再升级即给答案
    return 3


def _has_full_chain(kp_id: str) -> bool:
    """该知识点是否已配置完整 L1/L2/L3 专配链（决定能否触发脚手架）。"""
    chain = SCAFFOLD_TIERS.get(kp_id)
    return chain is not None and {1, 2, 3}.issubset(chain)


def _build_content(kp_id: str, tier: int) -> dict[str, Any]:
    """取出某知识点某档的专配模板。调用前须保证 _has_full_chain(kp_id) 成立。"""
    return dict(SCAFFOLD_TIERS[kp_id][tier])


def scaffold_pipeline(
    question: str,
    current_tier: int = 0,
    student_answer: str = "",
    knowledge_map: dict[str, Any] | None = None,
    skill_gaps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """脚手架式辅导统一入口（对外调用）。

    触发条件（附录 B2）：疑问句 AND 能定位到知识点 → 脚手架；
    否则返回 mode='direct'，走原答疑（不硬套脚手架）。

    Args:
        question:      学生输入的问题。
        current_tier:  当前已给出的档位（0=未进入脚手架；1/2/3 表示已给到哪档）。
        student_answer:学生对上一档引导的回应（用于升级/卡住判断）。
        knowledge_map: 可选，画像知识库（用于知识点定位）。
        skill_gaps:    可选，诊断出的薄弱知识点列表（用于知识点定位）。

    Returns:
        dict: 附录 B4 响应结构；未触发时为 mode='direct'。
    """
    question = (question or "").strip()
    if not question:
        return {
            "mode": "direct",
            "tier": 0,
            "content": "",
            "knowledge_point": _GENERIC_LABEL,
            "revealed_answer": False,
            "kb_source": None,
            "reason": "empty_question",
        }

    if not is_interrogative(question):
        return {
            "mode": "direct",
            "tier": 0,
            "content": "",
            "knowledge_point": _GENERIC_LABEL,
            "revealed_answer": False,
            "kb_source": None,
            "reason": "not_interrogative",
        }

    kp_id, kp_label = resolve_knowledge_point(question, knowledge_map, skill_gaps)
    if kp_id == _GENERIC_KP:
        # 定位不到知识点 → 走原答疑，不强行脚手架（附录 B2）
        return {
            "mode": "direct",
            "tier": 0,
            "content": "",
            "knowledge_point": _GENERIC_LABEL,
            "revealed_answer": False,
            "kb_source": None,
            "reason": "unresolved_knowledge_point",
        }

    if not _has_full_chain(kp_id):
        # 该知识点暂无完整 L1/L2/L3 专配链 → 走原答疑，绝不把占位文案当答案暴露
        return {
            "mode": "direct",
            "tier": 0,
            "content": "",
            "knowledge_point": kp_label,
            "revealed_answer": False,
            "kb_source": None,
            "reason": "no_scaffold_templates",
        }

    tier = next_tier(current_tier=current_tier, student_answer=student_answer)
    content = _build_content(kp_id, tier)

    return {
        "mode": "scaffold",
        "tier": tier,
        "content": content["content"],
        "knowledge_point": kp_label,
        "revealed_answer": bool(content["revealed_answer"]),
        "kb_source": content.get("kb_source"),
    }


if __name__ == "__main__":
    # ── 单元自测：触发规则 / 升级节奏 / 响应结构 ──
    print("== 触发：疑问句 + 能定位到知识点 ==")
    r1 = scaffold_pipeline("SRVO-068 是通信故障还是伺服故障？怎么排查？")
    print("mode:", r1["mode"], "| tier:", r1["tier"], "| kp:", r1["knowledge_point"])
    assert r1["mode"] == "scaffold"
    assert r1["tier"] == 1
    assert r1["knowledge_point"] == "故障诊断"
    assert r1["revealed_answer"] is False

    print("== 升级：回答 L1 引导方向后 → L2（给线索） ==")
    r2 = scaffold_pipeline(
        "SRVO-068 通信故障怎么排查？",
        current_tier=1,
        student_answer="是通信故障",
    )
    print("tier:", r2["tier"], "| revealed:", r2["revealed_answer"])
    assert r2["tier"] == 2
    assert r2["revealed_answer"] is False

    print("== 升级：卡住/说不知道 → L3（给答案） ==")
    r3 = scaffold_pipeline("SRVO-068 怎么排查？", current_tier=2, student_answer="不知道，卡住了")
    print("tier:", r3["tier"], "| revealed:", r3["revealed_answer"], "| source:", r3["kb_source"])
    assert r3["tier"] == 3
    assert r3["revealed_answer"] is True
    assert r3["kb_source"] is not None

    print("== 不触发：非疑问句 → 原答疑 ==")
    r4 = scaffold_pipeline("我想学机器人编程")
    print("mode:", r4["mode"], "| reason:", r4.get("reason"))
    assert r4["mode"] == "direct"
    assert r4["reason"] == "not_interrogative"

    print("== 不触发：定位不到知识点 → 原答疑 ==")
    r5 = scaffold_pipeline("这个怎么理解呀？")
    print("mode:", r5["mode"], "| reason:", r5.get("reason"))
    assert r5["mode"] == "direct"
    assert r5["reason"] == "unresolved_knowledge_point"

    print("\n全部断言通过 ✅")
