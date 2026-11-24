"""Screenshot a page of the running app (dev helper).
Usage: python tools/shot.py <path> <out.png> [--click selector] [--wait ms] [--eval js]"""
import argparse

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("path")
ap.add_argument("out")
ap.add_argument("--wait", type=int, default=1500)
ap.add_argument("--eval", action="append", default=[])
ap.add_argument("--click", action="append", default=[])
ap.add_argument("--width", type=int, default=1440)
ap.add_argument("--height", type=int, default=900)
a = ap.parse_args()

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": a.width, "height": a.height})
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
    page.goto(f"http://localhost:5173{a.path}")
    page.wait_for_timeout(a.wait)
    for sel in a.click:
        page.click(sel)
        page.wait_for_timeout(600)
    for js in a.eval:
        page.evaluate(js)
        page.wait_for_timeout(600)
    page.screenshot(path=a.out)
    for line in logs[:20]:
        print(line)
    b.close()
