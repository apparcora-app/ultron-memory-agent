import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import sqlite3
import json
from pathlib import Path

print('=== 1. Testing Telemetry Engine ===')
from telemetry.engine import TelemetryEngine
te = TelemetryEngine()
te.log_event('boss', 'PII_TEST', 'test_module', {'name': 'John Doe', 'ssn': '123-45-6789', 'ein': '12-3456789'})

print('=== 2. Testing Audit Logger ===')
from ultron.execution.gateway.audit_logger import AuditLogger
al = AuditLogger()
class DummyRecord:
    def model_dump_json(self):
        return json.dumps({'result_summary': 'John Doe SSN: 123-45-6789 EIN: 12-3456789'})
al._append_record(DummyRecord())

print('=== 3. Testing Chat Session Manager ===')
from memory.chat_session_manager import ChatSessionManager
csm = ChatSessionManager()
session_data = {
    'messages': [{'role': 'user', 'content': 'My SSN is 123-45-6789 and EIN is 12-3456789.'}],
    'version': 1
}
csm.save_session('boss', 'pii_terminal_test', session_data)

print('=== 4. Testing Swarm Orchestrator Blackboard ===')
from pipelines.swarm_orchestrator import SwarmOrchestrator
so = SwarmOrchestrator(None, None)
so._save_blackboard('pii_terminal_test', {'client_info': 'SSN 123-45-6789 EIN 12-3456789'}, {})

print('=== 5. Testing Mem0 Vector Embeddings ===')
from memory.memory_manager import MemoryManager
mm = MemoryManager('boss')
class MockMem:
    def add(self, messages, user_id):
        print(f'  [MEM0 ADD INTERCEPT] Payload headed to huggingface models:\n  {messages}')
        return {'results': [{'memory': 'Mocked'}]}
mm.mem = MockMem()
mm.add([{'role': 'user', 'content': 'SSN 123-45-6789 EIN 12-3456789'}])

print('\n' + '='*50)
print('=== DIRECT FILESYSTEM & DB VERIFICATION ===')
print('='*50)

print('\n[1] Telemetry DB (telemetry.db) latest entry:')
conn = sqlite3.connect('./data/telemetry.db')
c = conn.cursor()
c.execute('SELECT details FROM audit_logs WHERE event_type="PII_TEST" ORDER BY rowid DESC LIMIT 1')
print(' ', c.fetchone()[0])

print('\n[2] Audit Logger (computer_audit.jsonl) latest entry:')
with open('./data/logs/computer_audit.jsonl', 'r', encoding='utf-8') as f:
    print(' ', f.readlines()[-1].strip())

print('\n[3] Chat Session Manager (boss_pii_terminal_test.json):')
with open('./memory/data/sessions/boss_pii_terminal_test.json', 'r', encoding='utf-8') as f:
    print(' ', f.read().strip())

print('\n[4] Swarm Blackboard (latest.json):')
with open('./data/blackboard/latest.json', 'r', encoding='utf-8') as f:
    print(' ', f.read().strip())
