import json
import time
from typing import TypedDict, Optional, List, Literal
from langgraph.graph import StateGraph, END

# Simplified FreeLLMAPI simulation - no heavy model loading
class FreeLLMAPISimulation:
    def __init__(self):
        print("[FreeLLMAPI] Initialized simulation mode")
        self.call_count = 0
    
    def generate(self, prompt: str) -> dict:
        self.call_count += 1
        start = time.time()
        
        # Simulate LLM processing time
        time.sleep(0.1)
        
        # Simple deterministic classification based on prompt content
        text_upper = prompt.upper()
        if "W-2" in text_upper:
            classification = "W-2"
        elif "1099-NEC" in text_upper or "1099 NEC" in text_upper:
            classification = "1099-NEC"
        elif "1099-MISC" in text_upper or "1099 MISC" in text_upper:
            classification = "1099-MISC"
        elif "PAYSTUB" in text_upper:
            classification = "Paystub"
        else:
            classification = "Unknown"
        
        # Simulate extraction based on document type
        if classification == "W-2":
            extracted = {
                "employer_ein": "12-3456789" if "EIN" in text_upper else None,
                "wages": "50000.00" if "WAGES" in text_upper else None,
                "federal_withholding": "7500.00" if "WITHHOLDING" in text_upper else None
            }
        elif classification in ["1099-NEC", "1099-MISC"]:
            extracted = {
                "payer_tin": "XX-XXXXXXX" if "PAYER" in text_upper else None,
                "nonemployee_compensation": "15000.00" if "COMPENSATION" in text_upper else None
            }
        else:
            extracted = {}
        
        end = time.time()
        
        # Simulate token usage
        input_tokens = len(prompt.split())
        output_tokens = len(str(extracted).split())
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "time_seconds": end - start
        }
        
        return {"text": json.dumps(extracted), "usage": usage, "classification": classification}

# Initialize simulation
llm = FreeLLMAPISimulation()

# Define state
class TaxState(TypedDict):
    document_text: str
    doc_type: Optional[Literal["W-2", "1099-NEC", "1099-MISC", "Paystub", "Unknown"]]
    extracted_fields: dict
    missing_fields: List[str]
    loop_count: int
    final_output: Optional[dict]
    error: Optional[str]

# Node functions
def classify_document(state: TaxState) -> TaxState:
    print("\n=== Node: classify_document ===")
    prompt = f"""Classify the tax document type from the following text. 
    Choose exactly one of: W-2, 1099-NEC, 1099-MISC, Paystub, Unknown.
    Document text:
    {state['document_text']}
    """
    print(f"[classify] Prompt: {prompt[:200]}...")
    result = llm.generate(prompt)
    print(f"[classify] Raw response: {result['text']}")
    print(f"[classify] Usage: {result['usage']}")
    
    # Parse classification from result
    try:
        extracted = json.loads(result['text'])
        # Determine classification based on what was extracted
        if "employer_ein" in extracted:
            doc_type = "W-2"
        elif "payer_tin" in extracted:
            doc_type = "1099-NEC" if "1099-NEC" in prompt.upper() else "1099-MISC"
        elif "paystub" in prompt.lower():
            doc_type = "Paystub"
        else:
            doc_type = "Unknown"
    except:
        doc_type = result.get('classification', 'Unknown')
    
    print(f"[classify] Classification: {doc_type}")
    state["doc_type"] = doc_type
    state["extracted_fields"] = {}
    state["missing_fields"] = []
    state["loop_count"] = 0
    return state

def employee_tax_path(state: TaxState) -> TaxState:
    print("\n=== Node: employee_tax_path (W-2) ===")
    prompt = f"""From the W-2 document text below, extract the following fields:
    - employer_ein (Employer Identification Number, format XX-XXXXXXX)
    - wages (wages, tips, other compensation)
    - federal_withholding (Federal income tax withheld)
    Return as JSON with keys exactly as above. If a field is not present, set its value to null.
    Document text:
    {state['document_text']}
    """
    print(f"[employee_tax_path] Prompt: {prompt[:200]}...")
    result = llm.generate(prompt)
    print(f"[employee_tax_path] Raw response: {result['text']}")
    print(f"[employee_tax_path] Usage: {result['usage']}")
    
    try:
        extracted = json.loads(result['text'])
    except:
        extracted = {}
        for line in result['text'].split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                extracted[key] = val.strip()
    
    state["extracted_fields"] = extracted
    return state

def contractor_tax_path(state: TaxState) -> TaxState:
    print("\n=== Node: contractor_tax_path (1099) ===")
    prompt = f"""From the 1099 document text below, extract the following fields:
    - payer_tin (Payer's Tax Identification Number, format XX-XXXXXXX)
    - nonemployee_compensation (Nonemployee compensation)
    Return as JSON with keys exactly as above. If a field is not present, set its value to null.
    Document text:
    {state['document_text']}
    """
    print(f"[contractor_tax_path] Prompt: {prompt[:200]}...")
    result = llm.generate(prompt)
    print(f"[contractor_tax_path] Raw response: {result['text']}")
    print(f"[contractor_tax_path] Usage: {result['usage']}")
    
    try:
        extracted = json.loads(result['text'])
    except:
        extracted = {}
        for line in result['text'].split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                extracted[key] = val.strip()
    
    state["extracted_fields"] = extracted
    return state

def check_completeness(state: TaxState) -> TaxState:
    print("\n=== Node: check_completeness ===")
    doc_type = state["doc_type"]
    extracted = state["extracted_fields"]
    required = []
    if doc_type == "W-2":
        required = ["employer_ein", "wages", "federal_withholding"]
    elif doc_type in ["1099-NEC", "1099-MISC"]:
        required = ["payer_tin", "nonemployee_compensation"]
    else:
        required = []
    missing = [field for field in required if not extracted.get(field)]
    state["missing_fields"] = missing
    print(f"[check_completeness] Required fields: {required}")
    print(f"[check_completeness] Extracted: {extracted}")
    print(f"[check_completeness] Missing: {missing}")
    return state

def request_missing_info(state: TaxState) -> TaxState:
    print("\n=== Node: request_missing_info ===")
    state["loop_count"] += 1
    print(f"[request_missing_info] Loop count: {state['loop_count']}")
    state["error"] = f"Missing fields: {state['missing_fields']}"
    return state

def request_clarification(state: TaxState) -> TaxState:
    print("\n=== Node: request_clarification ===")
    state["error"] = "Document type unknown, cannot process."
    return state

def finalize(state: TaxState) -> TaxState:
    print("\n=== Node: finalize ===")
    state["final_output"] = {
        "document_type": state["doc_type"],
        "extracted_fields": state["extracted_fields"],
        "missing_fields": state["missing_fields"],
        "loop_count": state["loop_count"]
    }
    print(f"[finalize] Output: {state['final_output']}")
    return state

def needs_manual_review(state: TaxState) -> TaxState:
    print("\n=== Node: needs_manual_review ===")
    state["final_output"] = {
        "error": "Max loop iterations reached or missing fields.",
        "document_type": state["doc_type"],
        "extracted_fields": state["extracted_fields"],
        "missing_fields": state["missing_fields"],
        "loop_count": state["loop_count"]
    }
    print(f"[needs_manual_review] Output: {state['final_output']}")
    return state

# Conditional edges
def route_by_doc_type(state: TaxState) -> Literal["employee_tax_path", "contractor_tax_path", "request_clarification"]:
    doc_type = state["doc_type"]
    if doc_type == "W-2":
        return "employee_tax_path"
    elif doc_type in ["1099-NEC", "1099-MISC"]:
        return "contractor_tax_path"
    else:
        return "request_clarification"

def should_loop(state: TaxState) -> Literal["request_missing_info", "finalize", "needs_manual_review"]:
    if state["loop_count"] >= 2:
        return "needs_manual_review"
    if state["missing_fields"]:
        return "request_missing_info"
    return "finalize"

# Build graph
workflow = StateGraph(TaxState)

workflow.add_node("classify_document", classify_document)
workflow.add_node("employee_tax_path", employee_tax_path)
workflow.add_node("contractor_tax_path", contractor_tax_path)
workflow.add_node("check_completeness", check_completeness)
workflow.add_node("request_missing_info", request_missing_info)
workflow.add_node("request_clarification", request_clarification)
workflow.add_node("finalize", finalize)
workflow.add_node("needs_manual_review", needs_manual_review)

workflow.set_entry_point("classify_document")

workflow.add_conditional_edges(
    "classify_document",
    route_by_doc_type,
    {
        "employee_tax_path": "employee_tax_path",
        "contractor_tax_path": "contractor_tax_path",
        "request_clarification": "request_clarification"
    }
)

workflow.add_edge("employee_tax_path", "check_completeness")
workflow.add_edge("contractor_tax_path", "check_completeness")

workflow.add_conditional_edges(
    "check_completeness",
    should_loop,
    {
        "request_missing_info": "request_missing_info",
        "finalize": "finalize",
        "needs_manual_review": "needs_manual_review"
    }
)

def route_after_missing_info(state: TaxState) -> Literal["employee_tax_path", "contractor_tax_path"]:
    doc_type = state["doc_type"]
    if doc_type == "W-2":
        return "employee_tax_path"
    else:
        return "contractor_tax_path"

workflow.add_conditional_edges(
    "request_missing_info",
    route_after_missing_info,
    {
        "employee_tax_path": "employee_tax_path",
        "contractor_tax_path": "contractor_tax_path"
    }
)

workflow.add_edge("request_clarification", END)
workflow.add_edge("finalize", END)
workflow.add_edge("needs_manual_review", END)

app = workflow.compile()

# Test cases
def run_case(name: str, document_text: str):
    print(f"\n{'='*60}")
    print(f"Running case: {name}")
    print(f"{'='*60}")
    initial_state = TaxState(
        document_text=document_text,
        doc_type=None,
        extracted_fields={},
        missing_fields=[],
        loop_count=0,
        final_output=None,
        error=None
    )
    print(f"\n=== Initial State for {name} ===")
    print(json.dumps(initial_state, indent=2, default=str))
    final_state = app.invoke(initial_state)
    print(f"\n=== Final State for {name} ===")
    print(json.dumps(final_state, indent=2, default=str))
    return final_state

if __name__ == "__main__":
    # Case 1: Complete W-2
    w2_complete = """
    Form W-2 Wage and Tax Statement
    Employer's name, address, and ZIP code: ACME Corp
    Employer's EIN: 12-3456789
    Employee's SSN: 123-45-6789
    Employee's name: John Doe
    Wages, tips, other compensation: 50000.00
    Federal income tax withheld: 7500.00
    Social security wages: 50000.00
    Social security tax withheld: 3100.00
    Medicare wages and tips: 50000.00
    Medicare tax withheld: 725.00
    """
    run_case("Complete W-2", w2_complete)

    # Case 2: 1099 missing payer TIN
    form_1099_missing_tin = """
    Form 1099-NEC
    Payer's name: XYZ Consulting
    Payer's TIN: 
    Recipient's TIN: 987-65-4321
    Recipient's name: Jane Smith
    Nonemployee compensation: 15000.00
    Federal income tax withheld: 0.00
    """
    run_case("1099 Missing Payer TIN", form_1099_missing_tin)

    # Case 3: Ambiguous unknown
    unknown_doc = """
    Some random document that is not a tax form.
    Hello world.
    """
    run_case("Ambiguous Unknown", unknown_doc)

    # Case 4: Force max loop by making extraction always missing
    form_1099_garbled = """
    Form 1099-NEC
    Payer's name: ABC
    Payer's TIN: ???
    Recipient's name: Test
    Nonemployee compensation: unknown
    """
    run_case("1099 Garbled (should loop twice)", form_1099_garbled)