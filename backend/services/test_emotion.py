import asyncio
import redis.asyncio as redis
import json
async def main():
    r = redis.Redis(host='localhost', port=6379, db=0)
    await r.set('personaplex:state:default', json.dumps({'emotion': 'angry', 'style': 'sarcastic', 'language': 'ru'}))
    print('Emotion set to angry/sarcastic')
    await r.close()
asyncio.run(main())
