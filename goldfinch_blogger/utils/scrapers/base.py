from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options as ChromeOptions


class Scraper():
  new_post_url: str = None
  new_post_title: str = None
  new_post_date: str = None
  new_post_author: str = None
  new_post_content: str = None


  @classmethod
  def get_selenium(self):
    try:
      chrome_options = ChromeOptions()
      chrome_options.add_argument("--headless")
      chrome_options.add_argument("--no-sandbox")
      driver = Chrome(options=chrome_options)
    except:
      options = ChromeOptions()
      options.binary_location = '/opt/chrome/chrome'
      options.add_argument('--headless')
      options.add_argument('--no-sandbox')
      options.add_argument("--disable-gpu")
      options.add_argument("--window-size=1280x1696")
      options.add_argument("--single-process")
      options.add_argument("--disable-dev-shm-usage")
      options.add_argument("--disable-dev-tools")
      options.add_argument("--no-zygote")
      driver = Chrome("/opt/chromedriver", options=options)

    return driver


  def get_latest_post_meta(self):
    raise NotImplementedError


  def scrape_post(self):
    raise NotImplementedError