#! python3

import os
import praw
from prawcore import NotFound
import re
import requests
import schedule
import shelve
import time
from threading import Thread

imgur_url_pattern = re.compile(r'(http://i.imgur.com/(.*))(\?.*)?')


class ScraperConfig:

    def __init__(self, reddit_client_id, reddit_client_secret, reddit_user_agent, shelve_conf_path,
                 shelve_filename_keyword):
        self.client_id = reddit_client_id
        self.client_secret = reddit_client_secret
        self.user_agent = reddit_user_agent
        self.shelve_conf_path = shelve_conf_path
        self.shelve_keyword = shelve_filename_keyword


class Scraper:

    def __init__(self, scraper_config: ScraperConfig, _folder='./Birbs/', _subreddit='birbs'):

        self.folder = _folder
        self.subreddit = _subreddit
        self.scraper_config = scraper_config
        self.reddit = praw.Reddit(client_id=self.scraper_config.client_id,
                                  client_secret=self.scraper_config.client_secret,
                                  user_agent=self.scraper_config.user_agent)

    def crawl(self):

        if not self.sub_exists(self.subreddit):
            print("Subreddit not found! " + self.subreddit)
            return

        print('Running downloader on folder: {}'.format(self.folder))

        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

        images = self.reddit.subreddit(self.subreddit)

        counter = 0

        try:
            counter += self.download(images.hot(limit=30), self.folder)
            counter += self.download(images.top(limit=30), self.folder)
            print('')
            print('Download complete, loaded {} new images'.format(counter))
        except Exception as e:
            print('Download for {} threw errors: {}'.format(self.subreddit, e))

    def start(self):

        print('Starting new scraper for subreddit {} for folder {}'.format(self.subreddit, self.folder))

        self.crawl()
        schedule.every().day.do(self.crawl)
        thread = Thread(target=self.update)
        thread.start()
        print('Started update Thread')

    def download(self, _url_list, _folder):
        counter = 0

        cache = shelve.open(self.scraper_config.shelve_conf_path)
        file_names = {}
        if self.scraper_config.shelve_keyword in cache:
            file_names = cache[self.scraper_config.shelve_keyword]

        for url in _url_list:
            ext = url.url[-3:]
            if url.url[-4:] == 'gifv' or ext == 'gif':
                continue

            elif ext == 'jpg' or ext == 'png':
                file_url = url.url
                counter = self.download_image(_folder, cache, counter, ext, file_names, file_url, url)
                print('.', end='', flush=True)

            elif 'i.imgur.com/' in url.url:
                print(';', end='', flush=True)
                mo = imgur_url_pattern.search(url.url)
                imgur_filename = mo.group(2)
                if '?' in imgur_filename:
                    imgur_filename = imgur_filename[:imgur_filename.find('?')]
                file_url = 'http://i.imgur.com/' + imgur_filename
                ext = imgur_filename[-4:]
                ext = ext[1:3] if ext[0] == '.' else ext
                counter = self.download_image(_folder, cache, counter, ext, file_names, file_url, url)

            else:
                print('-', end='', flush=True)
                continue

        cache.close()
        return counter

    def download_image(self, _folder, cache, counter, ext, file_names, file_url, url, index=-1):
        post_name = url.title
        file_name = url.id + ('_' + str(index) if index != -1 else '') + '.' + ext
        path = _folder + file_name
        if not os.path.isfile(path):
            img = requests.get(file_url).content
            with open(path, 'wb') as handler:
                handler.write(img)
                file_names[file_name] = post_name
                cache[self.scraper_config.shelve_keyword] = file_names
            counter += 1
        else:
            print('_', end='', flush=True)
        return counter

    def sub_exists(self, sub=None):
        if sub is None:
            sub = self.subreddit
        exists = True
        try:
            self.reddit.subreddits.search_by_name(sub, exact=True)
        except Exception as e:
            exists = False
        return exists

    @staticmethod
    def update():
        while True:
            schedule.run_pending()
            time.sleep(30)
