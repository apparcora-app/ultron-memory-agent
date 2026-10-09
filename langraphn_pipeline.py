# Forwarding alias for langgraph_pipeline.py
import runpy, sys, os
_target = os.path.join(os.path.dirname(__file__), "langgraph_pipeline.py")
if __name__ == "__main__":
    runpy.run_path(_target, run_name="__main__")
else:
    from langgraph_pipeline import *
