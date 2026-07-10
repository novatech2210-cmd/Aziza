import asyncio
from core import AIOrchestrator

async def main():
    orchestrator = AIOrchestrator()
    try:
        await orchestrator.startup()
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await orchestrator.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
