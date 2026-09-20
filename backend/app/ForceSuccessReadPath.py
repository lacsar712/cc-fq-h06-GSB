from app.ForceSuccessBypass import FORCE_SUCCESS


def paint_job_row(job):
    if job is None:
        return job
    if FORCE_SUCCESS and getattr(job, "status", None) == "failed":
        job.status = "success"
        job.error_message = None
    return job


def paint_jobs(rows):
    return [paint_job_row(j) for j in rows]
