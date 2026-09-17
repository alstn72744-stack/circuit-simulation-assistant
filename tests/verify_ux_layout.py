"""Optional browser layout check (pip install playwright; uses installed Edge).

Synthetic graph fixture only: no LTspice or API. Saves desktop/mobile screenshots
and actual image geometry; starts/stops only its own temporary Streamlit server.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

PROJECT=Path(__file__).resolve().parents[1]


def main():
    from playwright.sync_api import sync_playwright
    folder=PROJECT/'simulation_output'/('ux_layout_verification_'+uuid4().hex)
    folder.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(PROJECT/'tests/ux_preview.py'),
        '--server.headless=true','--server.address=127.0.0.1',f'--server.port={port}',
        '--browser.gatherUsageStats=false'],cwd=PROJECT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        url=f'http://127.0.0.1:{port}'
        for _ in range(80):
            try:
                with urllib.request.urlopen(url+'/_stcore/health',timeout=1) as response:
                    assert response.status==200
                break
            except OSError:
                time.sleep(.25)
        else:
            raise RuntimeError('Streamlit startup timed out')
        measurements={}
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            try:
                page=browser.new_page()
                for label,width in [('desktop',1440),('mobile',390)]:
                    page.set_viewport_size({'width':width,'height':1000})
                    page.goto(url)
                    page.get_by_text('Layout fixture ready',exact=True).wait_for(timeout=60000)
                    page.wait_for_function('Array.from(document.querySelectorAll("[data-testid=stImage] img")).length === 5 && Array.from(document.querySelectorAll("[data-testid=stImage] img")).every(i => i.complete && i.naturalWidth > 0)')
                    sizes=page.locator('[data-testid=stImage] img').evaluate_all('''images => images.map(image => {
                        const box=image.getBoundingClientRect();
                        const row=image.closest('[data-testid="stHorizontalBlock"]').getBoundingClientRect();
                        return {width:box.width,height:box.height,x:box.x,right:box.right,
                            ratio:box.width/row.width,centerError:Math.abs(box.x+box.width/2-row.x-row.width/2),
                            aspect:box.width/box.height,naturalAspect:image.naturalWidth/image.naturalHeight};
                    })''')
                    page.screenshot(path=str(folder/f'{label}.png'),full_page=True)
                    measurements[label]=sizes
                    for size in sizes:
                        assert size['x']>=0 and size['right']<=width+1,size
                        assert size['centerError']<2,size
                        assert abs(size['aspect']-size['naturalAspect'])<.01,size
                        if label=='desktop':
                            assert .80<=size['ratio']<=.85,size
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),label
            finally:
                browser.close()
        (folder/'geometry.json').write_text(json.dumps(measurements,indent=2),encoding='utf-8')
        print('PASS: five graphs, desktop 83%, centered, aspect preserved, mobile no overflow:',folder)
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__=='__main__':
    main()
