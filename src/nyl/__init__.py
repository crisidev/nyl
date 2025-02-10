import subprocess
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Original subprocess.run
original_subprocess_run = subprocess.run

def logged_subprocess_run(*args, **kwargs):
    # Capture the stack trace
    stack_trace = traceback.format_stack()

    # Log the stack trace
    logging.error("Subprocess call stack trace:\n" + ''.join(stack_trace))

    logging.error(f"Running command: {args[0]}")
    result = original_subprocess_run(*args, **kwargs)
    logging.error(f"Return code: {result.returncode}")
    logging.error(f"Output: {result.stdout}")
    logging.error(f"Error: {result.stderr}")
    
    return result

# Monkey patch subprocess.run
subprocess.run = logged_subprocess_run

from importlib.metadata import version

__version__ = version("nyl")
