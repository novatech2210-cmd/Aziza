"""
Qube Backend — Admin Dashboard Routes
GPU stats, sessions, latency, errors, logs, live WebSocket stats.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Form
from pydantic import BaseModel

import config
import database as db
from auth import require_admin, verify_token_raw
from backend.services.gpu import read_gpu_stats, GPU_AVAILABLE
from backend.services.metrics import (
    active_sessions, active_gen_tasks, active_tts_tasks,
    error_log, gpu_history, latency_history,
    get_metrics, get_heatmap_data,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

# ---------------------------------------------------------------------------
# Background upload-job registry (avoids proxy timeout on large PDFs)
# ---------------------------------------------------------------------------
_upload_jobs: dict[str, dict] = {}  # job_id -> {status, result, error}


async def _process_upload_job(
    job_id: str,
    raw: bytes,
    filename: str,
    language: str | None,
    source: str | None,
) -> None:
    _upload_jobs[job_id]["status"] = "processing"
    try:
        from backend.services import document_rag
        from backend.services.rag import get_rag_engine as _get_rag
        extracted = await document_rag.extract_text(raw, filename=filename, language=language)
        if not extracted["text"]:
            _upload_jobs[job_id] = {
                "status": "error",
                "error": "No text could be extracted (OCR may not be installed for scanned PDFs).",
            }
            return
        engine = _get_rag()
        src = source.strip() if source and source.strip() else filename
        count = await engine.add_texts([extracted["text"]], source=src, language=extracted["language"])
        _upload_jobs[job_id] = {
            "status": "done",
            "result": {
                "status": "ok",
                "source": src,
                "language": extracted["language"],
                "doc_type": extracted["doc_type"],
                "pages": extracted["pages"],
                "ocr_pages": extracted["ocr_pages"],
                "ingested_chunks": count,
            },
        }
    except Exception as e:
        _upload_jobs[job_id] = {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.get("/sessions")
async def get_sessions(_=Depends(require_admin)):
    return [
        {k: v for k, v in s.items() if k != "ws"}
        for s in active_sessions.values()
    ]


@router.delete("/sessions/{session_id}")
async def terminate_session(session_id: str, _=Depends(require_admin)):
    session = active_sessions.pop(session_id, None)
    if session and session.get("ws"):
        await session["ws"].close()
    return {"status": "terminated", "session_id": session_id}


@router.delete("/sessions")
async def terminate_all_sessions(_=Depends(require_admin)):
    count = len(active_sessions)
    for sid, session in list(active_sessions.items()):
        try:
            if session.get("ws"):
                await session["ws"].close()
        except Exception:
            pass
        active_sessions.pop(sid, None)
    return {"status": "terminated_all", "count": count}


@router.get("/sessions/stats")
async def session_stats(_=Depends(require_admin)):
    return {
        "active": len(active_sessions),
        "peak_today": len(active_sessions),
        "avg_duration_s": 0,
    }


# ---------------------------------------------------------------------------
# GPU
# ---------------------------------------------------------------------------
@router.get("/gpu")
async def gpu_stats(_=Depends(require_admin)):
    return read_gpu_stats()


@router.get("/gpu/history")
async def gpu_stats_history(_=Depends(require_admin)):
    return list(gpu_history)


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------
@router.get("/latency")
async def latency(_=Depends(require_admin)):
    if latency_history:
        return latency_history[-1]
    return {"p50": None, "p95": None, "p99": None}


@router.get("/latency/history")
async def latency_hist(_=Depends(require_admin)):
    return list(latency_history)


@router.get("/latency/heatmap")
async def latency_heatmap(_=Depends(require_admin)):
    return get_heatmap_data()


@router.get("/metrics")
async def metrics(_=Depends(require_admin)):
    return get_metrics()


# ---------------------------------------------------------------------------
# Debug / Leak detection (Phase 7)
# ---------------------------------------------------------------------------
@router.get("/debug/leaks")
async def debug_leaks(_=Depends(require_admin)):
    """
    Returns live counts of resources held by the backend.
    Use this to detect leaks during stress testing: run before the test,
    run after cleanup, and verify counts return to baseline.
    """
    rss_mb = None
    try:
        # Try psutil first (cross-platform, accurate)
        import os
        import psutil  # type: ignore
        rss_mb = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except ImportError:
        # Fallback: resource module (Unix only)
        try:
            import resource  # type: ignore
            # ru_maxrss is in KB on Linux, bytes on macOS
            maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss_mb = round(maxrss / 1024, 1)  # assume Linux (KB)
        except Exception:
            pass
    except Exception:
        pass

    # Count running asyncio tasks (excludes the current task)
    try:
        current = asyncio.current_task()
        all_tasks = [t for t in asyncio.all_tasks() if t is not current]
        asyncio_tasks_total = len(all_tasks)
        asyncio_tasks_pending = sum(1 for t in all_tasks if not t.done())
    except Exception:
        asyncio_tasks_total = None
        asyncio_tasks_pending = None

    return {
        "active_sessions": len(active_sessions),
        "active_gen_tasks": len(active_gen_tasks),
        "active_tts_tasks": len(active_tts_tasks),
        "asyncio_tasks_total": asyncio_tasks_total,
        "asyncio_tasks_pending": asyncio_tasks_pending,
        "process_rss_mb": rss_mb,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Errors & Logs
# ---------------------------------------------------------------------------
@router.get("/errors")
async def errors(_=Depends(require_admin)):
    all_errors = list(error_log)
    all_errors.sort(key=lambda e: e.get("ts_epoch", 0), reverse=True)
    return all_errors[:500]


@router.delete("/errors")
async def clear_errors(_=Depends(require_admin)):
    error_log.clear()
    return {"status": "cleared"}


@router.get("/errors/rate")
async def error_rate(_=Depends(require_admin)):
    now = time.time()
    minute_ago = now - 60
    recent = [e for e in error_log if e.get("ts_epoch", 0) > minute_ago]
    return {"errors_per_minute": len(recent)}


@router.get("/logs")
async def logs(
    level: str = Query(None),
    service: str = Query(None),
    limit: int = Query(100),
    _=Depends(require_admin),
):
    result = list(error_log)
    if level:
        result = [e for e in result if e.get("level", "").upper() == level.upper()]
    if service:
        result = [e for e in result if e.get("service", "") == service]
    return result[-limit:]


# ---------------------------------------------------------------------------
# RAG (Knowledge Base)
# ---------------------------------------------------------------------------
from backend.services.rag import get_rag_engine


class IngestRequest(BaseModel):
    texts: list[str]
    source: str = "manual"
    language: str = "auto"


class RAGSearchRequest(BaseModel):
    query: str
    language: str | None = None
    top_k: int = 5


@router.get("/rag/stats")
async def rag_stats(_=Depends(require_admin)):
    engine = get_rag_engine()
    return engine.get_stats()


@router.post("/rag/ingest")
async def rag_ingest(req: IngestRequest, _=Depends(require_admin)):
    from backend.services.language import detect_language
    engine = get_rag_engine()

    # Auto-detect language if not specified
    language = req.language
    if language == "auto" and req.texts:
        # Detect from the first text chunk (they're usually all the same language)
        sample = req.texts[0][:500]
        detection = detect_language(sample)
        language = detection["primary"]

    count = await engine.add_texts(req.texts, source=req.source, language=language)
    return {"status": "ok", "ingested": count, "detected_language": language}


# ---------------------------------------------------------------------------
# RAG file upload (Phase 9): PDF / DOCX / TXT / MD with OCR fallback
# ---------------------------------------------------------------------------
_RAG_UPLOAD_EXTS = {".pdf", ".docx", ".txt", ".md", ".markdown"}
_RAG_UPLOAD_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/rag/upload-file")
async def rag_upload_file(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    source: str | None = Form(None),
    _=Depends(require_admin),
):
    """Upload a PDF / DOCX / TXT / MD into the global knowledge base.

    Returns a job_id immediately so the client can poll /rag/jobs/{job_id}
    for progress — this avoids proxy/tunnel timeouts on large files.
    """
    if not getattr(config, "PHASE9_ENABLED", False):
        raise HTTPException(
            503,
            "Phase 9 file ingestion is disabled. Set PHASE9_ENABLED=true to enable.",
        )
    if not file.filename:
        raise HTTPException(400, "Missing filename.")
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix not in _RAG_UPLOAD_EXTS:
        raise HTTPException(
            415,
            f"Unsupported file type '{suffix}'. Supported: {sorted(_RAG_UPLOAD_EXTS)}",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload.")
    if len(raw) > _RAG_UPLOAD_MAX_BYTES:
        raise HTTPException(
            413,
            f"File exceeds {_RAG_UPLOAD_MAX_BYTES // (1024 * 1024)} MB limit.",
        )

    job_id = str(uuid.uuid4())
    _upload_jobs[job_id] = {"status": "pending", "result": None, "error": None}
    asyncio.create_task(
        _process_upload_job(
            job_id,
            raw,
            file.filename,
            language if language and language != "auto" else None,
            source,
        )
    )
    return {"job_id": job_id, "status": "processing"}


@router.get("/rag/jobs/{job_id}")
async def rag_job_status(job_id: str, _=Depends(require_admin)):
    """Poll the status of a background upload job."""
    job = _upload_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


@router.get("/rag/upload-status")
async def rag_upload_status(_=Depends(require_admin)):
    """Surface whether file upload is enabled + whether OCR is wired up."""
    enabled = getattr(config, "PHASE9_ENABLED", False)
    ocr = False
    if enabled:
        try:
            from backend.services import document_rag
            ocr = document_rag.is_ocr_ready()
        except Exception:
            pass
    return {
        "enabled": enabled,
        "ocr_available": ocr,
        "max_bytes": _RAG_UPLOAD_MAX_BYTES,
        "supported_extensions": sorted(_RAG_UPLOAD_EXTS),
    }


@router.post("/rag/search")
async def rag_search(req: RAGSearchRequest, _=Depends(require_admin)):
    engine = get_rag_engine()
    results = await engine.retrieve(req.query, top_k=req.top_k, language=req.language)
    return {"results": results}


@router.get("/rag/documents")
async def rag_documents(
    query: str = Query(""),
    language: str = Query(None),
    limit: int = Query(50),
    _=Depends(require_admin),
):
    engine = get_rag_engine()
    docs = await engine.search_documents(query=query, language=language, limit=limit)
    return docs


@router.delete("/rag/documents/{doc_id}")
async def rag_delete_doc(doc_id: str, _=Depends(require_admin)):
    engine = get_rag_engine()
    deleted = await engine.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id}


@router.delete("/rag/source/{source}")
async def rag_delete_source(source: str, _=Depends(require_admin)):
    engine = get_rag_engine()
    count = engine.delete_by_source(source)
    return {"status": "deleted", "source": source, "chunks_removed": count}


@router.delete("/rag/clear")
async def rag_clear(_=Depends(require_admin)):
    engine = get_rag_engine()
    engine.clear()
    return {"status": "cleared"}


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------
class UserUpdateRequest(BaseModel):
    tier: str | None = None
    role: str | None = None
    status: str | None = None
    email: str | None = None


_VALID_TIERS = {"free", "pro", "enterprise"}
_VALID_ROLES = {"user", "admin"}
_VALID_STATUS = {"active", "suspended", "banned"}


@router.get("/users")
async def list_users(
    q: str = Query("", description="Search by username or email"),
    tier: str = Query(None),
    role: str = Query(None),
    status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_admin),
):
    where = []
    args = []
    if q:
        args.append(f"%{q}%")
        where.append(f"(username ILIKE ${len(args)} OR COALESCE(email,'') ILIKE ${len(args)})")
    if tier:
        args.append(tier)
        where.append(f"tier = ${len(args)}")
    if role:
        args.append(role)
        where.append(f"role = ${len(args)}")
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = await db.get_conn()
    try:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM users {where_sql}", *args)
        rows = await conn.fetch(
            f"""
            SELECT u.id, u.username, u.email, u.role, u.tier, u.status,
                   u.created_at, u.last_active,
                   COALESCE(s.messages_total, 0) AS messages_total,
                   COALESCE(s.tokens_total, 0) AS tokens_total
            FROM users u
            LEFT JOIN (
                SELECT user_id,
                       SUM(messages_sent) AS messages_total,
                       SUM(tokens_used) AS tokens_total
                FROM usage_stats GROUP BY user_id
            ) s ON s.user_id = u.id
            {where_sql}
            ORDER BY u.created_at DESC
            LIMIT {limit} OFFSET {offset}
            """,
            *args,
        )
    finally:
        await db.release_conn(conn)

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "id": r["id"],
                "username": r["username"],
                "email": r["email"],
                "role": r["role"],
                "tier": r["tier"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "last_active": r["last_active"].isoformat() if r["last_active"] else None,
                "messages_total": int(r["messages_total"] or 0),
                "tokens_total": int(r["tokens_total"] or 0),
            }
            for r in rows
        ],
    }


@router.put("/users/{user_id}")
async def update_user(user_id: int, req: UserUpdateRequest, admin=Depends(require_admin)):
    sets = []
    args = []
    if req.tier is not None:
        if req.tier not in _VALID_TIERS:
            raise HTTPException(400, f"Invalid tier. Must be one of {sorted(_VALID_TIERS)}")
        args.append(req.tier)
        sets.append(f"tier = ${len(args)}")
    if req.role is not None:
        if req.role not in _VALID_ROLES:
            raise HTTPException(400, f"Invalid role. Must be one of {sorted(_VALID_ROLES)}")
        args.append(req.role)
        sets.append(f"role = ${len(args)}")
    if req.status is not None:
        if req.status not in _VALID_STATUS:
            raise HTTPException(400, f"Invalid status. Must be one of {sorted(_VALID_STATUS)}")
        args.append(req.status)
        sets.append(f"status = ${len(args)}")
    if req.email is not None:
        args.append(req.email or None)
        sets.append(f"email = ${len(args)}")

    if not sets:
        raise HTTPException(400, "No fields to update")

    args.append(user_id)
    conn = await db.get_conn()
    try:
        row = await conn.fetchrow(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ${len(args)} RETURNING id, username, role, tier, status, email",
            *args,
        )
    finally:
        await db.release_conn(conn)
    if not row:
        raise HTTPException(404, "User not found")

    await _write_audit({
        "user_id": admin["id"],
        "username": admin["username"],
        "action": "user_update",
        "status": "success",
        "error_message": f"target={user_id} fields={list(req.model_dump(exclude_none=True).keys())}",
    })
    return dict(row)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin.get("id"):
        raise HTTPException(400, "Cannot delete your own account")
    conn = await db.get_conn()
    try:
        row = await conn.fetchrow("DELETE FROM users WHERE id = $1 RETURNING username", user_id)
    finally:
        await db.release_conn(conn)
    if not row:
        raise HTTPException(404, "User not found")

    await _write_audit({
        "user_id": admin.get("id"),
        "username": admin.get("username"),
        "action": "user_delete",
        "status": "success",
        "error_message": f"target={user_id} username={row['username']}",
    })
    return {"status": "deleted", "id": user_id}


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
async def _write_audit(entry: dict):
    """Insert an audit log row. Safe to call from any request handler."""
    if not config.DB_DSN:
        return  # silently skip when DB is not configured
    try:
        conn = await db.get_conn()
        try:
            await conn.execute(
                """
                INSERT INTO audit_log
                  (user_id, username, action, model, tokens_in, tokens_out,
                   latency_ms, ip_address, user_agent, session_id, status, error_message)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                entry.get("user_id"),
                entry.get("username"),
                entry.get("action", "unknown"),
                entry.get("model"),
                entry.get("tokens_in"),
                entry.get("tokens_out"),
                entry.get("latency_ms"),
                entry.get("ip_address"),
                entry.get("user_agent"),
                entry.get("session_id"),
                entry.get("status", "success"),
                entry.get("error_message"),
            )
        finally:
            await db.release_conn(conn)
    except Exception as e:
        print(f"[AUDIT] Failed to write audit log: {e}")


@router.get("/audit-logs")
async def list_audit_logs(
    q: str = Query("", description="Search username/error message"),
    user_id: int = Query(None),
    action: str = Query(None),
    model: str = Query(None),
    status: str = Query(None),
    since: str = Query(None, description="ISO timestamp lower bound"),
    until: str = Query(None, description="ISO timestamp upper bound"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _=Depends(require_admin),
):
    where = []
    args = []
    if q:
        args.append(f"%{q}%")
        where.append(f"(COALESCE(username,'') ILIKE ${len(args)} OR COALESCE(error_message,'') ILIKE ${len(args)})")
    if user_id is not None:
        args.append(user_id)
        where.append(f"user_id = ${len(args)}")
    if action:
        args.append(action)
        where.append(f"action = ${len(args)}")
    if model:
        args.append(model)
        where.append(f"model = ${len(args)}")
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    if since:
        try:
            args.append(datetime.fromisoformat(since.replace("Z", "+00:00")))
            where.append(f"ts >= ${len(args)}")
        except Exception:
            pass
    if until:
        try:
            args.append(datetime.fromisoformat(until.replace("Z", "+00:00")))
            where.append(f"ts <= ${len(args)}")
        except Exception:
            pass
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = await db.get_conn()
    try:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM audit_log {where_sql}", *args)
        rows = await conn.fetch(
            f"""
            SELECT id, ts, user_id, username, action, model, tokens_in, tokens_out,
                   latency_ms, ip_address, user_agent, session_id, status, error_message
            FROM audit_log
            {where_sql}
            ORDER BY ts DESC
            LIMIT {limit} OFFSET {offset}
            """,
            *args,
        )
    finally:
        await db.release_conn(conn)

    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": r["id"],
                "ts": r["ts"].isoformat() if r["ts"] else None,
                "user_id": r["user_id"],
                "username": r["username"],
                "action": r["action"],
                "model": r["model"],
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "latency_ms": r["latency_ms"],
                "ip_address": r["ip_address"],
                "user_agent": r["user_agent"],
                "session_id": r["session_id"],
                "status": r["status"],
                "error_message": r["error_message"],
            }
            for r in rows
        ],
    }


@router.get("/audit-logs/stats")
async def audit_log_stats(
    hours: int = Query(24, ge=1, le=720),
    _=Depends(require_admin),
):
    conn = await db.get_conn()
    try:
        totals = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'error') AS errors,
                   COALESCE(SUM(tokens_in), 0) AS tokens_in,
                   COALESCE(SUM(tokens_out), 0) AS tokens_out,
                   COALESCE(AVG(latency_ms), 0) AS avg_latency
            FROM audit_log
            WHERE ts >= NOW() - ($1::int * INTERVAL '1 hour')
            """,
            hours,
        )
        by_model = await conn.fetch(
            """
            SELECT COALESCE(model, 'unknown') AS model, COUNT(*) AS count
            FROM audit_log
            WHERE ts >= NOW() - ($1::int * INTERVAL '1 hour')
            GROUP BY model
            ORDER BY count DESC
            LIMIT 10
            """,
            hours,
        )
    finally:
        await db.release_conn(conn)

    return {
        "window_hours": hours,
        "total": int(totals["total"] or 0),
        "errors": int(totals["errors"] or 0),
        "tokens_in": int(totals["tokens_in"] or 0),
        "tokens_out": int(totals["tokens_out"] or 0),
        "avg_latency_ms": int(totals["avg_latency"] or 0),
        "by_model": [{"model": r["model"], "count": int(r["count"])} for r in by_model],
    }


@router.delete("/audit-logs")
async def clear_audit_logs(
    older_than_hours: int = Query(None, ge=1),
    _=Depends(require_admin),
):
    conn = await db.get_conn()
    try:
        if older_than_hours:
            res = await conn.execute(
                "DELETE FROM audit_log WHERE ts < NOW() - ($1::int * INTERVAL '1 hour')",
                older_than_hours,
            )
        else:
            res = await conn.execute("DELETE FROM audit_log")
    finally:
        await db.release_conn(conn)
    return {"status": "cleared", "result": res}


# ---------------------------------------------------------------------------
# Live WebSocket — pushes stats every 1s
# ---------------------------------------------------------------------------
@router.websocket("/ws/stats")
async def ws_admin_stats(ws: WebSocket):
    token = ws.query_params.get("token", "")
    payload = verify_token_raw(token)
    if not payload or payload.get("role") != "admin":
        await ws.close(code=4003, reason="Forbidden")
        return

    await ws.accept()
    try:
        while True:
            m = get_metrics()
            data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "gpu": read_gpu_stats(),
                "sessions": {"active": len(active_sessions)},
                "latency": {"p50": m["p50"], "p95": m["p95"]},
                "error_rate": m["error_rate"],
            }
            await ws.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
