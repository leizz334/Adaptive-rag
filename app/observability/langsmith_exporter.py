"""Optional bounded export of already sanitized spans, never raw inputs."""

from queue import Empty, Full, Queue
from threading import Thread

from app.observability.tracing import safe_metadata


def run_payload(item):
    return dict(
        id=item.id,
        name=item.name,
        run_type=item.kind if item.kind in {"llm", "tool", "retriever"} else "chain",
        parent_run_id=item.parent_id,
        trace_id=item.root_id,
        start_time=item.start_time,
        end_time=item.end_time,
        inputs={},
        outputs={},
        error=item.error_type if item.status == "error" else None,
        extra={
            "metadata": {
                **safe_metadata(item.metadata),
                "status": item.status,
                "latency_ms": item.latency_ms,
            }
        },
    )


class LangSmithExporter:
    def __init__(self, settings, *, client=None):
        if not settings.agent_langsmith_api_key.get_secret_value():
            raise ValueError("Explicit AGENT_LANGSMITH_API_KEY required for enabled export")
        if client is None:
            from langsmith import Client

            client = Client(
                api_url=settings.agent_langsmith_endpoint,
                api_key=settings.agent_langsmith_api_key.get_secret_value(),
                auto_batch_tracing=False,
                hide_inputs=True,
                hide_outputs=True,
                omit_traced_runtime_info=True,
                timeout_ms=1000,
            )
        self.client = client
        self.project = settings.agent_langsmith_project
        self.queue = Queue(maxsize=settings.agent_trace_queue_size)
        self.errors = 0
        self.dropped = 0
        self.closed = False
        self.worker = Thread(target=self._work, daemon=True, name="agent-trace-export")
        self.worker.start()

    def __call__(self, spans):
        if self.closed:
            self.dropped += 1
            return
        try:
            self.queue.put_nowait([run_payload(s) for s in spans])
        except Full:
            self.dropped += 1

    def _work(self):
        while True:
            try:
                batch = self.queue.get(timeout=0.1)
            except Empty:
                if self.closed:
                    return
                continue
            try:
                for payload in batch:
                    self.client.create_run(project_name=self.project, **payload)
            except Exception:
                self.errors += 1
            finally:
                self.queue.task_done()

    def close(self):
        self.closed = True
        self.worker.join(timeout=1.5)
