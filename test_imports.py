import sys
import os
sys.path.insert(0, os.getcwd())

try:
    from src.models import Storylet
    print("SUCCESS: src.models.Storylet imported")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"FAILURE: {e}")

try:
    from src.config import settings
    print(f"SUCCESS: src.config.settings imported (model: {settings.llm_model})")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"FAILURE: {e}")
