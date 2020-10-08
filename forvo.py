import glob
import os
import random
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
from scipy.stats import truncnorm
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Input CSV file name
CSV_PATH = 'data/Ancient Greek Words - Sheet1.csv'

# Wait time in seconds for audio download class to appear
AUDIO_ELEMENT_WAIT = 10

# Forvo credentials from environment variables
FORVO_EMAIL = os.environ['FORVO_EMAIL']
FORVO_PASSWORD = os.environ['FORVO_PASSWORD']
FORVO_DOWNLOAD_DIRECTORY = os.environ['FORVO_DOWNLOAD_DIRECTORY']


def get_truncated_normal(mean=0, sd=1, low=0, upp=10):
    """Get a set of normally distributed values"""
    return truncnorm(
        (low - mean) / sd, (upp - mean) / sd, loc=mean, scale=sd)


# Setup a normal distribution number generator to sleep from
d = get_truncated_normal(mean=1.5, sd=1, low=0.5, upp=3)
# Now we can: time.sleep( d.rvs() ) to look less like a machine

# Open the card database
df = pd.read_csv(CSV_PATH)

# Initialize the Chrome WebDriver to download into ./data/
chrome_options = webdriver.ChromeOptions()
prefs = {'download.default_directory': FORVO_DOWNLOAD_DIRECTORY}
chrome_options.add_experimental_option('prefs', prefs)
driver = webdriver.Chrome(
    executable_path='driver/chromedriver_mac_76',
    chrome_options=chrome_options,
)

# Login to Forvo
driver.get('https://forvo.com/login/')
driver.find_element_by_name('login').send_keys(FORVO_EMAIL)
driver.find_element_by_name('password').send_keys(FORVO_PASSWORD)
remember = driver.find_element_by_name('remember')
remember.click()
remember.submit()

# Loop over rows, fetching the audio files
audio_paths = []
for index, row in df.iterrows():
    word = row['Word'].strip()
    forvo_url = row['Forvo URL']

    # Get the page...
    print(f'Fetching Forvo URL for {word} from {forvo_url} ...')
    driver.get(forvo_url)

    # Get the Forvo version of the word from the page - it can differ from what we searched for
    page = BeautifulSoup(driver.page_source)
    header_text = page.find('h2').text

    word_search = re.search('Translation of (.*)\n', header_text, re.IGNORECASE)
    forvo_word = None
    if word_search:
        forvo_word = word_search.group(1).strip()
    else:
        raise Exception(f"Couldn't find word {word} on page!")

    # Check if the audio file already exists and skip if it does
    audio_download_glob = f'{FORVO_DOWNLOAD_DIRECTORY}/pronunciation_*_{forvo_word}.mp3'
    glob_files = glob.glob(audio_download_glob)
    if len(glob_files) > 0:
        found_file = glob_files[0]
        print(f'Skipping {word}, it already exists at {found_file} ...')

        # Add the path to our list
        try:
            downloaded_glob_files = glob.glob(audio_download_glob)
            downloaded_file_path = downloaded_glob_files[0]
            audio_paths.append(
                downloaded_file_path,
            )
        except IndexError:
            print(f'\nDownload error for {word} :(\n')
            audio_paths.append('')

        # Skip downloading this file
        continue

    # Slow it down there, hoss...
    time.sleep(d.rvs())

    # Wait for the first audio download link to appear and click it, slowly
    try:
        WebDriverWait(driver, AUDIO_ELEMENT_WAIT).until(
            EC.element_to_be_clickable(
                (By.CLASS_NAME, 'download'),
            ),
        )
    except TimeoutException as e:
        print(f'\nWait Timed out! Skipping {word} :(\n')
        print(e)
    time.sleep(d.rvs())
    driver.find_element_by_class_name('download').click()
    time.sleep(d.rvs())

    # Add the new file path to our list
    try:
        downloaded_glob_files = glob.glob(audio_download_glob)
        downloaded_file_path = downloaded_glob_files[0]
        audio_paths.append(
            downloaded_file_path,
        )
    except IndexError:
        print(f'\nDownload error for {word} :(\n')
        audio_paths.append('')

df['Audio Path'] = pd.Series(audio_paths)

without_ending = CSV_PATH.replace('.csv', '')
output_path = f'{without_ending} With Audio.csv'
df.to_csv(output_path)

print('Tada!')
