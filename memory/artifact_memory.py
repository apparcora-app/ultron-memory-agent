import os
import json
import uuid
from datetime import datetime
from typing import Any, List, Dict

class LocalArtifactEngine:
    def __init__(self, user_id: str, data_dir: str = './data', **kwargs):
        self.user_id = user_id
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.interaction_log_path = os.path.join(self.data_dir, 'interaction_log.jsonl')

    def _append_log(self, text: str):
        with open(self.interaction_log_path, 'a', encoding='utf-8') as f:
            entry = {
                'id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'text': text,
                'user_id': self.user_id
            }
            f.write(json.dumps(entry) + '\n')

    def add(self, messages_or_text, user_id: str = None) -> Dict[str, Any]:
        if isinstance(messages_or_text, str):
            text = messages_or_text
        elif isinstance(messages_or_text, list):
            text = '\n'.join([m.get('content', '') for m in messages_or_text if m.get('content')])
        else:
            text = str(messages_or_text)
            
        if not text.strip():
            return {'results': []}

        self._append_log(text)
        return {'status': 'added', 'text_length': len(text)}

    def search(self, query: str, recency_bias: float = 0.3) -> List[Dict[str, Any]]:
        # Interaction log is append-only for debugging; core state handles prompt injection.
        return []

    def format_for_prompt(self, memories: List[Dict[str, Any]]) -> str:
        return ""

    def get_all(self) -> List[Dict[str, Any]]:
        return []

    def delete(self, memory_id: str) -> None:
        pass

    def detect_and_store_emotional_context(self, user_text: str) -> str:
        text_lower = user_text.lower()
        sentiment = 'NEUTRAL'
        if any(w in text_lower for w in ['asap', 'urgent', 'immediately', 'emergency', 'help!']):
            sentiment = 'URGENT'
        elif any(w in text_lower for w in ['wrong', 'failed', 'broken', 'issue', 'error', 'not working']):
            sentiment = 'FRUSTRATED'
        elif any(w in text_lower for w in ['great', 'awesome', 'perfect', 'thanks', 'excellent']):
            sentiment = 'SATISFIED'
        elif any(w in text_lower for w in ['analyze', 'calculate', 'audit', 'model']):
            sentiment = 'ANALYTICAL'

        if sentiment != 'NEUTRAL':
            self.add(f'[User Emotional Context Signal: {sentiment}]')
        return sentiment