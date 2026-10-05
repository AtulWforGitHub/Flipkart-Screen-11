import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from cookie_manager import load_cookies_from_mongo

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1440,900')
opts.add_argument('--lang=en-IN')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])
opts.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=opts)
try:
    cookies = load_cookies_from_mongo('primary')
    print('cookie_count', len(cookies))
    driver.get('https://www.flipkart.com')
    time.sleep(1)
    driver.delete_all_cookies()
    for i, cookie in enumerate(cookies):
        try:
            cookie.pop('storeId', None)
            if 'sameSite' in cookie:
                ss = cookie.pop('sameSite')
                if ss:
                    cookie['sameSite'] = ss
            driver.add_cookie(cookie)
        except Exception as e:
            print('skip', i, e)
    driver.refresh()
    time.sleep(3)
    txt = driver.find_element('tag name', 'body').text
    lines = txt.split('\n')[:25]
    print('BODY_HEAD')
    for l in lines:
        print(repr(l))
    print('LOGIN text present?', 'Login' in txt)
    print('contains Rahul?', 'Rahul' in txt)
    print('contains Hi,?', 'Hi,' in txt)
    print('contains Hello,?', 'Hello,' in txt)
    print('cookie_count_after', len(driver.get_cookies()))
    print('GREETINGS')
    greetings = driver.find_elements('xpath', "//*[contains(text(), 'Hi,') or contains(text(), 'Hello,')]")
    for el in greetings[:10]:
        print(repr(el.text))
    print('MATCHES')
    matches = driver.find_elements('xpath', "//*[contains(text(), 'Rahul') or contains(text(), 'Login')]")
    for el in matches[:20]:
        print(repr(el.text))
finally:
    driver.quit()
