import os
import json
from dataclasses import dataclass

@dataclass
class MemoryBlock:
    name: str
    content: str
    max_tokens: int = 500

class CoreMemory:
    PERSISTENCE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'core_memory')
    
    def __init__(self, user_id: str = 'boss'):
        self.user_id = user_id
        self.blocks = {
            'boss_profile': MemoryBlock(name='boss_profile', content='Name: Hanzla Rehman\nRole: Boss / CEO', max_tokens=400),
            'active_task': MemoryBlock(name='active_task', content='No active task.', max_tokens=600),
            'session_scratchpad': MemoryBlock(name='session_scratchpad', content='(empty)', max_tokens=400)
        }
        self.filepath = os.path.join(self.PERSISTENCE_DIR, f"{self.user_id}_core.md")
        self._load()
        
    def update_block(self, block_name: str, new_content: str) -> bool:
        if block_name in self.blocks:
            self.blocks[block_name].content = new_content
            self._save()
            return True
        return False
        
    def append_to_block(self, block_name: str, text: str) -> bool:
        if block_name in self.blocks:
            self.blocks[block_name].content += f"\n{text}"
            self._save()
            return True
        return False
        
    def replace_in_block(self, block_name: str, old_text: str, new_text: str) -> bool:
        if block_name in self.blocks:
            if old_text in self.blocks[block_name].content:
                self.blocks[block_name].content = self.blocks[block_name].content.replace(old_text, new_text)
                self._save()
                return True
        return False
        
    def format_for_prompt(self) -> str:
        formatted = "--- CORE MEMORY ---\n"
        for name, block in self.blocks.items():
            formatted += f"[{name}]\n{block.content}\n\n"
        return formatted
        
    def _save(self) -> None:
        if not os.path.exists(self.PERSISTENCE_DIR):
            os.makedirs(self.PERSISTENCE_DIR, exist_ok=True)
            
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Core Memory: {self.user_id}\n\n")
            for name, block in self.blocks.items():
                f.write(f"## {name}\n")
                f.write(f"{block.content.strip()}\n\n")
            
    def _load(self) -> None:
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            sections = re.split(r'^##\s+(.*)$', content, flags=re.MULTILINE)
            for i in range(1, len(sections), 2):
                name = sections[i].strip()
                body = sections[i+1].strip()
                if name in self.blocks:
                    self.blocks[name].content = body
        except Exception as e:
            print(f"Failed to load core memory for {self.user_id}: {e}")
