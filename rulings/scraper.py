import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

class Content:
    BASE_URL = "https://putusan3.mahkamahagung.go.id/direktori"

    def __init__(self, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0"):
        self.headers = {"User-Agent": user_agent}

    def timestamp_string(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_status(self, message, url):
        """Returns a response status code

        Arguments:
        - message: the activity added with an emoji
        - url: link to the website
        """
        timestamp = self.timestamp_string()
        print(f"{timestamp} {message}: {url}")

    def get_response(self, url, proxies=None):
        """Returns 200 if the response is accepted
        Use proxy module to make a proxied web request

        Arguments:
        - url: self-explanatory
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        try:
            self.get_status("[GET \U0001F4BE]", url)
            response = requests.get(url, headers=self.headers, proxies=proxies, timeout=None)
            if response.status_code != 200:
                self.get_status("FAIL \U0001F494", url)
                pass
            return response
        except Exception:
            self.get_status("FAIL \U0001F494", url)
    
    def parse_content(self, response):
        """Response is derived from the returned object in get_response method
        """
        bs = BeautifulSoup(response.content, features="html.parser")

        return bs

    def save_to_json(self, data, output):
        """Save output into a JSON format
        """
        filename = f"{output}.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        self.get_status("[SAVE \U00002705]", filename)
        

class Aggregate(Content):

    def direktori(self, proxies=None):
        """Returns total rulings by "Direktori" (e.g. Perdata Agama, Pidana Umum, etc)

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        response = self.get_response(self.BASE_URL, proxies)
        bs = self.parse_content(response)
        bs = bs.select("#collapseZero > div:nth-child(1) > div:nth-child(1)")[0]
        bs = bs.find_all("div")
        data = []
        for b in bs[1:]:
            overall = " ".join(b.text.split()[:-1]).upper()
            total = int(b.text.split()[-1])
            data.append({"direktori": overall, "total": total})

        self.save_to_json(data, "data/direktori")

        return data

    def peradilan(self, proxies=None):
        """Returns total rulings by "Peradilan" (e.g. Mahkamah Agung, Peradilan Umum, etc)

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        response = self.get_response(self.BASE_URL, proxies)
        bs = self.parse_content(response)
        bs = bs.select("#collapseOne > div:nth-child(1) > div:nth-child(1)")[0]
        bs = bs.find_all("div")
        data = []
        for b in bs[1:]:
            overall = " ".join(b.text.split()[:-1]).upper()
            total = int(b.text.split()[-1])
            data.append({"peradilan": overall, "total": total})

        self.save_to_json(data, "data/peradilan")

        return data

    def periode(self, proxies=None):
        """Returns total rulings grouped by:
            - Court name, e.g. "PN Jakarta Barat", "PN Kudus", etc. Empty court name means all courts
            - Type of ruling: either "putus", "register", "upload"
            - Year: self-explanatory

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        select_value = lambda text: [x for x in text if x != ""]
        dictionary = lambda pengadilan, based, data: {
            "pengadilan": pengadilan,
            "based": based,
            "year": int(data[0]),
            "total": int(data[1])
        }

        _periode = []
        for based in ["putus", "register", "upload"]:
            response = self.get_response(f"{self.BASE_URL}/periode/tahunjenis/{based}.html")
            bs = self.parse_content(response)
            pengadilan = bs.select("#id_pengadilan")[0]
            pengadilan = pengadilan.find_all("option")
            pengadilan = [x["value"] for x in pengadilan]
            for p in pengadilan:
                if p == "":
                    url = f"{self.BASE_URL}/periode/tahunjenis/{based}.html"
                else:
                    url = f"{self.BASE_URL}/periode/tahunjenis/{based}/pengadilan/{p}.html"
                response = self.get_response(url)
                data = bs.select(".table")[0]
                tr = data.find("tbody").find_all("tr")
                data = [x.text.split("\n") for x in tr]
                data = [dictionary(p, based, select_value(x)) for x in data]
                _periode.append(data)
                self.save_to_json(_periode, "data/periode")

        return _periode
    
    def klasifikasi(self, proxies=None):
        """Returns total rulings by klasifikasi for each direktori, e.g. Perceraian, Pengesahan Nikah from Perdata Agama

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        dictionary = lambda direktori, data: {
            "direktori": direktori,
            "klasifikasi": " ".join(data[:-1]),
            "total": data[-1]
        }
        response = self.get_response(self.BASE_URL, proxies)
        bs = self.parse_content(response)
        bs = bs.select("#collapseZero > div:nth-child(1) > div:nth-child(1)")[0]
        a = bs.find_all("a")
        href = [x["href"] for x in a][1:]
        _klasifikasi = []
        for h in href:
            response = self.get_response(h, proxies)
            bs = self.parse_content(response)
            k = bs.select("#collapseThree > div:nth-child(1) > div:nth-child(1)")[0]
            k = [x for x in k.find_all("div", {"class": "form-check"})]
            k = [[x.find("a")["href"], re.sub("[\n\r]", "", x.text).split(" ")] for x in k]
            for _k in k:
                direktori = _k[0].replace("https://putusan3.mahkamahagung.go.id/direktori/index/kategori/", "")
                direktori = direktori.replace(".html", "")
                data = [x for x in _k[1] if x != ""]
                _klasifikasi.append(dictionary(direktori, data))
                self.save_to_json(_klasifikasi, "data/klasifikasi")

        return _klasifikasi

    def periode_klasifikasi(self, proxies=None):
        """Returns total rulings by klasifikasi grouped by:
            - Court name, e.g. "PN Jakarta Barat", "PN Kudus", etc. Empty court name means all courts
            - Type of ruling: either "putus", "register", "upload"
            - Year: self-explanatory

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        select_value = lambda text: [x for x in text if x != ""]
        dictionary = lambda _direktori, pengadilan, based, data: {
            "direktori": _direktori,
            "pengadilan": pengadilan,
            "based": based,
            "year": int(data[0]),
            "total": int(data[1])
        }

        klasifikasi = self.klasifikasi()
        direktori = [x["direktori"] for x in klasifikasi]
        _periode_klasifikasi = []
        for based in ["putus", "register", "upload"]:
            for d in direktori:
                url = f"https://putusan3.mahkamahagung.go.id/direktori/periode/tahunjenis/{based}/kategori/{d}.html"
                response = self.get_response(url, proxies)
                bs = self.parse_content(response)
                pengadilan = bs.select("#id_pengadilan")[0]
                pengadilan = pengadilan.find_all("option")
                pengadilan = [x["value"] for x in pengadilan]
                for p in pengadilan:
                    if p != "":
                        response = requests.get(f"{url.replace('.html', '')}/pengadilan/{p}.html", proxies)
                    else:
                        response = requests.get(url, proxies)
                    bs = self.parse_content(response)
                    data = bs.select(".table")[0]
                    tr = data.find("tbody").find_all("tr")
                    _direktori = url.replace("https://putusan3.mahkamahagung.go.id/direktori/periode/tahunjenis/putus/kategori/", "")
                    _direktori = _direktori.replace(".html", "")
                    data = [x.text.split("\n") for x in tr]
                    data = [dictionary(_direktori, p, based, select_value(x)) for x in data]
                    _periode_klasifikasi.append(data)
                    self.save_to_json(_periode_klasifikasi, "data/periode-klasifikasi")

        return _periode_klasifikasi


class Case(Content):

    def total_page(self, proxies=None):
        """Returns total page (integer)

        Argument:
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        response = self.get_response("https://putusan3.mahkamahagung.go.id/direktori.html", proxies)
        bs = self.parse_content(response)
        css = ".pagination"
        page = int(bs.select(css)[0].find_all("a")[-1]["data-ci-pagination-page"])

        return page

    def case(self, proxies=None, total_page=5):
        """Returns each ruling URL for every page.

        Arguments:
        - total_page: number of pages that will be scraped.
        Default value is five pages, which results to almost 300 rulings
        """
        i = 1
        last_page = self.total_page(proxies)
        if total_page != last_page:
            last_page = total_page
        data = []
        while i <= last_page:
            url = f"https://putusan3.mahkamahagung.go.id/direktori/index/page/{i}.html"
            response = self.get_response(url, proxies)
            bs = self.parse_content(response)
            bs = bs.select(".tab-container")[0]
            a = bs.find_all("a")
            href = [x["href"] for x in a]
            for h in href:
                if "/putusan/" in h:
                    data.append(h)
            i += 1
            
        return data

    def putusan(self, bs):
        """Returns title of a particular ruling
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(1) > h2:nth-child(1)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None

        return output

    def nomor(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(2) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None

        return output

    def tingkat_proses(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(3) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def klasifikasi(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(4) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def kata_kunci(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(5) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None

        return output

    def tahun(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(6) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def tanggal_register(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(7) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def lembaga_peradilan(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(8) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None

        return output

    def jenis_lembaga_peradilan(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(9) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def hakim_ketua(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(10) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def hakim_anggota(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(11) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output
    
    def panitera(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(12) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def amar(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(13) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output
    
    def amar_lainnya(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(14) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def catatan_amar(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(15) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def tanggal_musyawarah(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(16) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def tanggal_dibacakan(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(17) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def kaidah(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(18) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output
    
    def abstrak(self, bs):
        """Returns
        """
        try:
            css = ".table > tbody:nth-child(1) > tr:nth-child(19) > td:nth-child(2)"
            output = bs.select(css)[0].text.upper()
            output = re.sub("[\r\n\t]", "", output)
            output = re.sub(" +", " ", output)
        except Exception as e:
            print(e)
            output = None
        
        return output

    def create_json(self, data, proxies=None):
        """Returns final output of each ruling in JSON format

        Arguments:
        - data: the output from `case` method
        - proxies: a string of socks5. Reference: https://2.python-requests.org/en/master/user/advanced/#socks
        """
        _json = []
        for url in data:
            response = self.get_response(url, proxies)
            bs = self.parse_content(response)
            d = {
                "putusan": self.putusan(bs),
                "nomor": self.nomor(bs),
                "tingkat_proses": self.tingkat_proses(bs),
                "klasifikasi": self.klasifikasi(bs),
                "kata_kunci": self.kata_kunci(bs),
                "tahun": self.tahun(bs),
                "tanggal_register": self.tanggal_register(bs),
                "lembaga_peradilan": self.lembaga_peradilan(bs),
                "jenis_lembaga_peradilan": self.jenis_lembaga_peradilan(bs),
                "hakim_ketua": self.hakim_ketua(bs),
                "hakim_anggota": self.hakim_anggota(bs),
                "panitera": self.panitera(bs),
                "amar": self.amar(bs),
                "amar_lainnya": self.amar_lainnya(bs),
                "catatan_amar": self.catatan_amar(bs),
                "tanggal_musyawarah": self.tanggal_musyawarah(bs),
                "tanggal_dibacakan": self.tanggal_dibacakan(bs),
                "kaidah": self.kaidah(bs),
                "abstrak": self.abstrak(bs)
            }
            _json.append(d)
            self.save_to_json(_json, "data/putusan-per-kasus")

        return _json


if __name__ == "__main__":
    aggregate = Aggregate()
    aggregate.direktori()
    aggregate.peradilan()
    aggregate.periode()
    aggregate.klasifikasi()
    aggregate.periode_klasifikasi()
