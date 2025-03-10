# coding: utf-8

import os
import getpass

def _set_if_undefined(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"Please provide your {var}:")

def setup_environment():
    # _set_if_undefined("OPENAI_API_KEY")
    _set_if_undefined("OPENROUTER_API_KEY")
    _set_if_undefined("TAVILY_API_KEY")
