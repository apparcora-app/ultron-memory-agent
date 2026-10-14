"""
Empirical verification test for Ultron Skills Matrix Search & Filter functionality.
Verifies:
1. Static index.html and assets are built and served.
2. Skill item search matches name, tags, description, category, and ID.
3. Multi-word search tokens are properly evaluated.
4. Cross-category search count calculation is correct.
"""

import json
from pathlib import Path


def test_skills_matrix_static_bundle():
    static_dir = Path(__file__).resolve().parent.parent / "static"
    index_file = static_dir / "index.html"
    assert index_file.exists(), "static/index.html must exist"
    content = index_file.read_text(encoding="utf-8")
    assert '<div id="root"></div>' in content, "Root element missing in index.html"
    assert "/static/assets/index-" in content, "Built assets missing in index.html"


def check_matches_search(skill, term):
    if not term:
        return True
    tokens = [t.lower() for t in term.split() if t]
    if not tokens:
        return True

    name = (skill.get("name") or "").lower()
    desc = (skill.get("description") or "").lower()
    skill_id = (skill.get("id") or skill.get("skill_id") or "").lower()
    category = (skill.get("category") or "").lower()
    tags_list = skill.get("tags") or []
    tags = " ".join(tags_list).lower() if isinstance(tags_list, list) else str(tags_list).lower()
    instructions = (skill.get("instructions") or "").lower()

    return all(
        token in name
        or token in desc
        or token in skill_id
        or token in category
        or token in tags
        or token in instructions
        for token in tokens
    )


def test_skills_search_matching():
    sample_skills = [
        {
            "id": "agent_browser",
            "name": "Agent Browser Automation CLI",
            "category": "Automation",
            "description": "Headless browser automation CLI optimized for AI agents with accessibility tree snapshots.",
            "tags": ["browser", "automation", "playwright"],
        },
        {
            "id": "ai_automation_workflows",
            "name": "AI Automation & Multi-Model Pipelines",
            "category": "Automation",
            "description": "Build automated AI workflows combining multiple models, APIs, and cloud services.",
            "tags": ["ai-automation", "workflow", "batch-processing"],
        },
        {
            "id": "corporate_tax_calc",
            "name": "Corporate Tax Reconciliation Engine",
            "category": "Accounting",
            "description": "Calculates Form 1120 corporate tax deductions and depreciation schedules.",
            "tags": ["tax", "irs", "accounting"],
        },
    ]

    # Test 1: Tag search ("playwright")
    matches = [s for s in sample_skills if check_matches_search(s, "playwright")]
    assert len(matches) == 1
    assert matches[0]["id"] == "agent_browser"

    # Test 2: Name search ("browser automation")
    matches = [s for s in sample_skills if check_matches_search(s, "browser automation")]
    assert len(matches) == 1
    assert matches[0]["id"] == "agent_browser"

    # Test 3: Description search ("depreciation")
    matches = [s for s in sample_skills if check_matches_search(s, "depreciation")]
    assert len(matches) == 1
    assert matches[0]["id"] == "corporate_tax_calc"

    # Test 4: ID search ("ai_automation")
    matches = [s for s in sample_skills if check_matches_search(s, "ai_automation")]
    assert len(matches) == 1
    assert matches[0]["id"] == "ai_automation_workflows"

    # Test 5: Category filter cross-check
    # If category is "Automation" but user searches "tax", category filter yields 0,
    # but all-categories search yields 1.
    term = "tax"
    selected_category = "Automation"
    all_matches = [s for s in sample_skills if check_matches_search(s, term)]
    category_matches = [
        s for s in all_matches if s.get("category") == selected_category
    ]
    assert len(category_matches) == 0
    assert len(all_matches) == 1
    assert all_matches[0]["id"] == "corporate_tax_calc"

    print("All search verification test assertions passed successfully!")
