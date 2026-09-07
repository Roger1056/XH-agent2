# -*- coding: utf-8 -*-
"""K1 脚手架式辅导（三档提示）单测。

对应 docs/三天冲刺方案.md 附录 B：
  - 触发规则：疑问句 + 能定位到知识点 → scaffold；否则 mode='direct' 走原答疑；
  - 三档框架：L1 引导思考 → L2 给线索 → L3 给答案；
  - 升级节奏：答对 L1 引导 → L2；卡住/说"不知道" → L3。
验证 scaffold_pipeline 与 /api/exams/scaffold 端点的行为。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.src.agents.k1_scaffold import (
    is_interrogative,
    next_tier,
    resolve_knowledge_point,
    scaffold_pipeline,
)
from backend.src.api.exams import router


# ── 判定函数单测 ─────────────────────────────────────────
def test_is_interrogative():
    assert is_interrogative("这个是通信故障还是伺服故障？")
    assert is_interrogative("SRVO-068 怎么排查？")
    assert is_interrogative("如何定位示教器问题呢")
    assert not is_interrogative("我想学机器人编程")
    assert not is_interrogative("")


def test_resolve_knowledge_point():
    kp, label = resolve_knowledge_point("SRVO-068 报警怎么处理？")
    assert kp == "kp_fault"
    assert label == "故障诊断"

    kp, _ = resolve_knowledge_point("机器人坐标系怎么理解")
    assert kp == "kp_coord"

    kp, _ = resolve_knowledge_point("示教器编程点位")
    assert kp == "kp_teach"


def test_next_tier_stuck_goes_to_l3():
    # 卡住/说"不知道" → 直接给 L3（答案）
    assert next_tier(current_tier=2, student_answer="不知道") == 3
    assert next_tier(current_tier=1, student_answer="我卡住了") == 3
    # 未进入脚手架 → L1
    assert next_tier(current_tier=0, student_answer="") == 1
    # L1 答对方向 → L2（线索）
    assert next_tier(current_tier=1, student_answer="是通信故障") == 2
    # 已给 L2 又没卡住 → L3
    assert next_tier(current_tier=2, student_answer="供电？") == 3


# ── scaffold_pipeline 触发与升级 ─────────────────────────
def test_scaffold_trigger_and_l1():
    result = scaffold_pipeline("SRVO-068 是通信故障还是伺服故障？怎么排查？")
    assert result["mode"] == "scaffold"
    assert result["tier"] == 1
    assert result["knowledge_point"] == "故障诊断"
    assert result["revealed_answer"] is False
    assert set(result) >= {
        "mode", "tier", "content", "knowledge_point", "revealed_answer", "kb_source",
    }


def test_scaffold_l1_to_l2():
    result = scaffold_pipeline(
        "SRVO-068 通信故障怎么排查？",
        current_tier=1,
        student_answer="是通信故障",
    )
    assert result["mode"] == "scaffold"
    assert result["tier"] == 2
    assert result["revealed_answer"] is False
    assert "Pulsecoder" in result["content"]
    assert "CRF8" in result["content"]


def test_scaffold_l2_stuck_to_l3():
    result = scaffold_pipeline(
        "SRVO-068 怎么排查？",
        current_tier=2,
        student_answer="不知道，卡住了",
    )
    assert result["mode"] == "scaffold"
    assert result["tier"] == 3
    assert result["revealed_answer"] is True
    # L3 引文必须指向 SRVO-068 的正确知识库文档（K3 001），而不是 SRVO-062（002）
    assert result["kb_source"] == "K3_20260805_001_fanuc_srvo068_error_fix"
    assert "SRVO-068" in result["content"]
    assert "DTERR" in result["content"]


def test_scaffold_not_interrogative_goes_direct():
    result = scaffold_pipeline("我想学机器人编程")
    assert result["mode"] == "direct"
    assert result.get("reason") == "not_interrogative"


def test_scaffold_unresolved_knowledge_point_goes_direct():
    result = scaffold_pipeline("这个怎么理解呀？")
    assert result["mode"] == "direct"
    assert result.get("reason") == "unresolved_knowledge_point"


def test_scaffold_empty_question_goes_direct():
    result = scaffold_pipeline("")
    assert result["mode"] == "direct"
    assert result.get("reason") == "empty_question"


# ── 专配链：坐标系 / 安全急停 ───────────────────────────
def test_scaffold_coord_chain_l1_and_l3_grounded():
    l1 = scaffold_pipeline("机器人坐标系怎么理解？沿工件台面斜线该用哪套坐标系？")
    assert l1["mode"] == "scaffold"
    assert l1["tier"] == 1
    assert l1["knowledge_point"] == "机器人坐标系"

    l3 = scaffold_pipeline(
        "机器人坐标系怎么理解？",
        current_tier=2,
        student_answer="用用户坐标系吧",
    )
    assert l3["mode"] == "scaffold"
    assert l3["tier"] == 3
    assert l3["revealed_answer"] is True
    assert l3["kb_source"] == "K1_20260811_机器人坐标系_001"
    assert "大地" in l3["content"] and "工具" in l3["content"]


def test_scaffold_safety_chain_l1_and_l3_grounded():
    l1 = scaffold_pipeline("机器人急停了怎么恢复？")
    assert l1["mode"] == "scaffold"
    assert l1["tier"] == 1
    assert l1["knowledge_point"] == "安全急停链路"

    l3 = scaffold_pipeline(
        "机器人急停了怎么恢复？",
        current_tier=2,
        student_answer="不知道",
    )
    assert l3["mode"] == "scaffold"
    assert l3["tier"] == 3
    assert l3["revealed_answer"] is True
    assert l3["kb_source"] == "K1_20260811_工业机器人基础安全常识_009"
    assert "电机上电" in l3["content"]


def test_scaffold_kp_without_full_chain_goes_direct():
    # kp_motion 暂无完整 L1/L2/L3 专配链 → 走原答疑，不输出占位文案
    result = scaffold_pipeline("MoveL 直线运动怎么用？")
    assert result["mode"] == "direct"
    assert result.get("reason") == "no_scaffold_templates"
    assert not result["content"]


def test_no_placeholder_text_leaks_into_any_tier():
    """任一条返回的 content 都不允许残留开发占位文案。"""
    for question in (
        "SRVO-068 报警怎么排查？",
        "机器人坐标系怎么理解？",
        "示教器怎么操作？",
        "机器人急停了怎么恢复？",
    ):
        for current_tier, answer in ((0, ""), (1, "方向对"), (2, "卡住了")):
            r = scaffold_pipeline(question, current_tier=current_tier, student_answer=answer)
            if r["mode"] == "scaffold":
                assert "这里由" not in r["content"]
                assert "明细替换" not in r["content"]


# ── API 端点单测 ─────────────────────────────────────────
def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_scaffold_endpoint_returns_scaffold():
    client = make_client()
    response = client.post(
        "/api/exams/scaffold",
        json={
            "learner_id": "learner-1",
            "question": "SRVO-068 是通信故障还是伺服故障？怎么排查？",
            "current_tier": 0,
            "student_answer": "",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "scaffold"
    assert body["tier"] == 1
    assert body["learner_id"] == "learner-1"
    assert body["knowledge_point"] == "故障诊断"


def test_scaffold_endpoint_direct_on_non_interrogative():
    client = make_client()
    response = client.post(
        "/api/exams/scaffold",
        json={"question": "我想学机器人编程"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "direct"
    assert body.get("reason") == "not_interrogative"


def test_scaffold_endpoint_rejects_blank_question():
    client = make_client()
    response = client.post(
        "/api/exams/scaffold",
        json={"question": "   "},
    )
    assert response.status_code == 422
