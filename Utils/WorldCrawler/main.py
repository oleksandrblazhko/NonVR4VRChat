"""
main.py
"""

from crawler import WorldCrawler


def main():

    crawler = WorldCrawler()

    crawler.login()

    crawler.crawl()


if __name__ == "__main__":

    main()
    