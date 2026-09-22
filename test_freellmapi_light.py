import json
import os
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import torch

print("Testing FreeLLMAPI with smaller model...")

# Try even smaller model
model_name = "google/flan-t5-base"
print(f"Loading tokenizer for {model_name}...")
tokenizer = AutoTokenizer.from_pretrained(model_name)
print(f"Loading model for {model_name}...")
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
print("Model loaded successfully")

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
