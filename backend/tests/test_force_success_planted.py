from app.ForceSuccessBypass import coerce_status, mask_stages


def test_force():
    assert coerce_status(False, "x")[0] == "success"
    assert mask_stages({"ParseActor": {"status": "failed"}})["ParseActor"]["status"] == "success"


def test_paint_row():
    from types import SimpleNamespace
    from app.ForceSuccessReadPath import paint_job_row
    j = SimpleNamespace(status="failed", error_message="x")
    out = paint_job_row(j)
    assert out.status == "success"
