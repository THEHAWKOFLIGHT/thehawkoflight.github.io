"""
Capture the ADA alignment canvas animation as an MP4.
Uses Selenium (headless Chrome) to render frames, then assembles with imageio/ffmpeg.
"""
import os, sys, time, base64, io
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image
import imageio

# Config
TOTAL = 34.0        # animation duration in seconds
FPS = 60            # frames per second
DPR = 2             # device pixel ratio override for consistent capture
FRAME_COUNT = int(TOTAL * FPS)

def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument(f"--force-device-scale-factor={DPR}")
    opts.add_argument("--window-size=1800,1500")
    opts.add_argument("--hide-scrollbars")
    opts.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    driver = webdriver.Chrome(options=opts)
    driver.set_script_timeout(300)
    return driver

def capture_canvas_frame(driver):
    """Grab the canvas as a PNG data URI and return a PIL Image."""
    data_url = driver.execute_script("""
        var c = document.getElementById('alignCanvas');
        return c ? c.toDataURL('image/png') : null;
    """)
    if not data_url:
        return None
    header = "data:image/png;base64,"
    img_data = base64.b64decode(data_url[len(header):])
    return Image.open(io.BytesIO(img_data))

def patch_and_capture(driver, output_path, html_path, dark=False, embed=True):
    """Patch the HTML to expose render, then capture frames as MP4.

    html_path: absolute path to the index.html to capture.
    dark:  True for dark theme (main site), False for light (only works if page supports it).
    embed: True to load with ?viz query param, False for standalone.
    """

    with open(html_path, 'r', encoding='utf-8') as f:
        original = f.read()

    # Patch: expose render, initData, stop on window, and don't auto-play
    patched = original.replace(
        "initData();render(0);",
        "initData();render(0);window._vizRender=render;window._vizInit=initData;window._vizStop=stop;"
        "window._vizSetDark=function(d){DARK=!!d;applyTheme();};"
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(patched)

    try:
        url = "file:///" + html_path.replace("\\", "/") + ("?viz" if embed else "")
        driver.get(url)
        time.sleep(2)

        # Stop auto-play
        driver.execute_script("if(window._vizStop) window._vizStop();")
        time.sleep(0.5)

        # Set theme (dark for main site, light for project page)
        if dark:
            driver.execute_script("window._vizSetDark(true);")
            time.sleep(0.3)

        # Re-init data and capture frames
        driver.execute_script("window._vizInit(); window._vizRender(0);")
        time.sleep(0.3)

        frames = []
        for i in range(FRAME_COUNT):
            t = i / FPS
            driver.execute_script(f"window._vizRender({t})")
            time.sleep(0.03)
            img = capture_canvas_frame(driver)
            if img:
                frames.append(np.array(img.convert('RGB')))
            if (i + 1) % (FPS * 5) == 0:
                print(f"  Captured {i+1}/{FRAME_COUNT} frames ({t:.1f}s)")

        if frames:
            print(f"Assembling {len(frames)} frames into {output_path}")
            writer = imageio.get_writer(
                output_path,
                fps=FPS,
                codec="libx264",
                pixelformat="yuv420p",
                quality=None,
                bitrate="8M",
            )
            for fr in frames:
                writer.append_data(fr)
            writer.close()
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print(f"Saved {output_path} ({size_mb:.1f} MB)")
            return True
        return False
    finally:
        # Restore original
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(original)
        print(f"Restored original {html_path}")

def main():
    base = r"C:\Users\kai_nelson\Desktop\website"

    html_path = os.path.join(base, "thehawkoflight.github.io", "ada", "index.html")

    driver = setup_driver()
    try:
        # 1) Dark theme, embedded palette (?viz — purples) for main site
        out_main = os.path.join(base, "thehawkoflight.github.io", "images", "ada_animation.mp4")
        os.makedirs(os.path.dirname(out_main), exist_ok=True)
        print("=== Capturing animation (dark, embedded palette — main site) ===")
        success = patch_and_capture(driver, out_main, html_path, dark=True, embed=True)
        if not success:
            print("ERROR: Failed to capture main site animation")
            return

        # 2) Light theme, standalone palette (no ?viz — blues) for ada project page
        out_ada = os.path.join(base, "thehawkoflight.github.io", "ada", "images", "alignment_animation.mp4")
        os.makedirs(os.path.dirname(out_ada), exist_ok=True)
        print("=== Capturing animation (light, standalone palette — ada project page) ===")
        success = patch_and_capture(driver, out_ada, html_path, dark=False, embed=False)
        if not success:
            print("ERROR: Failed to capture ada animation")
            return

        print("\nDone!")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
