import requests
import re

session = requests.Session()
# Vast.ai login actually goes to https://console.vast.ai/api/v0/users/auth/ or similar?
# Let's try with playwright.
