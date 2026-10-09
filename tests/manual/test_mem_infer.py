import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import os
from mem0 import Memory
import asyncio
from dotenv import load_dotenv
load_dotenv()

cfg = {
  'vector_store': {'provider': 'chroma', 'config': {'collection_name': 'test_mem', 'path': './test_mem_db'}},
  'embedder': {'provider': 'huggingface'},
  'llm': {'provider': 'gemini', 'config': {'api_key': os.getenv('GEMINI_API_KEY')}}
}
m = Memory.from_config(cfg)
print('Writing memory...')
m.add('My secret password is [ultron_omega_99]', user_id='test_777', infer=False)
print('Recalling memory...')
res = m.search('secret password', filters={'user_id': 'test_777'})
print('Search results:')
print(res)
