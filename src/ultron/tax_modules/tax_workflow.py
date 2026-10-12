import json
import time
from typing import Literal, TypedDict

import torch
from langgraph.graph import END, StateGraph
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
            device=0 if torch.cuda.is_available() else -1,
        )
        print("[FreeLLMAPI] Model loaded.")

    def generate(self, prompt: str) -> dict:
        start = time.time()
        result = self.generator(prompt, max_length=200, num_return_sequences=1)
        generated_text = result[0]['generated_text']
        end = time.time()
        # Token counting
        input_tokens = len(self.tokenizer.encode(prompt))
        output_tokens = len(self.tokenizer.encode(generated_text))
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "time_seconds": end - start
        }
        return {"text": generated_text.strip(), "usage": usage}

# Define state
class TaxState(TypedDict):
    document_text: str
    doc_type: Literal["W-2", "1099-NEC", "1099-MISC", "Paystub", "Unknown"] | None
    extracted_fields: dict
    missing_fields: list[str]
    loop_count: int
    final_output: dict | None
    error: str | None

# Initialize FreeLLMAPI
llm = FreeLLMAPI()

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
    # Extract classification
    text_upper = result['text'].upper()
    if "W-2" in text_upper:
        doc_type = "W-2"
    elif "1099-NEC" in text_upper or "1099 NEC" in text_upper:
        doc_type = "1099-NEC"
    elif "1099-MISC" in text_upper or "1099 MISC" in text_upper:
        doc_type = "1099-MISC"
    elif "PAYSTUB" in text_upper:
        doc_type = "Paystub"
    else:
        doc_type = "Unknown"
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
    # Try to parse JSON
    import json
    try:
        extracted = json.loads(result['text'])
    except:
        # Fallback: simple parsing
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
    import json
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
    # In a real system, we would ask user; here we just note
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

workflow.add_edge("request_missing_info", "employee_tax_path")  # loop back to same path? Actually we need to go back to extraction?
# For simplicity, loop back to the same extraction node based on doc type.
# We'll instead loop back to the appropriate extraction node.
# But we can't have dynamic edges easily; we'll loop back to classify? Not ideal.
# Let's change: after request_missing_info, we go back to the extraction node based on doc_type.
# We'll need to add a node that routes again.
# For simplicity, we'll loop back to the extraction node (employee_tax_path or contractor_tax_path) based on doc_type.
# We'll add a conditional edge from request_missing_info.

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
    # We'll create a 1099 where the LLM fails to extract payer_tin and nonemployee_compensation
    # We'll trick by using a document that looks like 1099 but with missing fields that LLM can't extract.
    # Since we can't control LLM perfectly, we'll just rely on loop count.
    # We'll run a case where missing fields persist after two loops.
    # We'll use a document that is clearly 1099 but with garbled text so extraction fails.
    form_1099_garbled = """
    Form 1099-NEC
    Payer's name: ABC
    Payer's TIN: ???
    Recipient's name: Test
    Nonemployee compensation: unknown
    """
    run_case("1099 Garbled (should loop twice)", form_1099_garbled)
