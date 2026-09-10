import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""
Interactive CLI to test Semantic Skill Vector Search & Hybrid RRF Retrieval.

Usage:
  python test_semantic_search.py "your query here"
  python test_semantic_search.py --interactive
"""

import sys, time
from skill_manager import SkillManager

def main():
    sm = SkillManager()
    
    if len(sys.argv) > 1 and sys.argv[1] != "--interactive":
        query = " ".join(sys.argv[1:])
        run_query(sm, query)
        return

    print("\n=======================================================")
    print(" 🧠 ULTRON SEMANTIC SKILL VECTOR RETRIEVAL TESTER")
    print(" Type any question to see which skills are retrieved.")
    print(" Type 'exit' or 'q' to quit.")
    print("=======================================================\n")

    while True:
        try:
            query = input("Enter prompt/query: ").strip()
            if not query or query.lower() in ["exit", "q", "quit"]:
                break
            run_query(sm, query)
        except (KeyboardInterrupt, EOFError):
            break

def run_query(sm: SkillManager, query: str):
    t0 = time.time()
    matched = sm.get_matched_skills(query, limit=3)
    elapsed_ms = (time.time() - t0) * 1000

    print(f"\n[QUERY]: \"{query}\" ({elapsed_ms:.1f}ms)")
    if not matched:
        print("  No matching skills found.\n")
        return

    for idx, skill in enumerate(matched, 1):
        tags_preview = ", ".join(skill.tags[:4]) if skill.tags else "general"
        print(f"  {idx}. [{skill.id}] {skill.name}")
        print(f"     Category: {skill.category} | Tags: [{tags_preview}]")
        print(f"     Description: {skill.description[:100]}...")
    print("-" * 55 + "\n")

if __name__ == "__main__":
    main()
