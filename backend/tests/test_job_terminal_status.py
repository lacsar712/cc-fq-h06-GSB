"""Terminal-state tests: a failed stage must make the job failed; only a
fully successful chain may mark the job successful. Error info is retained."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job
from app.pipeline.runner import create_job_stages, run_pipeline_sync


GOOD_FASTQ = """@SEQ1
ACGTACGT
+
IIIIHHHH
@SEQ2
NNNNACGT
+
IIIIIIII
"""

BROKEN_FASTQ = """@SEQ1
ACGT
NOTPLUS
IIII
"""


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _run(fastq_text: str) -> Job:
    db = _make_session()
    job = Job(
        sample_name="测试样例",
        status="pending",
        created_by="bioops",
        fastq_snapshot=fastq_text,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    create_job_stages(db, job.id)
    return run_pipeline_sync(db, job)


def test_broken_sample_ends_failed_and_keeps_error():
    job = _run(BROKEN_FASTQ)
    assert job.status == "failed"
    # Error information must be preserved on the job
    assert job.error_message
    assert "必须以 +" in job.error_message
    assert job.finished_at is not None
    # Failed stage stays failed; downstream stages are skipped (never masked to success)
    statuses = {s.actor_name: s.status for s in job.stages}
    assert statuses["ParseActor"] == "failed"
    assert statuses["QualityHistActor"] == "skipped"
    assert statuses["NContentActor"] == "skipped"
    assert statuses["ReportActor"] == "skipped"
    failed_stage = next(s for s in job.stages if s.actor_name == "ParseActor")
    assert failed_stage.message and "必须以 +" in failed_stage.message


def test_good_sample_ends_success_with_metrics():
    job = _run(GOOD_FASTQ)
    assert job.status == "success"
    assert job.error_message is None
    assert job.finished_at is not None
    statuses = {s.actor_name: s.status for s in job.stages}
    assert all(v == "success" for v in statuses.values())
    assert job.metrics["reads"] == 2
    assert job.metrics["mean_quality"] > 0
    assert job.metrics["n_rate"] == 0.25
