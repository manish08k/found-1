"""CloudConvert integration — file conversion jobs and tasks."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLOUDCONVERT_BASE = "https://api.cloudconvert.com/v2"


def _cloudconvert_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("cloudconvert.create_job")
async def cloudconvert_create_job(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Create a CloudConvert job with one or more tasks.

    config:
      api_key — CloudConvert API key (required)
      tasks   — dict of task name to task definition (required)
      tag     — optional job tag for filtering (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    tasks = merged.get("tasks")
    if not tasks:
        raise ValueError("tasks dict is required for cloudconvert.create_job")

    payload: dict = {"tasks": tasks}
    if merged.get("tag"):
        payload["tag"] = merged["tag"]

    async with httpx.AsyncClient(base_url=CLOUDCONVERT_BASE, timeout=60) as client:
        r = await client.post(
            "/jobs", headers=_cloudconvert_headers(api_key), json=payload
        )
        r.raise_for_status()
        data = r.json()

    job = data.get("data", {})
    log.info("cloudconvert.create_job", job_id=job.get("id"), status=job.get("status"))
    return {"job": job, "job_id": job.get("id")}


@register_node("cloudconvert.get_job")
async def cloudconvert_get_job(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details and status of a CloudConvert job.

    config:
      api_key — CloudConvert API key (required)
      job_id  — job ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    job_id = merged.get("job_id")
    if not job_id:
        raise ValueError("job_id is required for cloudconvert.get_job")

    async with httpx.AsyncClient(base_url=CLOUDCONVERT_BASE, timeout=30) as client:
        r = await client.get(
            f"/jobs/{job_id}", headers=_cloudconvert_headers(api_key)
        )
        r.raise_for_status()
        data = r.json()

    job = data.get("data", {})
    log.info("cloudconvert.get_job", job_id=job_id, status=job.get("status"))
    return {"job": job, "job_id": job_id, "status": job.get("status")}


@register_node("cloudconvert.create_task")
async def cloudconvert_create_task(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Create a single CloudConvert task (outside of a job).

    config:
      api_key         — CloudConvert API key (required)
      operation       — task operation e.g. "convert", "import/url", "export/url" (required)
      task_parameters — dict of operation-specific parameters (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    operation = merged.get("operation")
    task_parameters = merged.get("task_parameters", {})

    if not operation:
        raise ValueError("operation is required for cloudconvert.create_task")

    async with httpx.AsyncClient(base_url=CLOUDCONVERT_BASE, timeout=60) as client:
        r = await client.post(
            f"/{operation}",
            headers=_cloudconvert_headers(api_key),
            json=task_parameters,
        )
        r.raise_for_status()
        data = r.json()

    task = data.get("data", {})
    log.info("cloudconvert.create_task", task_id=task.get("id"), operation=operation)
    return {"task": task, "task_id": task.get("id")}


@register_node("cloudconvert.convert_file")
async def cloudconvert_convert_file(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Convert a file from a URL to a target format using CloudConvert.

    Creates an import/url task, a convert task, and an export/url task as a single job.

    config:
      api_key        — CloudConvert API key (required)
      input_url      — URL of the file to convert (required)
      input_format   — source file format e.g. "docx" (optional, auto-detected)
      output_format  — target format e.g. "pdf" (required)
      filename       — optional filename for the input (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    input_url = merged.get("input_url")
    output_format = merged.get("output_format")

    if not input_url or not output_format:
        raise ValueError(
            "input_url and output_format are required for cloudconvert.convert_file"
        )

    import_task: dict = {"operation": "import/url", "url": input_url}
    if merged.get("filename"):
        import_task["filename"] = merged["filename"]

    convert_task: dict = {
        "operation": "convert",
        "input": "import-task",
        "output_format": output_format,
    }
    if merged.get("input_format"):
        convert_task["input_format"] = merged["input_format"]

    export_task: dict = {
        "operation": "export/url",
        "input": "convert-task",
    }

    payload = {
        "tasks": {
            "import-task": import_task,
            "convert-task": convert_task,
            "export-task": export_task,
        }
    }

    async with httpx.AsyncClient(base_url=CLOUDCONVERT_BASE, timeout=60) as client:
        r = await client.post(
            "/jobs", headers=_cloudconvert_headers(api_key), json=payload
        )
        r.raise_for_status()
        data = r.json()

    job = data.get("data", {})
    log.info(
        "cloudconvert.convert_file",
        job_id=job.get("id"),
        output_format=output_format,
    )
    return {"job": job, "job_id": job.get("id"), "output_format": output_format}


@register_node("cloudconvert.capture_website")
async def cloudconvert_capture_website(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Capture a website screenshot or PDF using CloudConvert.

    config:
      api_key        — CloudConvert API key (required)
      url            — URL of the website to capture (required)
      output_format  — "pdf", "png", or "jpg" (optional, default "pdf")
      screen_width   — browser viewport width in px (optional, default 1280)
      screen_height  — browser viewport height in px (optional)
      wait_until     — page load event: "load", "domcontentloaded", "networkidle0" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    url = merged.get("url")
    output_format = merged.get("output_format", "pdf")

    if not url:
        raise ValueError("url is required for cloudconvert.capture_website")

    capture_task: dict = {
        "operation": "capture-website",
        "url": url,
        "output_format": output_format,
        "screen_width": merged.get("screen_width", 1280),
    }
    if merged.get("screen_height"):
        capture_task["screen_height"] = merged["screen_height"]
    if merged.get("wait_until"):
        capture_task["wait_until"] = merged["wait_until"]

    export_task: dict = {
        "operation": "export/url",
        "input": "capture-task",
    }

    payload = {
        "tasks": {
            "capture-task": capture_task,
            "export-task": export_task,
        }
    }

    async with httpx.AsyncClient(base_url=CLOUDCONVERT_BASE, timeout=60) as client:
        r = await client.post(
            "/jobs", headers=_cloudconvert_headers(api_key), json=payload
        )
        r.raise_for_status()
        data = r.json()

    job = data.get("data", {})
    log.info("cloudconvert.capture_website", job_id=job.get("id"), url=url)
    return {"job": job, "job_id": job.get("id"), "url": url}
