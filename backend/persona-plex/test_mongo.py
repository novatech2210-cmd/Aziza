import asyncio
from database import db, save_memory, get_session_history

async def test_conn():
    try:
        await save_memory({"session_id": "test_session", "message": "test"})
        res = await get_session_history("test_session")
        print("SUCCESS:", len(res), "records found")
    except Exception as e:
        print("ERROR:", e)

asyncio.run(test_conn())
