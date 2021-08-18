import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from warnings import simplefilter

class Constant:
    BASE_URL = "https://putusan3.mahkamahagung.go.id/direktori"
    DIREKTORI = {
        "perdata-agama-1": "perdata-agama",
        "pidana-umum-1": "pidana-umum",
        "perdata-1": "perdata",
        "pidana-khusus-1": "pidana-khusus",
        "tun-1": "tata-usaha-negara",
        "perdata-khusus": "perdata-khusus",
        "pidana-militer-1": "pidana-militer",
        "pajak-2": "pajak",
        "sengketa-kewenangan-mengadili-1": "sengketa-kewenangan-mengadili"
    }
    CSS_SELECTOR = {
        "direktori": "#collapseZero > div:nth-child(1) > div:nth-child(1)",
        "peradilan": "#collapseOne > div:nth-child(1) > div:nth-child(1)",
        "klasifikasi": "#collapseThree > div:nth-child(1) > div:nth-child(1)",
        "pengadilan": "#collapseOne > div:nth-child(1) > div:nth-child(1)"
    }


class Content(Constant):

    def __init__(self, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0"):
        self.headers = {"User-Agent": user_agent}

    def timestamp_string(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_status(self, message, url):
        timestamp = self.timestamp_string()
        print(f"{timestamp} {message}: {url}")

    def get_response(self, url, proxies=None):
        try:
            self.get_status("[GET \U0001F4BE]", url)
            simplefilter("ignore")
            r = requests.get(url, verify=False, headers=self.headers, proxies=proxies, timeout=None)
            if r.status_code != 200:
                self.get_status("FAIL \U0001F494", url)
                pass
            return r
        except Exception:
            self.get_status("FAIL \U0001F494", url)
    
    def parse_content(self, response):
        bs = BeautifulSoup(response.content, features="html.parser")

        return bs
        

class Aggregate(Content):

    def overall(self, css_selector, by="direktori"):
        """List of CSS selectors available:
        - Direktori: "#collapseZero > div:nth-child(1) > div:nth-child(1)"
        - Peradilan: "#collapseOne > div:nth-child(1) > div:nth-child(1)"
        """
        response = self.get_response(self.BASE_URL)
        bs = self.parse_content(response)
        bs = bs.select(css_selector)[0]
        bs = bs.find_all("div")
        data = []
        for b in bs[1:]:
            overall = " ".join(b.text.split()[:-1]).upper()
            total = int(b.text.split()[-1])
            data.append({by: overall, "total": total})

        return data

    def by_direktori(self, direktori, css_selector, by="klasifikasi"):
        """List of CSS selectors available:
        Klasifikasi: "#collapseThree > div:nth-child(1) > div:nth-child(1)"
        Pengadilan: "#collapseOne > div:nth-child(1) > div:nth-child(1)"
        """
        response = self.get_response(f"{self.BASE_URL}/index/kategori/{direktori}.html")
        bs = self.parse_content(response)
        bs = bs.select(css_selector)[0]
        bs = bs.find_all("div")
        data = []
        for b in bs:
            try:
                overall = " ".join(b.text.split()[:-1]).upper()
                total = int(b.text.split()[-1])
                data.append({by: overall, "total": total})
            except IndexError:
                pass

        return data
    
    def bulk_by_direktori(self, save_file=True):
        bulk = []
        for d in self.DIREKTORI.keys():
            for c in ["klasifikasi", "pengadilan"]:
                data = self.by_direktori(d, self.CSS_SELECTOR[c], c)
                bulk.append(data)
                if save_file:
                    self.save_to_json(data, f"data/{self.DIREKTORI[d]}/{c}")

        return bulk

    def by_year(self, direktori, based_on):
        select_value = lambda text: [x for x in text if x != '']
        dictionary = lambda text: {'year': int(text[0]), 'total': int(text[1])}

        response = self.get_response(f"{self.BASE_URL}/periode/tahunjenis/{based_on}/kategori/{direktori}.html")
        bs = self.parse_content(response)
        data = bs.find('table', {'class': 'table table-striped'})
        tr = data.find('tbody').find_all('tr')
        data = [x.text.split('\n') for x in tr]
        data = [dictionary(select_value(x)) for x in data]

        return data
    
    def bulk_by_year(self, save_file=True):
        bulk = []
        for d in self.DIREKTORI.keys():
            for b in self.BASED_ON:
                data = self.by_year(d, b)

                if save_file:
                    self.save_to_json(data, f"data/direktori-yearly/{self.DIREKTORI[d]}-{b}")

    def by_direktori_yearly(self, direktori, year):
        url = f"{self.BASE_URL}/index/kategori/{direktori}/tahunjenis/putus/tahun/{year}.html"
        response = self.get_response(url)
        bs = self.parse_content(response)

    def save_to_json(self, data, output):
        filename = f"{output}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        self.get_status("[SAVE \U00002705]", filename)


class Case(Content):

    def find_portfolio(self, bs):
         return bs.find_all('ul', {'class': 'portfolio-meta nobottommargin'})

    def find_a(self, portofolio):
        return [x.find_all('a') for x in portofolio]

    def get_href(self, a):
        for i in a:
            for j in i:
                if 'pdf' in j['href']:
                    return j['href']

    def download_pdf(self, href, output='tes'):
        return os.system(f'wget {href} -O {output}.pdf --no-check-certificate --user-agent="{self.headers["User-Agent"]}"')

    def pdf_to_txt(self, pdf_file='tes'):
        return os.system(f'pdftotext {pdf_file}.pdf')
