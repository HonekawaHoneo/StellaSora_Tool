from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parent
shots = root / 'previews'
shots.mkdir(exist_ok=True)
base = 'http://127.0.0.1:4317/'
results = []
errors = []

def frame_for(page, variant):
    return page.frame_locator('.option[data-variant="' + variant + '"] iframe')

def check_frames(page, total, difference=None, used=None, remaining=None):
    for variant in ['current','a','b']:
        frame = frame_for(page, variant)
        expect(frame.locator('#total')).to_have_text(total)
        if difference is not None: expect(frame.locator('#remaining')).to_have_text(difference)
        if used is not None: expect(frame.locator('#count-trait3')).to_have_value(str(used))
        if remaining is not None and variant != 'current':
            expect(frame.locator('[data-id="trait3"] .remaining-number')).to_have_text(str(remaining))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1140}, device_scale_factor=1)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base)
    check_frames(page,'170','330',7,3)
    page.screenshot(path=str(shots / 'mobile-comparison.png'), full_page=True)

    a = page.frame_locator('iframe[title="A案 研究の残数を大きく"]')
    a.locator('[data-id="trait3"] .increment').click()
    check_frames(page,'170','330',8,2)
    assert a.locator('#total').inner_text() == '170'
    a.locator('[data-id="reroll"] .increment').click()
    check_frames(page,'210','290',8,2)
    results.append({'check': 'shared clicks', 'research_remaining': 2, 'total': 210, 'difference': 290})

    for scenario, total, difference in [('limits','170','330'),('reached','500','0'),('over','580','-80'),('unset','170','目標未設定')]:
        page.locator('#scenario').select_option(scenario)
        check_frames(page,total,difference)
        if scenario in ['limits','over']:
            for variant in ['a','b']:
                expect(frame_for(page,variant).locator('.remaining-number')).to_have_text(['0','0'])
        results.append({'check': scenario, 'total': total, 'difference': difference})

    page.locator('#scenario').select_option('normal')
    check_frames(page,'170','330',7,3)
    page.get_by_role('button', name='PC 1280px').click()
    for iframe in page.locator('iframe').all(): expect(iframe).to_have_attribute('width','1280')
    page.screenshot(path=str(shots / 'desktop-comparison.png'), full_page=True)

    for variant in ['current', 'a', 'b']:
        for width, height, label in [(320,720,'small'),(390,720,'mobile'),(1280,800,'desktop')]:
            preview = browser.new_page(viewport={'width':width, 'height':height}, device_scale_factor=1)
            preview.on('pageerror', lambda error: errors.append(str(error)))
            preview.goto(base + 'preview.html?variant=' + variant + '&scenario=normal')
            expect(preview.locator('#total')).to_have_text('170')
            if variant != 'current': preview.wait_for_selector('.remaining-number')
            measurements = preview.evaluate("""() => ({
                pageWidth: document.documentElement.scrollWidth,
                viewport: innerWidth,
                height: document.documentElement.scrollHeight,
                researchTop: document.querySelector('.record-group').getBoundingClientRect().top,
                purchaseTop: document.querySelector('.notes-group').getBoundingClientRect().top,
                noteCards: [...document.querySelectorAll('.note-card')].map(e => ({width:e.clientWidth,scrollWidth:e.scrollWidth})),
                researchCards: [...document.querySelectorAll('.record')].map(e => ({width:e.clientWidth,scrollWidth:e.scrollWidth})),
                remaining: [...document.querySelectorAll('.remaining-number')].map(e => e.textContent),
                used: ['trait3','enhancement2'].map(id => document.querySelector('#count-' + id).value),
            })""")
            assert measurements['pageWidth'] <= width, (variant, width, measurements)
            assert all(item['scrollWidth'] <= item['width'] for item in measurements['researchCards']), (variant,width,measurements)
            assert measurements['used'] == ['7','3']
            if variant != 'current': assert measurements['remaining'] == ['3','2']
            results.append({'check':'layout','variant':variant,'size':label,**measurements})
            if label != 'small':
                preview.screenshot(path=str(shots / (variant + '-' + label + '.png')), full_page=True)
            preview.close()

    browser.close()

assert not errors, errors
(shots / 'checks.json').write_text(json.dumps({'results':results,'pageErrors':errors},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(results),'pageErrors':errors,'screenshots':str(shots)},ensure_ascii=False))
