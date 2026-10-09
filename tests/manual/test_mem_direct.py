import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import os
from memory.memory_manager import MemoryManager
from dotenv import load_dotenv
load_dotenv()
async def run():
    print('Initializing MemoryManager...')
    mem = MemoryManager(user_id='test_user_777')
    print('Writing memory...')
    try:
        mem.add([{'role': 'user', 'content': 'My secret passphrase is [ultron_omega_99]'}])
    except Exception as e:
        print('Failed to write:', e)
    print('Recalling memory...')
    res = mem.search('secret passphrase')
    print('Response:')
    for r in res: print(r)
asyncio.run(run())
