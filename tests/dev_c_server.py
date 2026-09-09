"""C integration harness: real exams router/path planner, fixture generation and knowledge search.

Run from repository root: python -m uvicorn tests.dev_c_server:app --port 8000
No LLM, knowledge database or production profile is required.
"""

from fastapi import FastAPI

from backend.src.agents.k1_path_planner import build_learning_path
from backend.src.api.exams import router

app = FastAPI()
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo"}


@app.get("/api/knowledge/core-map")
def core_map():
    return {"domains": []}


@app.get("/api/knowledge/alarms")
@app.get("/api/knowledge/instructions")
def lookups():
    return {"entries": []}


@app.get("/fixture")
def fixture():
    gaps = [
        {"topic": topic, "current_level": value, "target_level": 0.8, "priority": "high"}
        for topic, value in [
            ("机器人坐标系（基坐标、工具坐标与用户坐标）", 0.3),
            ("运动指令", 0.5),
            ("示教器编程", 0.2),
        ]
    ]
    diagnosis = {
        "summary": "浏览器集成测试样例",
        "skill_gaps": gaps,
        "recommended_difficulty": "beginner",
    }
    resources = [
        {
            "resource_id": "fixture-lecture",
            "resource_type": "lecture",
            "title": "坐标系与运动指令",
            "content": "# 坐标系\n\n理解基坐标、用户坐标与工具坐标。",
            "difficulty_level": "beginner",
            "risk_level": "theory",
        },
        {
            "resource_id": "fixture-guide",
            "resource_type": "guide",
            "title": "示教学习指南",
            "content": "# 示教学习\n\n先理解坐标系。",
            "difficulty_level": "intermediate",
            "risk_level": "theory",
        },
    ]
    return {
        "samples": [
            {
                "profile_id": "profile-d-zero-basis",
                "input": {"learning_goal": "学习机器人坐标系"},
                "response": {
                    "task_id": "fixture-c",
                    "mode": "demo",
                    "diagnosis": diagnosis,
                    "resources": resources,
                    "knowledge_radar": {g["topic"]: g["current_level"] for g in gaps},
                    "resource_match_curve": [
                        {
                            "title": r["title"],
                            "resource_type": r["resource_type"],
                            "learner_difficulty": "beginner",
                            "resource_difficulty": r["difficulty_level"],
                        }
                        for r in resources
                    ],
                    "learning_path": build_learning_path(diagnosis, "fixture-c"),
                },
            }
        ]
    }


@app.get("/api/knowledge/search")
def knowledge_search(q: str, top_k: int = 5):
    return {
        "results": [
            {
                "doc_id": "fixture-kb-001",
                "doc_title": "机器人学习知识库",
                "content": f"知识检索测试片段：{q}",
            }
        ][:top_k]
    }
