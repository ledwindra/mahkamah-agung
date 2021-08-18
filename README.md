# About 🧑🏻‍⚖️

This repository aims to scrape Supreme Court of Indonesia's rulings website. It contains statistics and ruling details over several types, which are broken down into courts and time periods (year and month). Following are the ruling types:

|Type|Description|
|-|-|
|Perdata Agama||
|Pidana Umum||
|Perdata||
|Pidana Khusus||
|TUN||
|Perdata Khusus||
|Pidana Militer||
|Pajak||

# Permission

It looks like they don't limit whan information we can get from this website:

```
# https://mahkamahagung.go.id/robots.txt

User-agent: *
```

# Usage

Besides using the available datasets, you can also execute the code by yourself. You should have Python 3.6 or above installed. Here's the steps:

1. Clone the repository or download repository as ZIP

```bash
# clone repository through command line
# this includes .git directory
git clone https://github.com/ledwindra/mahkamah-agung.git
cd mahkamah-agung

# download repository through command line
# this doesn't include .git directory as opposed to cloning method
wget https://github.com/ledwindra/mahkamah-agung/archive/refs/heads/main.zip
unzip main.zip
cd mahkamah-agung-main
```

2. Use virtual environment and install requirements

```bash
python -m venv .venv
source .venv/bin/activate # macOS or Linux
pip install --upgrade pip
pip install -r requirements.txt
```

3. Go to Python interpreter and give it a try

    a. You can make a request one-by-one
    ```python
    >>> from src.scraper import Aggregate
    >>> aggregate = Aggregate()
    >>> direktori = aggregate.overall("#collapseZero > div:nth-child(1) > div:nth-child(1)", "direktori")
    2021-08-18 07:32:33 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori
    >>> direktori
    [{'direktori': 'PERDATA AGAMA', 'total': 4415195}, {'direktori': 'PIDANA UMUM', 'total': 635994}, {'direktori': 'PERDATA', 'total': 626112}, {'direktori': 'PIDANA KHUSUS', 'total': 393608}, {'direktori': 'TUN', 'total': 53101}, {'direktori': 'PERDATA KHUSUS', 'total': 31685}, {'direktori': 'PIDANA MILITER', 'total': 21802}, {'direktori': 'PAJAK', 'total': 8726}, {'direktori': 'SENGKETA KEWENANGAN MENGADILI', 'total': 6}]
    ```

    b. You can also make requests in bulk
    ```python
    >>> from src.scraper import Aggregate
    >>> aggregate = Aggregate()
    >>> aggregate.bulk_by_direktori()
    2021-08-18 07:45:58 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori/index/kategori/perdata-agama-1.html
    2021-08-18 07:46:00 [SAVE ✅]: data/perdata-agama/klasifikasi.json
    2021-08-18 07:46:00 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori/index/kategori/perdata-agama-1.html
    2021-08-18 07:46:04 [SAVE ✅]: data/perdata-agama/pengadilan.json
    2021-08-18 07:46:04 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori/index/kategori/pidana-umum-1.html
    ```

    c. Similar to a and b, but to get annual trends
    ```python
    >>> from src.scraper import Aggregate
    >>> aggregate = Aggregate()
    >>> aggregate.by_year("perdata-agama-1", "putus")
    2021-08-18 07:51:06 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori/periode/tahunjenis/putus/kategori/perdata-agama-1.html
    [{'year': '3020', 'total': 1}, {'year': '3015', 'total': 1}, {'year': '3014', 'total': 2}, {'year': '3013', 'total': 4}, {'year': '2915', 'total': 1}, {'year': '2914', 'total': 3}, {'year': '2204', 'total': 1}, {'year': '2107', 'total': 7}, {'year': '2106', 'total': 3}, {'year': '2105', 'total': 18}, {'year': '2104', 'total': 5}, {'year': '2077', 'total': 1}, {'year': '2051', 'total': 2}, {'year': '2047', 'total': 1}, {'year': '2023', 'total': 1}, {'year': '2022', 'total': 2}, {'year': '2021', 'total': 347561}, {'year': '2020', 'total': 647866}, {'year': '2019', 'total': 644985}, {'year': '2018', 'total': 579427}, {'year': '2017', 'total': 520160}, {'year': '2016', 'total': 496834}, {'year': '2015', 'total': 274743}, {'year': '2014', 'total': 238949}, {'year': '2013', 'total': 197291}, {'year': '2012', 'total': 157248}, {'year': '2011', 'total': 121437}, {'year': '2010', 'total': 66195}, {'year': '2009', 'total': 38873}, {'year': '2008', 'total': 25262}, {'year': '2007', 'total': 16504}, {'year': '2006', 'total': 8274}, {'year': '2005', 'total': 5102}, {'year': '2004', 'total': 2064}, {'year': '2003', 'total': 341}, {'year': '2002', 'total': 230}, {'year': '2001', 'total': 104}, {'year': '2000', 'total': 118}, {'year': '1998', 'total': 2}, {'year': '1997', 'total': 1}, {'year': '1995', 'total': 1}, {'year': '1987', 'total': 97}, {'year': '1986', 'total': 459}, {'year': '1985', 'total': 300}, {'year': '1984', 'total': 661}, {'year': '1983', 'total': 805}, {'year': '1982', 'total': 652}, {'year': '1981', 'total': 1099}, {'year': '1980', 'total': 347}, {'year': '1979', 'total': 918}, {'year': '1978', 'total': 440}, {'year': '1977', 'total': 566}, {'year': '1976', 'total': 103}, {'year': '1972', 'total': 2}, {'year': '1970', 'total': 301}, {'year': '1969', 'total': 1}, {'year': '1968', 'total': 6}, {'year': '1961', 'total': 8}, {'year': '1959', 'total': 2}, {'year': '1953', 'total': 7}, {'year': '1950', 'total': 10}, {'year': '1911', 'total': 1}, {'year': '1902', 'total': 1}, {'year': '1900', 'total': 5}, {'year': '1018', 'total': 1}, {'year': '1016', 'total': 1}, {'year': '1015', 'total': 2}, {'year': '1014', 'total': 5}, {'year': '1013', 'total': 1}, {'year': '1012', 'total': 1}, {'year': '218', 'total': 4}, {'year': '217', 'total': 3}, {'year': '216', 'total': 4}, {'year': '215', 'total': 33}, {'year': '214', 'total': 3}, {'year': '213', 'total': 8}, {'year': '212', 'total': 4}, {'year': '211', 'total': 4}, {'year': '210', 'total': 4}, {'year': '209', 'total': 4}, {'year': '208', 'total': 6}, {'year': '207', 'total': 16}, {'year': '206', 'total': 6}, {'year': '205', 'total': 10}, {'year': '204', 'total': 21}, {'year': '203', 'total': 8}, {'year': '202', 'total': 3}, {'year': '201', 'total': 69}, {'year': '111', 'total': 1}, {'year': '105', 'total': 2}, {'year': '104', 'total': 1}, {'year': '15', 'total': 1}]
    ```

4. [Optional] For analytics purpose, you can create dataframes and visualizations from the datasets
```python
>>> import pandas as pd
>>> import matplotlib.pyplot as plt
>>> from src.scraper import Aggregate
>>> aggregate = Aggregate()
>>> df = pd.DataFrame(aggregate.by_year("perdata-agama-1", "putus"))
2021-08-18 07:55:22 [GET 💾]: https://putusan3.mahkamahagung.go.id/direktori/periode/tahunjenis/putus/kategori/perdata-agama-1.html
>>> df = df[df.year.between(2010, 2020)]
>>> df
    year   total
17  2020  647949
18  2019  644994
19  2018  579438
20  2017  520160
21  2016  496834
22  2015  274743
23  2014  238951
24  2013  197292
25  2012  157248
26  2011  121437
27  2010   66195
>>> df.plot(x="year", y="total", grid=True, legend=False, xticks=range(2010, 2021))
<AxesSubplot:xlabel='year'>
>>> plt.savefig("img/perdata-agama-putus.png")
```

## Line graph example

<p align="left"><img src="./img/perdata-agama-putus.png"></p>

# Miscellaneous
- Submit issues [here](https://github.com/ledwindra/mahkamah-agung/issues) if you have any questions of find any bug.
- This repository is mostly developed using [GitHub Codespaces](https://github.com/features/codespaces) which is 🌟 insanely 🌟 awesome 🌟.
