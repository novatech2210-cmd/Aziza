from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    # Vast.ai login page
    print("Navigating to login...")
    page.goto("https://cloud.vast.ai/login/")
    time.sleep(2)
    # The actual login modal or page might have specific inputs. 
    # Try looking for username/password fields.
    print("Filling credentials...")
    try:
        page.fill("input[type='email']", "stulkun@mail.ru", timeout=5000)
        page.fill("input[type='password']", "vastai0505")
        page.click("button:has-text('Log in')")
    except Exception as e:
        print("Login form not found. Retrying with different selectors...")
        try:
            page.fill("[name='email']", "stulkun@mail.ru", timeout=5000)
            page.fill("[name='password']", "vastai0505")
            page.click("button[type='submit']")
        except Exception as e2:
            print("Failed to find inputs. Page content snippet:")
            print(page.content()[:1000])
            browser.close()
            exit(1)

    print("Waiting for login...")
    time.sleep(5)
    
    # Go to instances
    print("Navigating to instances...")
    page.goto("https://cloud.vast.ai/instances/")
    time.sleep(5)
    
    print("Instances page HTML snippet:")
    content = page.content()
    # Search for ssh commands in the page content
    import re
    ssh_commands = set(re.findall(r'ssh [a-zA-Z0-9_\-\.\@\s]+ -p \d+', content))
    print("Found SSH commands:", ssh_commands)

    # Let's also dump the API key if possible
    # We can fetch it from localStorage
    local_storage = page.evaluate("() => JSON.stringify(window.localStorage)")
    print("Local Storage:", local_storage)
    
    browser.close()
