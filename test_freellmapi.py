import json
import os
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import torch

print("Testing FreeLLMAPI initialization...")

# Initialize tokenizer and model
model_name = "google/flan-t5-tiny"
print(f"Loading tokenizer for {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
print(f"Loading model for {model_name}...")
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
print("Model loaded successfully")

# Create pipeline
pipe = pipeline(
    "text2text-generation",
    model=model,
    tokenizer=tokenizer,
    max_length=100,
    do_sample=False,
    device=0 if torch.cuda.is_available() else -1
)

print("Pipeline created")

# Test generation
system_prompt = "You are an expert tax document classifier. Determine document type. Return JSON with doc_type field."
prompt = "Document content: Form W-2 Employee Name: John Doe Employer: ABC Corp"
full_prompt = f"{system_prompt}\n{prompt}"

print("\n--- Test LLM Call ---")
print(f"Prompt: {full_prompt}")

inputs = tokenizer(full_prompt, return_tensors="pt", truncation=True, max_length=512)
if torch.cuda.is_available():
    inputs = {k: v.cuda() for k, v in inputs.items()}
outputs = model.generate(**inputs, num_return_sequences=1, do_sample=False)
response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f"Response: {response_text}")

# Test with actual FreeLLMAPI wrapper
print("\n--- Testing FreeLLMAPI wrapper ---")
from tax_workflow_runnable import FreeLLMAPI
llm = FreeLLMAPI(model_name)
response = llm.generate(prompt, system_prompt)
print(f"Wrapper response: {response['text']}")
print(f"Tokens: {response['prompt_tokens']}, {response['completion_tokens']}")