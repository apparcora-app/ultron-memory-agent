import sys
sys.path.append(".")
import asyncio
from agent import MemoryAgent

async def test():
    agent = MemoryAgent(user_id="test_user")
    
    # Fake user input
    user_input = "give me a ats score of my resume using ats skill and also save this resume in your memory for futures job search and my profile and portfolio, i will ask about thing from my cv later"
    
    # generate prompt
    prompt, active_skills = agent._generate_system_prompt(user_input, [])
    
    print(f"Active skills: {len(active_skills)}")
    print(f"System prompt length (chars): {len(prompt)}")
    print(f"System prompt length (approx tokens): {len(prompt) // 4}")
    
    # test tool triage size
    from tools import ALL_TOOLS
    import json
    tool_defs = json.dumps(ALL_TOOLS)
    print(f"All Tools length (chars): {len(tool_defs)}")
    print(f"All Tools length (approx tokens): {len(tool_defs) // 4}")

asyncio.run(test())
