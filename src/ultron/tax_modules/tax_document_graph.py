import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

# Ensure mem0_agent is on sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph.graph import END, StateGraph
from openai import OpenAI

from ultron.core.config import _detect_freellmapi_api_key, _detect_freellmapi_base_url

# ── 1. FreeLLMAPI Client & Telemetry Initialization ──────────────────────────
base_url = _detect_freellmapi_base_url()
api_key = _detect_freellmapi_api_key()
freellm_client = OpenAI(base_url=base_url, api_key=api_key)

telemetry = {
    "total_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "models_used": set()
}

def call_freellmapi_chat(messages: list[dict[str, str]], call_context: str, preview_input: str) -> tuple[str, str, Any]:
    """Execute live chat completion via FreeLLMAPI with causally connected logging."""
    print(f"  >>> [FREELLMAPI CALL - {call_context}]")
    print(f"      Input Context: '{preview_input}'")

    resp = freellm_client.chat.completions.create(
        model="auto",
        messages=messages,
        temperature=0
    )

    content = resp.choices[0].message.content.strip()
    model = resp.model
    usage = resp.usage

    if usage:
        telemetry["total_calls"] += 1
        telemetry["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        telemetry["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
        telemetry["total_tokens"] += getattr(usage, "total_tokens", 0) or 0
        telemetry["models_used"].add(model)

    print(f"  <<< [FREELLMAPI RESPONSE - {call_context}]")
    print(f"      Input Context: '{preview_input}'")
    print(f"      Returned Content: '{content}'")
    print(f"      Model Engine: '{model}'")
    print(f"      Usage Metadata: {usage}")

    return content, model, usage

# ── 2. State Schema Definition ────────────────────────────────────────────────
class TaxDocState(TypedDict):
    raw_document: str
    doc_type: str                  # W-2, 1099-NEC, 1099-MISC, Paystub, Unknown
    extracted_fields: dict[str, Any]
    missing_fields: list[str]
    loop_count: int
    max_loops: int
    status: str                    # INTAKE, CLASSIFIED, FIELDS_EXTRACTED, COMPLETE, INCOMPLETE, FINALIZED, NEEDS_MANUAL_REVIEW, REQUEST_CLARIFICATION
    node_history: list[str]
    clarification_message: str | None
    final_output: dict[str, Any] | None
    supplemental_data: dict[str, Any] | None

# ── 3. Node Definitions ───────────────────────────────────────────────────────

def classify_node(state: TaxDocState) -> dict:
    """Node 'classify': Determine document type using FreeLLMAPI (not keyword matching)."""
    doc_text = state["raw_document"]
    preview = doc_text[:90].replace("\n", " ") + "..."
    print("\n[NODE: classify] Classifying document type via FreeLLMAPI...")

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert US tax document classification system. "
                "Analyze the provided document text and classify it into exactly one of: "
                "W-2, 1099-NEC, 1099-MISC, Paystub, Unknown. "
                "Respond with ONLY the exact category label, nothing else."
            )
        },
        {"role": "user", "content": f"Document Text:\n{doc_text}"}
    ]

    raw_resp, model, usage = call_freellmapi_chat(messages, "CLASSIFY_DOC_TYPE", preview)

    # Normalize classification result
    cleaned = raw_resp.strip("'\"`.")
    doc_type = "Unknown"
    for label in ["W-2", "1099-NEC", "1099-MISC", "Paystub"]:
        if label.lower() in cleaned.lower():
            doc_type = label
            break

    print(f"  [CLASSIFY RESULT] Assigned Document Type: '{doc_type}'")
    return {
        "doc_type": doc_type,
        "status": "CLASSIFIED",
        "node_history": state.get("node_history", []) + ["classify"]
    }

def route_doc_type(state: TaxDocState) -> str:
    """Conditional Edge: W-2 -> employee_tax_path; 1099-* -> contractor_tax_path; Unknown -> request_clarification."""
    doc_type = state["doc_type"]
    if doc_type == "W-2":
        dest = "employee_tax_path"
    elif doc_type.startswith("1099"):
        dest = "contractor_tax_path"
    else:
        dest = "request_clarification"
    print(f"  [CONDITIONAL ROUTE: classify -> {dest}] (doc_type='{doc_type}')")
    return dest

def employee_tax_path_node(state: TaxDocState) -> dict:
    """Node 'employee_tax_path': Extract W-2 required fields (employer EIN, wages, withholding)."""
    doc_text = state["raw_document"]
    preview = doc_text[:90].replace("\n", " ") + "..."
    print("\n[NODE: employee_tax_path] Extracting required W-2 employee fields via FreeLLMAPI...")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a tax data extraction agent. Extract the following fields from the W-2 document: "
                "1. employer_ein (string or null if not found) "
                "2. wages (number or null if not found) "
                "3. withholding (number or null if not found) "
                "Return valid JSON only with keys: employer_ein, wages, withholding."
            )
        },
        {"role": "user", "content": f"W-2 Document:\n{doc_text}"}
    ]

    raw_resp, model, usage = call_freellmapi_chat(messages, "EXTRACT_W2_FIELDS", preview)

    clean_json_str = raw_resp.strip("`").replace("json\n", "", 1).strip()
    try:
        extracted = json.loads(clean_json_str)
    except Exception:
        extracted = {"employer_ein": None, "wages": None, "withholding": None}

    print(f"  [EXTRACTED W-2 DATA] {extracted}")
    return {
        "extracted_fields": extracted,
        "status": "FIELDS_EXTRACTED",
        "node_history": state.get("node_history", []) + ["employee_tax_path"]
    }

def contractor_tax_path_node(state: TaxDocState) -> dict:
    """Node 'contractor_tax_path': Extract 1099 required fields (payer TIN, nonemployee comp)."""
    doc_text = state["raw_document"]
    preview = doc_text[:90].replace("\n", " ") + "..."
    print("\n[NODE: contractor_tax_path] Extracting required 1099 contractor fields via FreeLLMAPI...")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a tax data extraction agent. Extract the following fields from the 1099 document: "
                "1. payer_tin (string or null if missing/redacted/not provided) "
                "2. nonemployee_comp (number or null if missing/not provided) "
                "Return valid JSON only with keys: payer_tin, nonemployee_comp."
            )
        },
        {"role": "user", "content": f"1099 Document:\n{doc_text}"}
    ]

    raw_resp, model, usage = call_freellmapi_chat(messages, "EXTRACT_1099_FIELDS", preview)

    clean_json_str = raw_resp.strip("`").replace("json\n", "", 1).strip()
    try:
        extracted = json.loads(clean_json_str)
    except Exception:
        extracted = {"payer_tin": None, "nonemployee_comp": None}

    print(f"  [EXTRACTED 1099 DATA] {extracted}")
    return {
        "extracted_fields": extracted,
        "status": "FIELDS_EXTRACTED",
        "node_history": state.get("node_history", []) + ["contractor_tax_path"]
    }

def check_completeness_node(state: TaxDocState) -> dict:
    """Node 'check_completeness': Validate that all mandatory fields are present and non-empty."""
    doc_type = state["doc_type"]
    extracted = state.get("extracted_fields", {})
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)

    if doc_type == "W-2":
        mandatory = ["employer_ein", "wages", "withholding"]
    else:
        mandatory = ["payer_tin", "nonemployee_comp"]

    missing = [k for k in mandatory if extracted.get(k) is None or str(extracted.get(k)).strip() == ""]

    print(f"\n[NODE: check_completeness] Evaluating Field Completeness (Iteration {loop_count}/{max_loops})")
    print(f"  Mandatory Schema: {mandatory}")
    print(f"  Extracted State:  {extracted}")
    print(f"  Missing Fields:   {missing if missing else 'None (100% Complete)'}")

    return {
        "missing_fields": missing,
        "status": "COMPLETE" if not missing else "INCOMPLETE",
        "node_history": state.get("node_history", []) + ["check_completeness"]
    }

def route_completeness(state: TaxDocState) -> str:
    """Conditional Edge: Complete -> finalize; Incomplete (loops < max) -> request_missing_info; Incomplete (loops >= max) -> needs_manual_review."""
    missing = state.get("missing_fields", [])
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)

    if not missing:
        dest = "finalize"
        print("  [CONDITIONAL ROUTE: check_completeness -> finalize] All required fields verified.")
    elif loop_count >= max_loops:
        dest = "needs_manual_review"
        print(f"  [CONDITIONAL ROUTE: check_completeness -> needs_manual_review] Max loops reached ({loop_count}/{max_loops}). Halting to manual review.")
    else:
        dest = "request_missing_info"
        print(f"  [CONDITIONAL ROUTE: check_completeness -> request_missing_info] Missing fields {missing}. Looping for clarification.")

    return dest

def request_missing_info_node(state: TaxDocState) -> dict:
    """Node 'request_missing_info': Increments loop counter and generates clarification request."""
    curr_loops = state.get("loop_count", 0)
    new_loop_count = curr_loops + 1
    missing = state.get("missing_fields", [])

    print(f"\n[NODE: request_missing_info] Executing Clarification Loop #{new_loop_count} (Cap: {state.get('max_loops', 2)})...")

    user_prompt = (
        f"The taxpayer submitted a {state['doc_type']} that is missing mandatory fields: {missing}. "
        f"Write a concise 1-sentence prompt requesting these specific items."
    )
    messages = [
        {"role": "system", "content": "You are a professional tax intake assistant. Generate a polite 1-sentence missing field notification."},
        {"role": "user", "content": user_prompt}
    ]

    raw_resp, model, usage = call_freellmapi_chat(messages, f"REQUEST_MISSING_INFO_LOOP_{new_loop_count}", str(missing))

    # Check if supplemental taxpayer data is provided for this run
    updated_fields = dict(state.get("extracted_fields", {}))
    supp_data = state.get("supplemental_data") or {}
    for fld in missing:
        if fld in supp_data:
            updated_fields[fld] = supp_data[fld]
            print(f"  [TAXPAYER SUPPLEMENTAL INPUT RECEIVED] Injected '{fld}' = '{supp_data[fld]}'")

    return {
        "loop_count": new_loop_count,
        "clarification_message": raw_resp,
        "extracted_fields": updated_fields,
        "node_history": state.get("node_history", []) + ["request_missing_info"]
    }

def finalize_node(state: TaxDocState) -> dict:
    """Node 'finalize': Output structured JSON deliverable for validated document."""
    print("\n[NODE: finalize] Compiling structured JSON deliverable...")
    final_payload = {
        "status": "FINALIZED_VALIDATED",
        "doc_type": state["doc_type"],
        "extracted_data": state["extracted_fields"],
        "validation": {
            "is_complete": True,
            "loops_taken": state["loop_count"],
            "missing_fields": []
        },
        "node_sequence": state.get("node_history", []) + ["finalize"],
        "timestamp": datetime.utcnow().isoformat()
    }
    return {
        "status": "FINALIZED",
        "final_output": final_payload,
        "node_history": state.get("node_history", []) + ["finalize"]
    }

def needs_manual_review_node(state: TaxDocState) -> dict:
    """Node 'needs_manual_review': Terminal node when loop limit cap is exhausted."""
    print("\n[NODE: needs_manual_review] Escalating document to human tax reviewer...")
    review_payload = {
        "status": "ESCALATED_NEEDS_MANUAL_REVIEW",
        "doc_type": state["doc_type"],
        "missing_fields": state["missing_fields"],
        "loop_count": state["loop_count"],
        "extracted_partial": state["extracted_fields"],
        "reason": f"Maximum loop iterations ({state.get('max_loops', 2)}) reached without obtaining required fields.",
        "node_sequence": state.get("node_history", []) + ["needs_manual_review"],
        "timestamp": datetime.utcnow().isoformat()
    }
    return {
        "status": "NEEDS_MANUAL_REVIEW",
        "final_output": review_payload,
        "node_history": state.get("node_history", []) + ["needs_manual_review"]
    }

def request_clarification_node(state: TaxDocState) -> dict:
    """Node 'request_clarification': Terminal node for unknown/unsupported document types."""
    doc_text = state["raw_document"]
    preview = doc_text[:90].replace("\n", " ") + "..."
    print("\n[NODE: request_clarification] Rejecting unsupported document via FreeLLMAPI...")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a tax intake specialist. The user provided an unknown or unsupported document. "
                "Write a polite 1-sentence notice explaining that only standard US tax forms (W-2, 1099) "
                "can be processed, and request a valid form."
            )
        },
        {"role": "user", "content": f"Document text was:\n{doc_text[:300]}"}
    ]

    raw_resp, model, usage = call_freellmapi_chat(messages, "UNKNOWN_DOC_CLARIFICATION", preview)

    clarification_payload = {
        "status": "REJECTED_UNKNOWN_DOCUMENT",
        "doc_type": state["doc_type"],
        "notice": raw_resp,
        "node_sequence": state.get("node_history", []) + ["request_clarification"],
        "timestamp": datetime.utcnow().isoformat()
    }
    return {
        "status": "REQUEST_CLARIFICATION",
        "final_output": clarification_payload,
        "node_history": state.get("node_history", []) + ["request_clarification"]
    }

# ── 4. StateGraph Assembly & Compilation ──────────────────────────────────────

def build_tax_graph():
    graph = StateGraph(TaxDocState)

    # Register Nodes
    graph.add_node("classify", classify_node)
    graph.add_node("employee_tax_path", employee_tax_path_node)
    graph.add_node("contractor_tax_path", contractor_tax_path_node)
    graph.add_node("check_completeness", check_completeness_node)
    graph.add_node("request_missing_info", request_missing_info_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("needs_manual_review", needs_manual_review_node)
    graph.add_node("request_clarification", request_clarification_node)

    # Entry Point
    graph.set_entry_point("classify")

    # Conditional edge from classify
    graph.add_conditional_edges(
        "classify",
        route_doc_type,
        {
            "employee_tax_path": "employee_tax_path",
            "contractor_tax_path": "contractor_tax_path",
            "request_clarification": "request_clarification"
        }
    )

    # Path to completeness
    graph.add_edge("employee_tax_path", "check_completeness")
    graph.add_edge("contractor_tax_path", "check_completeness")

    # Conditional edge from check_completeness
    graph.add_conditional_edges(
        "check_completeness",
        route_completeness,
        {
            "finalize": "finalize",
            "request_missing_info": "request_missing_info",
            "needs_manual_review": "needs_manual_review"
        }
    )

    # Loop back edge: request_missing_info -> check_completeness
    graph.add_edge("request_missing_info", "check_completeness")

    # Terminal edges
    graph.add_edge("finalize", END)
    graph.add_edge("needs_manual_review", END)
    graph.add_edge("request_clarification", END)

    return graph.compile()

# ── 5. Main Test Runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    app = build_tax_graph()

    print("================================================================================")
    print("  LANGGRAPH TAX DOCUMENT ROUTING WORKFLOW — FreeLLMAPI LIVE VERIFICATION")
    print("================================================================================")
    print(f"FreeLLMAPI Endpoint: {base_url}")
    print(f"FreeLLMAPI Auth:     {api_key[:12]}...")

    # ── CASE 1: Complete W-2 Input (No Loop -> Finalize) ──
    print("\n" + "="*80)
    print("  CASE 1: COMPLETE W-2 INPUT (Expectation: No loop, routes to finalize)")
    print("="*80)
    w2_doc = (
        "Form W-2 Wage and Tax Statement 2025\n"
        "Employer: Acme Global Technologies LLC\n"
        "Employer Identification Number (EIN): 12-3456789\n"
        "Employee: Jane Doe (SSN: XXX-XX-4412)\n"
        "Box 1 Wages, tips, other compensation: $94,500.00\n"
        "Box 2 Federal income tax withheld: $16,800.00\n"
        "Box 16 State wages: $94,500.00\n"
        "Box 17 State income tax: $4,725.00"
    )
    case1_init: TaxDocState = {
        "raw_document": w2_doc,
        "doc_type": "Unknown",
        "extracted_fields": {},
        "missing_fields": [],
        "loop_count": 0,
        "max_loops": 2,
        "status": "INTAKE",
        "node_history": [],
        "clarification_message": None,
        "final_output": None,
        "supplemental_data": None
    }

    case1_state = dict(case1_init)
    print("[CASE 1] Starting LangGraph stream execution...")
    for step in app.stream(case1_init):
        node_name = list(step.keys())[0]
        case1_state.update(step[node_name])
        print(f"\n>>> [STATE TRANSITION AFTER: {node_name}]")
        print(json.dumps({
            "doc_type": case1_state.get("doc_type"),
            "extracted_fields": case1_state.get("extracted_fields"),
            "missing_fields": case1_state.get("missing_fields"),
            "loop_count": case1_state.get("loop_count"),
            "status": case1_state.get("status"),
            "node_history": case1_state.get("node_history")
        }, indent=2))

    print("\n[CASE 1 SUMMARY]")
    print(f"  Final Status:       {case1_state.get('status')}")
    print(f"  Node Execution Log: {' -> '.join(case1_state.get('node_history', []))}")
    print(f"  Did Loop Fire:      {case1_state.get('loop_count') > 0} (Loop Count: {case1_state.get('loop_count')})")
    print(f"  Final Output Deliverable:\n{json.dumps(case1_state.get('final_output'), indent=2)}")

    # ── CASE 2: 1099 Input Missing Payer TIN (Loops & Resolves) ──
    print("\n" + "="*80)
    print("  CASE 2: 1099 INPUT MISSING PAYER TIN (Expectation: Loops to request_missing_info, resolves, finalizes)")
    print("="*80)
    contractor_doc = (
        "Form 1099-NEC Nonemployee Compensation 2025\n"
        "RECIPIENT'S name: Alex Mercer Consulting\n"
        "RECIPIENT'S TIN: 456-78-9012\n"
        "Box 1 Nonemployee compensation: $58,200.00\n"
        "PAYER'S TIN: [REDACTED / UNKNOWN / NOT PROVIDED ON FORM]\n"
        "PAYER'S name: Cyberdyne Software Systems"
    )
    case2_init: TaxDocState = {
        "raw_document": contractor_doc,
        "doc_type": "Unknown",
        "extracted_fields": {},
        "missing_fields": [],
        "loop_count": 0,
        "max_loops": 2,
        "status": "INTAKE",
        "node_history": [],
        "clarification_message": None,
        "final_output": None,
        "supplemental_data": {"payer_tin": "98-7654321"}  # Taxpayer provides TIN upon clarification
    }

    case2_state = dict(case2_init)
    print("[CASE 2] Starting LangGraph stream execution...")
    for step in app.stream(case2_init):
        node_name = list(step.keys())[0]
        case2_state.update(step[node_name])
        print(f"\n>>> [STATE TRANSITION AFTER: {node_name}]")
        print(json.dumps({
            "doc_type": case2_state.get("doc_type"),
            "extracted_fields": case2_state.get("extracted_fields"),
            "missing_fields": case2_state.get("missing_fields"),
            "loop_count": case2_state.get("loop_count"),
            "status": case2_state.get("status"),
            "node_history": case2_state.get("node_history")
        }, indent=2))

    print("\n[CASE 2 SUMMARY]")
    print(f"  Final Status:       {case2_state.get('status')}")
    print(f"  Node Execution Log: {' -> '.join(case2_state.get('node_history', []))}")
    print(f"  Did Loop Fire:      {case2_state.get('loop_count') > 0} (Loop Count: {case2_state.get('loop_count')})")
    print(f"  Final Output Deliverable:\n{json.dumps(case2_state.get('final_output'), indent=2)}")

    # ── CASE 3: Ambiguous / Unknown Input (Terminal Clarification) ──
    print("\n" + "="*80)
    print("  CASE 3: AMBIGUOUS / UNKNOWN INPUT (Expectation: Routes to request_clarification, exits cleanly)")
    print("="*80)
    unknown_doc = (
        "Planet Fitness Monthly Membership Agreement & Electronic Funds Transfer Authorization\n"
        "Member Account: PF-9920148\n"
        "Member Name: Jordan Smith\n"
        "Monthly Dues: $24.99 per month\n"
        "Annual Fee: $49.00 billed every October\n"
        "This is not a tax document. Retain for personal records."
    )
    case3_init: TaxDocState = {
        "raw_document": unknown_doc,
        "doc_type": "Unknown",
        "extracted_fields": {},
        "missing_fields": [],
        "loop_count": 0,
        "max_loops": 2,
        "status": "INTAKE",
        "node_history": [],
        "clarification_message": None,
        "final_output": None,
        "supplemental_data": None
    }

    case3_state = dict(case3_init)
    print("[CASE 3] Starting LangGraph stream execution...")
    for step in app.stream(case3_init):
        node_name = list(step.keys())[0]
        case3_state.update(step[node_name])
        print(f"\n>>> [STATE TRANSITION AFTER: {node_name}]")
        print(json.dumps({
            "doc_type": case3_state.get("doc_type"),
            "extracted_fields": case3_state.get("extracted_fields"),
            "missing_fields": case3_state.get("missing_fields"),
            "loop_count": case3_state.get("loop_count"),
            "status": case3_state.get("status"),
            "node_history": case3_state.get("node_history")
        }, indent=2))

    print("\n[CASE 3 SUMMARY]")
    print(f"  Final Status:       {case3_state.get('status')}")
    print(f"  Node Execution Log: {' -> '.join(case3_state.get('node_history', []))}")
    print(f"  Final Output Deliverable:\n{json.dumps(case3_state.get('final_output'), indent=2)}")

    # ── CASE 4: Max-Loop Cap Enforcement (Exits to needs_manual_review) ──
    print("\n" + "="*80)
    print("  CASE 4: MAX-LOOP ITERATION CAP ENFORCEMENT (Expectation: Hits max 2 loops, exits to needs_manual_review)")
    print("="*80)
    unresolvable_doc = (
        "Form 1099-MISC Miscellaneous Information 2025\n"
        "RECIPIENT: Alpha Beta Consulting\n"
        "Box 3 Other income: $15,000.00\n"
        "PAYER'S TIN: [PERMANENTLY MISSING / NO RESPONSE]"
    )
    case4_init: TaxDocState = {
        "raw_document": unresolvable_doc,
        "doc_type": "Unknown",
        "extracted_fields": {},
        "missing_fields": [],
        "loop_count": 0,
        "max_loops": 2,
        "status": "INTAKE",
        "node_history": [],
        "clarification_message": None,
        "final_output": None,
        "supplemental_data": None  # No supplemental data -> fails completeness repeatedly
    }

    case4_state = dict(case4_init)
    print("[CASE 4] Starting LangGraph stream execution...")
    for step in app.stream(case4_init):
        node_name = list(step.keys())[0]
        case4_state.update(step[node_name])
        print(f"\n>>> [STATE TRANSITION AFTER: {node_name}]")
        print(json.dumps({
            "doc_type": case4_state.get("doc_type"),
            "extracted_fields": case4_state.get("extracted_fields"),
            "missing_fields": case4_state.get("missing_fields"),
            "loop_count": case4_state.get("loop_count"),
            "status": case4_state.get("status"),
            "node_history": case4_state.get("node_history")
        }, indent=2))

    print("\n[CASE 4 SUMMARY]")
    print(f"  Final Status:       {case4_state.get('status')}")
    print(f"  Node Execution Log: {' -> '.join(case4_state.get('node_history', []))}")
    print(f"  Loops Attempted:    {case4_state.get('loop_count')} (Cap: {case4_state.get('max_loops')})")
    print(f"  Final Output Deliverable:\n{json.dumps(case4_state.get('final_output'), indent=2)}")

    # ── TOTAL TELEMETRY SUMMARY ──
    print("\n" + "="*80)
    print("  GLOBAL FREELLMAPI USAGE & COST TELEMETRY")
    print("="*80)
    print(f"Total Live LLM Calls Dispatched: {telemetry['total_calls']}")
    print(f"Total Prompt Tokens:             {telemetry['prompt_tokens']}")
    print(f"Total Completion Tokens:         {telemetry['completion_tokens']}")
    print(f"Total Combined Tokens:           {telemetry['total_tokens']}")
    print(f"Dispatched Model Architectures:  {', '.join(telemetry['models_used']) if telemetry['models_used'] else 'N/A'}")
    print("Total Incurred Cost:             $0.00 (Zero-Cost FreeLLMAPI Sovereign Gateway)")
