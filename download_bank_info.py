import os
import time
import shutil
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

CWD = os.getcwd()
CURRENT_FILES = set(os.listdir(CWD))

def enable_download_in_headless_chrome(browser, download_dir):
  #add missing support for chrome "send_command"  to selenium webdriver
  browser.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')

  params = {'cmd': 'Page.setDownloadBehavior', 'params': {'behavior': 'allow', 'downloadPath': download_dir}}
  browser.execute("send_command", params)

def start_chrome(download_dir, headless=True):
  chrome_options = Options()
  chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
  })

  if headless:
    print('Starting chromedriver in headless mode')
    chrome_options.add_argument("--headless")

  driver = webdriver.Chrome(executable_path=os.path.abspath("chromedriver"),   chrome_options=chrome_options)

  if headless:
    print('Enabling downloads in headless chrome')
    enable_download_in_headless_chrome(driver, download_dir)

  return driver

def load_alliant(driver, cookie):
  print('Navigating to Alliant CU')
  driver.get("https://www.alliantcreditunion.com")

  # We need the cookie for the "saved computer" on Alliant's domain
  driver.add_cookie(cookie)

def log_in(username, password, driver):
  print('Logging in to Alliant CU')
  login_btn = driver.find_element_by_partial_link_text("Login")
  login_btn.click()

  username_input = driver.find_element_by_id("ctl00_pagePlaceholder_txt_username")
  username_input.send_keys(username)

  password_input = driver.find_element_by_id("ctl00_pagePlaceholder_txt_password")
  password_input.send_keys(password)

  login_btn = driver.find_element_by_id("ctl00_pagePlaceholder_btn_logon")
  login_btn.click()

def download(account, driver):
  print('Downloading past 30 days history for', account)
  account_link = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.LINK_TEXT, account)))
  account_link.click()

  driver.find_element_by_link_text("Download History").click()

  csv_button = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//input[@value='Csv']")))
  csv_button.click()
  driver.find_element_by_xpath("//input[@src='../../design/btn_Download.png']").click()

  # Wait for popup to disappear
  WebDriverWait(driver, 3).until(EC.invisibility_of_element_located((By.ID, 'upShadowDiv')))
  driver.find_element_by_link_text("Cancel").click()

  # Wait for Download History dialog to go away
  WebDriverWait(driver, 3).until(EC.invisibility_of_element_located((By.XPATH, "//input[@value='Csv']")))
  driver.find_element_by_partial_link_text("Accounts").click()

def new_files(previous_files, directory):
  return set(os.listdir(directory)).difference(previous_files)

def wait_for_file(previous_files, directory):
  n = 0
  while len(new_files(previous_files, directory)) < 1 and n < 5:
    time.sleep(1)
    n += 1

  return new_files(previous_files, directory).pop()

def move_file(from_file, to_file, directory):
  shutil.move(directory + '/' + from_file, directory + '/' + to_file)

def parse_cookie(filename):
  with open(filename, 'r') as f:
    return eval(f.read())

if __name__ == '__main__':
  import argparse
  import getpass

  parser = argparse.ArgumentParser(description='Download bank account history')
  parser.add_argument('username', type=str,
                      help='username to use to log in to Alliant')
  parser.add_argument('cookie_file', type=str, default='cookie',
                      help='location of the file containing the necessary cookie')
  parser.add_argument('--noheadless', help='Don\'t run in headless mode',
                      const=False, dest='headless', action='store_const',
                      default=True)

  args = parser.parse_args()

  password = getpass.getpass('Enter password for Alliant CU:')

  driver = start_chrome(CWD, headless=args.headless)
  cookie = parse_cookie(args.cookie_file)
  load_alliant(driver, cookie)

  try:
    log_in(args.username, password, driver)
    download('Checking', driver)
    print('Waiting for files to download...')
    new_file = wait_for_file(CURRENT_FILES, CWD)
    move_file(new_file, 'checking.csv', CWD)
    CURRENT_FILES.add('checking.csv')

    download('Savings Account', driver)
    print('Waiting for files to download...')
    new_file = wait_for_file(CURRENT_FILES, CWD)
    move_file(new_file, 'savings.csv', CWD)

    print('Success!')
    driver.close()
  except Exception as e:
    driver.save_screenshot(CWD + '/last_screen.png')
    driver.close()
    print("Something went wrong")
    traceback.print_exc()
