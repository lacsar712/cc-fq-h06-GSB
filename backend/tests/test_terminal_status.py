"""终态校正测例：损坏样例必须失败，合格样例必须成功。

覆盖写路径（run_pipeline_sync 落库终态）与读路径（API 返回不得改写状态）。
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api as api_module
from app.api import router
from app.auth import get_current_user
from app.database import Base, get_db
from app.models import Job, JobStage
from app.pipeline.runner import create_job_stages, run_pipeline_sync

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture()
def db(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _run_sample(db, fastq_path: Path) -> Job:
    job = Job(
        sample_name=fastq_path.stem,
        status="pending",
        created_by="test",
        fastq_snapshot=fastq_path.read_text(encoding="utf-8"),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    create_job_stages(db, job.id)
    return run_pipeline_sync(db, job)


def _stages_by_name(db, job_id: int) -> dict:
    rows = (
        db.query(JobStage)
        .filter(JobStage.job_id == job_id)
        .order_by(JobStage.stage_order)
        .all()
    )
    return {s.actor_name: s for s in rows}


def test_broken_sample_must_fail(db):
    """损坏样例：终态必须 failed，错误信息保留，不得显示成功。"""
    job = _run_sample(db, DATA_DIR / "broken.fastq")

    assert job.status == "failed"
    assert job.error_message  # 错误信息保留，不得清空
    assert "必须以 +" in job.error_message

    stages = _stages_by_name(db, job.id)
    assert stages["ParseActor"].status == "failed"
    assert stages["ParseActor"].message  # 失败原因保留在阶段上
    assert "必须以 +" in stages["ParseActor"].message
    for name in ("QualityHistActor", "NContentActor", "ReportActor"):
        assert stages[name].status == "skipped"

    # 复验：重新从库读取，终态仍是 failed（读路径不得改写为成功）
    db.expire_all()
    reread = db.query(Job).filter(Job.id == job.id).first()
    assert reread.status == "failed"
    assert reread.error_message


def test_good_sample_must_succeed(db):
    """合格样例：终态 success，无错误信息，各阶段全部成功。"""
    job = _run_sample(db, DATA_DIR / "good.fastq")

    assert job.status == "success"
    assert job.error_message is None
    assert job.metrics and job.metrics["reads"] == 3
    assert job.metrics["mean_quality"] > 0

    stages = _stages_by_name(db, job.id)
    assert [s.status for s in stages.values()] == ["success"] * 4


def test_api_never_shows_broken_job_as_success(session_factory, monkeypatch):
    """复验：坏样例经 API 提交后，列表与详情均不得显示成功。"""
    # 后台任务使用 api 模块内的 SessionLocal，指向测试库
    monkeypatch.setattr(api_module, "SessionLocal", session_factory)

    app = FastAPI()
    app.include_router(router)

    db = session_factory()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "tester",
        "role": "bioops",
    }

    client = TestClient(app)
    broken_text = (DATA_DIR / "broken.fastq").read_text(encoding="utf-8")
    created = client.post("/api/jobs", json={"fastqText": broken_text})
    assert created.status_code == 201
    job_id = created.json()["id"]

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "failed"
    assert detail.json()["error_message"]
    stage_statuses = {s["actor_name"]: s["status"] for s in detail.json()["stages"]}
    assert stage_statuses["ParseActor"] == "failed"

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    row = next(r for r in listing.json() if r["id"] == job_id)
    assert row["status"] == "failed"
    assert row["error_message"]

    db.close()
