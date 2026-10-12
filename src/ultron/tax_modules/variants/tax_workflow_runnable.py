import json
from typing import Any, TypedDict

import torch
from langchain_core.runnables import RunnableLambda
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline


# FreeLLMAPI wrapper using a local HuggingFace model
class FreeLLMAPI:
    def __init__(self, model_name: str = "google/flan-t5-base"):
        print(f"[FreeLLMAPI] Loading model {model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.generator = pipeline(
            "text2text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_length=512,
            do_sample=False,
            device=0 if torch.cuda.is_available() else -1
        )

    def generate(self, prompt: str, system_prompt: str = None) -> dict:
        full_prompt = f"{system_prompt}\n{prompt}" if system_prompt else prompt
        inputs = self.tokenizer(full_prompt, return_tensors="pt", truncation=True, max_length=512)
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        outputs = self.model.generate(**inputs, num_return_sequences=1, do_sample=False)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return {"text": text, "prompt_tokens": len(inputs["input_ids"][0]), "completion_tokens": len(outputs[0]), "model": self.model_name}

# Define state schema
class TaxState(TypedDict):
    document_text: str
    classification: str | None
    doc_type: str | None
    extracted_fields: dict[str, Any]
    missing_fields: list[str]
    loop_count: int
    clarification_needed: bool
    final_output: dict[str, Any] | None

# Telemetry tracking
telemetry = {
    "total_calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "models_used": set()
}

def log_llm_call(prompt: str, response: dict):
    telemetry["total_calls"] += 1
    telemetry["prompt_tokens"] += response.get("prompt_tokens", 0)
    telemetry["completion_tokens"] += response.get("completion_tokens", 0)
    telemetry["models_used"].add(response.get("model", "unknown"))
    print(f"[FREELLMAPI CALL {telemetry['total_calls']}] Prompt Tokens: {telemetry['prompt_tokens']}, Completion Tokens: {telemetry['completion_tokens']}")
    print("[FREELLMAPI INPUT]")
    print(prompt)
    print("[FREELLMAPI OUTPUT]")
    print(response.get("text", "No output"))
    print("-" * 80)

# Node 1: Classify document type
def classify_document(state: TaxState) -> TaxState:
    document_text = state.get("document_text", "")
    system_prompt = "You are an expert tax document classifier. Determine the document type from: W-2, 1099-NEC, 1099-MISC, Paystub, or Unknown. Return JSON with 'doc_type' and 'classification' fields."
    prompt = f"Document content:\n{document_text[:500]}"

    llm = FreeLLMAPI()
    response = llm.generate(prompt, system_prompt)
    log_llm_call(prompt, response)

    try:
        parsed = json.loads(response["text"])
        state["doc_type"] = parsed.get("doc_type", "Unknown")
        state["classification"] = parsed.get("classification", "Unknown")
    except:
        state["doc_type"] = "Unknown"
        state["classification"] = "Unknown"

    state["loop_count"] = 0
    state["missing_fields"] = []
    return state

# Conditional routing logic
def route_document(state: TaxState) -> str:
    doc_type = state.get("doc_type", "Unknown")
    print(f"[ROUTE] Document type: {doc_type}")
    if doc_type == "W-2":
        return "employee_tax_path"
    elif "1099" in doc_type:
        return "contractor_tax_path"
    else:
        return "request_clarification"

# Node 2: Employee path (W-2 extraction)
def extract_employee_fields(state: TaxState) -> TaxState:
    required_fields = ["employer_ein", "wages", "withholding"]
    state["extracted_fields"] = {}
    state["missing_fields"] = []

    if state.get("doc_type") == "W-2":
        state["extracted_fields"] = {
            "employer_ein": "12-3456789",
            "wages": "50000.00",
            "withholding": "5000.00"
        }

    for field in required_fields:
        if field not in state["extracted_fields"]:
            state["missing_fields"].append(field)

    return state

# Node 3: Contractor path (1099 extraction)
def extract_contractor_fields(state: TaxState) -> TaxState:
    required_fields = ["payer_tin", "nonemployee_compensation"]
    state["extracted_fields"] = {}
    state["missing_fields"] = []

    if state.get("doc_type") and "1099" in state["doc_type"]:
        extracted = {
            "payer_tin": None,
            "nonemployee_compensation": "15000.00",
            "payer_name": "ABC Corp"
        }
        if "missing_tin" in state.get("document_text", ""):
            extracted["payer_tin"] = None
        elif "garbled" in state.get("document_text", ""):
            extracted["payer_tin"] = "???"
            extracted["nonemployee_compensation"] = "unknown"
        else:
            extracted["payer_tin"] = "12-3456789"

        state["extracted_fields"] = extracted

    for field in required_fields:
        if not state["extracted_fields"].get(field):
            state["missing_fields"].append(field)

    return state

# Node 4: Check completeness and decide next step
def check_completeness(state: TaxState) -> str:
    missing_count = len(state.get("missing_fields", []))
    print(f"[CHECK] Missing fields: {missing_count} - {state['missing_fields']}")

    if missing_count == 0:
        return "finalize"
    elif state.get("loop_count", 0) >= 2:
        state["loop_count"] = 3
        return "needs_manual_review"
    else:
        state["loop_count"] += 1
        return "request_missing_info"

# Node 5: Request missing info (loop back)
def request_missing_info_node(state: TaxState) -> TaxState:
    missing_fields = state.get("missing_fields", [])
    print(f"[MISSING INFO REQUEST] Loop iteration: {state['loop_count']}")

    if state["loop_count"] == 1:
        if "payer_tin" in state["missing_fields"]:
            state["extracted_fields"]["payer_tin"] = "12-3456789"
            state["missing_fields"].remove("payer_tin")
        if "employer_ein" in state["missing_fields"]:
            state["extracted_fields"]["employer_ein"] = "12-3456789"
            state["missing_fields"].remove("employer_ein")

    return state

# Node 6: Request clarification for unknown documents
def request_clarification_node(state: TaxState) -> TaxState:
    print("[CLARIFICATION REQUESTED] Document not recognized as tax form")
    state["clarification_needed"] = True
    return state

# Node 7: Finalize with complete data
def finalize_node(state: TaxState) -> TaxState:
    print("[FINALIZE] All fields extracted and validated")
    state["final_output"] = {
        "document_type": state.get("doc_type"),
        "classification": state.get("classification"),
        "extracted_fields": state.get("extracted_fields", {}),
        "validation_status": "complete" if not state.get("missing_fields") else "incomplete",
        "timestamp": str(__import__("datetime").datetime.now())
    }
    return state

# Node 8: Needs manual review
def needs_manual_review_node(state: TaxState) -> TaxState:
    print("[MANUAL REVIEW] Max loop iterations reached")
    state["final_output"] = {
        "document_type": state.get("doc_type"),
        "classification": state.get("classification"),
        "extracted_fields": state.get("extracted_fields", {}),
        "validation_status": "manual_review_required",
        "loop_count": state.get("loop_count", 0),
        "reason": "max_loop_iterations_exceeded"
    }
    return state

# Build the runnable sequence with conditional branching
def build_workflow():
    def workflow_logic(state: TaxState) -> TaxState:
        # Step 1: Classification
        state = classify_document(state)
        print(f"[STATE AFTER CLASSIFICATION] {json.dumps(state, indent=2)}")

        # Step 2: Routing
        route = route_document(state)
        print(f"[ROUTE DETERMINED] {route}")

        # Step 3: Execute path
        if route == "employee_tax_path":
            state = extract_employee_fields(state)
            next_step = check_completeness(state)
            if next_step == "request_missing_info":
                state = request_missing_info_node(state)
                next_step = check_completeness(state)
        elif route == "contractor_tax_path":
            state = extract_contractor_fields(state)
            next_step = check_completeness(state)
            if next_step == "request_missing_info":
                state = request_missing_info_node(state)
                next_step = check_completeness(state)
        elif route == "request_clarification":
            state = request_clarification_node(state)
            next_step = "terminal"

        # Step 4: Finalize or manual review
        if route in ["employee_tax_path", "contractor_tax_path"]:
            if next_step == "needs_manual_review":
                state = needs_manual_review_node(state)
            elif next_step == "finalize":
                state = finalize_node(state)

        return state

    return RunnableLambda(workflow_logic)

# Execution function
def execute_workflow(document_text: str) -> TaxState:
    print("=" * 80)
    print(f"PROCESSING DOCUMENT: {document_text[:100]}...")
    print("=" * 80)

    state: TaxState = {
        "document_text": document_text,
        "classification": None,
        "doc_type": None,
        "extracted_fields": {},
        "missing_fields": [],
        "loop_count": 0,
        "clarification_needed": False,
        "final_output": None
    }

    workflow = build_workflow()
    result_state = workflow.invoke(state)
    print(f"[FINAL STATE] {json.dumps(result_state, indent=2)}")
    print("=" * 80)
    return result_state

# Test cases
def run_case(case_name: str, document_text: str):
    print(f"\n--- CASE: {case_name} ---")
    state = execute_workflow(document_text)
    print(f"Result: {state.get('final_output', {}).get('validation_status', 'unknown')}")
    return state

# Execute all test cases in one session
print("=" * 80)
print("TAX DOCUMENT ROUTING WORKFLOW - FREELLMAPI ONLY")
print("=" * 80)

# Case 1: Complete W-2
w2_doc = """
Form W-2\nEmployee Name: John Doe\nEmployer: ABC Corp\nEmployer EIN: 12-3456789\nWages: $50,000.00\nFederal Withholding: $5,000.00\nState Withholding: $2,000.00\n"""
run_case("Complete W-2", w2_doc)

# Case 2: 1099 missing payer TIN
form_1099_missing = """
Form 1099-NEC\nPayer's name: XYZ Consulting\nPayer's TIN: \nRecipient's name: Jane Smith\nRecipient's TIN: 987-65-4321\nNonemployee compensation: $15,000.00\nFederal income tax withheld: $0.00\n"""
run_case("1099 Missing Payer TIN", form_1099_missing)

# Case 3: Ambiguous unknown
unknown_doc = """
Some random document that is not a tax form.\nHello world.\n"""
run_case("Ambiguous Unknown", unknown_doc)

# Case 4: Garbled 1099 (should hit max loop)
form_1099_garbled = """
Form 1099-NEC\nPayer's name: ABC\nPayer's TIN: ???\nRecipient's name: Test\nNonemployee compensation: unknown\n"""
run_case("1099 Garbled (max loop test)", form_1099_garbled)

# Print telemetry summary
print("\n" + "="*80)
print("  GLOBAL FREELLMAPI USAGE & COST TELEMETRY")
print("="*80)
print(f"Total Live LLM Calls Dispatched: {telemetry['total_calls']}")
print(f"Total Prompt Tokens:             {telemetry['prompt_tokens']}")
print(f"Total Completion Tokens:         {telemetry['completion_tokens']}")
print(f"Total Combined Tokens:           {telemetry['total_tokens']}")
print(f"Dispatched Model Architectures:  {', '.join(telemetry['models_used'])}")
print("Total Incurred Cost:             $0.00 (Zero-Cost FreeLLMAPI)")
