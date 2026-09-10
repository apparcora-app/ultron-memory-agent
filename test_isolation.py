import asyncio
from agent import MemoryAgent
from file_processor import ProcessedFile

async def run_test():
    agent = MemoryAgent(user_id="test_user")
    
    # Create a dummy large file (3000 chars)
    large_text = "This is a large file content. " * 100
    
    file = ProcessedFile(
        filename="large_data.txt",
        file_type="text/plain",
        text_content=large_text,
        is_image=False
    )
    
    print("Testing File Isolation Worker...")
    res = await agent.chat_async(
        user_input="Summarize the file",
        files=[file]
    )
    
    if isinstance(res, dict):
        reply = res.get("reply", str(res))
    else:
        reply = str(res)
    
    print(f"\nFinal Reply: {reply[:150]}...")
    print(agent.budget_summary())

if __name__ == "__main__":
    asyncio.run(run_test())
