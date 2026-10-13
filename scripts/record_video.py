import os
from playwright.sync_api import sync_playwright


def record(html_abs_path, duration_seconds, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=output_dir,
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.goto("file://" + html_abs_path)
        page.wait_for_timeout(int((duration_seconds + 1.5) * 1000))
        video_path = page.video.path()
        context.close()
        browser.close()
        return video_path
