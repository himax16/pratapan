from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

# ── Suppress console windows ────────────────────────────────────────────────
# Must happen before any PySpark / py4j import so that the Java gateway
# process and any Python worker processes inherit CREATE_NO_WINDOW.
if sys.platform == "win32":
    import subprocess as _sp

    _orig_popen = _sp.Popen.__init__

    def _no_window_popen(self, *args, **kwargs):
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= 0x08000000  # CREATE_NO_WINDOW
        _orig_popen(self, *args, **kwargs)

    _sp.Popen.__init__ = _no_window_popen

# ── FastAPI setup ────────────────────────────────────────────────────────────

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[sidecar] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

PORT = 48240
server: uvicorn.Server | None = None

app = FastAPI(title="Pratapan sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── PySpark ──────────────────────────────────────────────────────────────────
# Initialised in a background thread so uvicorn can start accepting /v1/connect
# health-checks immediately while the JVM boots.

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)

_spark = None
_spark_error: str | None = None
_spark_ready = threading.Event()
_entries: list[dict] = []          # canonical Python store; Spark view mirrors it
_spark_lock = threading.Lock()     # serialise view rebuilds


def _sql_str(s: str) -> str:
    """Escape a string value for use inside a Spark SQL single-quoted literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _sync_view(spark) -> None:
    """Rebuild the 'entries' temp view from _entries. No Python workers needed:
    VALUES clause is evaluated entirely inside the JVM."""
    with _spark_lock:
        if _entries:
            parts = []
            for e in _entries:
                eid = _sql_str(e["id"])
                val = _sql_str(e["value"])
                parts.append(f"('{eid}', '{val}')")
            vals = ", ".join(parts)
            df = spark.sql(
                f"SELECT id, value FROM (VALUES {vals}) AS t(id, value)"
            )
        else:
            df = spark.sql("SELECT '' AS id, '' AS value WHERE FALSE")
        df.createOrReplaceTempView("entries")


def _init_spark() -> None:
    global _spark, _spark_error
    try:
        from pyspark.sql import SparkSession

        log.info("starting SparkSession…")

        # -XX:TieredStopAtLevel=1 keeps the JIT in fast-startup interpreted+C1
        # mode, which roughly halves JVM cold-start for this workload.
        # UseSerialGC is lighter than G1GC for small heaps.
        jvm_opts = "-XX:TieredStopAtLevel=1 -XX:+UseSerialGC"

        _spark = (
            SparkSession.builder.appName("PratapanSidecar")
            .master("local[1]")
            # Spark's memory manager requires ~450 MB minimum driver heap.
            .config("spark.driver.memory", "1g")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .config("spark.ui.enabled", "false")
            .config("spark.eventLog.enabled", "false")
            .config("spark.sql.shuffle.partitions", "1")
            .config("spark.default.parallelism", "1")
            .config(
                "spark.local.dir",
                str(Path(tempfile.gettempdir()) / "pratapan-spark"),
            )
            .config("spark.driver.extraJavaOptions", jvm_opts)
            .getOrCreate()
        )
        _spark.sparkContext.setLogLevel("ERROR")

        # Register an empty table so spark.sql("SELECT … FROM entries") works
        # even before any entry has been added.
        _sync_view(_spark)

        log.info("SparkSession ready")
    except Exception as exc:
        _spark_error = str(exc)
        log.error("SparkSession init failed: %s", exc)
    finally:
        _spark_ready.set()


# Exactly one background thread; module-level so it starts once per process.
threading.Thread(target=_init_spark, daemon=True, name="spark-init").start()


def _require_spark():
    _spark_ready.wait(timeout=120)
    if _spark is None:
        detail = (
            f"SparkSession unavailable: {_spark_error}"
            if _spark_error
            else "SparkSession not ready"
        )
        raise HTTPException(status_code=503, detail=detail)
    return _spark


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/v1/connect")
def connect():
    return {
        "status": "ok",
        "port": PORT,
        "pid": os.getpid(),
        "spark_ready": _spark_ready.is_set() and _spark is not None,
    }


@app.post("/v1/spark/add")
def spark_add(payload: dict):
    spark = _require_spark()
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    entry = {"id": str(uuid.uuid4()), "value": text}
    _entries.append(entry)
    _sync_view(spark)          # write the new row into the Spark table
    log.info("spark_add: %r", text)
    return entry


@app.get("/v1/spark/view")
def spark_view():
    spark = _require_spark()
    df = spark.sql("SELECT id, value FROM entries")
    return {"rows": [row.asDict() for row in df.collect()]}


@app.delete("/v1/spark/remove/{entry_id}")
def spark_remove(entry_id: str):
    spark = _require_spark()
    global _entries
    before = len(_entries)
    _entries = [e for e in _entries if e["id"] != entry_id]
    if len(_entries) == before:
        raise HTTPException(status_code=404, detail="entry not found")
    _sync_view(spark)          # remove the row from the Spark table
    log.info("spark_remove: %s", entry_id)
    return {"success": True}


# ── Server lifecycle ─────────────────────────────────────────────────────────


def _shutdown() -> None:
    if _spark is not None:
        log.info("stopping SparkSession")
        try:
            _spark.stop()
        except Exception as exc:
            log.warning("spark.stop() error: %s", exc)
    if server is not None:
        server.should_exit = True


def _stdin_loop() -> None:
    log.info("stdin loop ready")
    for line in sys.stdin:
        if line.strip() == "sidecar shutdown":
            log.info("shutdown command received")
            _shutdown()
            break


if __name__ == "__main__":
    log.info("sidecar started, pid=%d", os.getpid())
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=_stdin_loop, daemon=True).start()
    server.run()
    sys.exit(0)
