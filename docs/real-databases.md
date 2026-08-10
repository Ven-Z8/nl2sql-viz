# Real-World Complex Databases — Research Links

> Real, multi-table databases per domain for the NL2SQL benchmark. Loaded through
> the dataset system (schema.json + FKs). ✅ = downloaded and loaded into Postgres.

## Retail / E-commerce

| Database                          | Tables                                                                          |         Size | Link                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------- | -----------: | --------------------------------------------------------------------- |
| **Olist Brazilian E-commerce** ✅ | 9 (customers, orders, items, payments, sellers, products, reviews, geolocation) | ~100K orders | [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) |
| **Northwind**                     | 13 (customers, orders, order_details, products, suppliers, employees)           |   ~2K orders | [GitHub](https://github.com/pthom/northwind_psql)                     |
| **Chinook**                       | 11 (customers, invoices, invoice_items, tracks, albums, artists)                | ~4K invoices | [GitHub](https://github.com/lerocha/chinook-database)                 |
| **TPC-H**                         | 8 (lineitem, orders, customer, part, supplier, nation, region)                  |  1M-10M rows | [TPC](https://www.tpc.org/tpch/)                                      |

## Healthcare

| Database                               | Tables                                                       |             Size | Link                                                                                                              |
| -------------------------------------- | ------------------------------------------------------------ | ---------------: | ----------------------------------------------------------------------------------------------------------------- |
| **MIMIC-IV**                           | 20+ (patients, admissions, diagnoses, procedures, labevents) | ~380K admissions | [PhysioNet](https://physionet.org/content/mimiciv/2.2/) (requires credentialing)                                  |
| **CMS Medicare Inpatient** ✅          | 1 (SynPUF inpatient claims, 81 cols)                         |      ~67K claims | [CMS](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files) |
| **Hospital Inpatient Discharges (NY)** | 1 large table                                                |       ~2.5M rows | [Kaggle](https://www.kaggle.com/datasets/rohitrox/hospital-inpatient-discharges)                                  |

## Finance / Fintech

| Database                     | Tables                                 |                       Size | Link                                                                          |
| ---------------------------- | -------------------------------------- | -------------------------: | ----------------------------------------------------------------------------- |
| **Lending Club**             | 2 (accepted, rejected loans)           |       2.26M rows, 151 cols | [Kaggle](https://www.kaggle.com/datasets/wordsforthewise/lending-club)        |
| **FDIC Bank Data** ✅        | 2 (institutions, financials 2020-24)   | ~4.3K banks, 84K quarterly | [FDIC](https://www.fdic.gov/bank-data)                                        |
| **SEC Financial Statements** | 5+ (companies, statements, line items) |                   millions | [SEC EDGAR](https://www.sec.gov/dera/data/financial-statement-data-sets.html) |
| **Brazilian Credit Risk**    | 3 (clients, loans, payments)           |               ~45K clients | [Kaggle](https://www.kaggle.com/datasets/laotse/credit-risk-dataset)          |

## Marketing / Advertising

| Database                       | Tables                              |       Size | Link                                                                                            |
| ------------------------------ | ----------------------------------- | ---------: | ----------------------------------------------------------------------------------------------- |
| **Criteo Display Ads**         | 1 large table                       |  ~45M rows | [Kaggle](https://www.kaggle.com/c/criteo-display-ad-challenge)                                  |
| **Google Analytics Sample** ✅ | 1 (Cyclistic bike-share trips 2021) | 5.6M trips | [Kaggle](https://www.kaggle.com/datasets/kirilosyossif/cyclistic-case-study-google-certificate) |
| **Marketing Campaign (Maven)** | 1 table                             | ~2.2K rows | [Kaggle](https://www.kaggle.com/datasets/rodsaldanha/arketing-campaign)                         |

## SaaS / Product

| Database                      | Tables                            |               Size | Link                                                              |
| ----------------------------- | --------------------------------- | -----------------: | ----------------------------------------------------------------- |
| **Stack Overflow Data**       | 4 (users, posts, comments, votes) |           millions | [Stack Exchange](https://data.stackexchange.com/stackoverflow)    |
| **Amplitude Public Datasets** | 2-3 (events, users)               | millions of events | [Amplitude](https://amplitude.com/blog/amplitude-public-datasets) |
| **GitHub Archive**            | 1 large table                     | billions of events | [GH Archive](https://www.gharchive.org/)                          |

## Operations / Supply Chain

| Database                  | Tables                              |                Size | Link                                                                                             |
| ------------------------- | ----------------------------------- | ------------------: | ------------------------------------------------------------------------------------------------ |
| **TPC-DS** ✅             | 24 (sales, inventory, catalog, web) | SF=0.01, ~277K rows | [TPC](https://www.tpc.org/tpcds/)                                                                |
| **Supply Chain Shipment** | 1 table                             |          ~1.8K rows | [Kaggle](https://www.kaggle.com/datasets/divyeshardeshana/supply-chain-shipment-pricing-dataset) |
| **Brazilian Logistics**   | 3 (shipments, routes, carriers)     |     ~100K shipments | [Kaggle](https://www.kaggle.com/datasets/willianoliveiragibin/brazilian-ecommerce-logistics)     |

## Demographics / Government

| Database                     | Tables                            |                                      Size | Link                                                                              |
| ---------------------------- | --------------------------------- | ----------------------------------------: | --------------------------------------------------------------------------------- |
| **US Census ACS** ✅         | 2 (tracts, counties, 37 cols)     |                                74K tracts | [Kaggle](https://www.kaggle.com/datasets/muonneutrino/us-census-demographic-data) |
| **Census-Income (KDD)**      | 1 large table                     |                                ~299K rows | [UCI](https://archive.ics.uci.edu/dataset/117/census+income+kdd)                  |
| **World Bank Indicators** ✅ | 3 (countries, indicators, values) | 217 countries, 40 indicators, 337K values | [World Bank](https://data.worldbank.org/)                                         |

---

## How to add one

1. Download the dataset (CSV/Parquet per table)
2. Create `data/datasets/<id>/schema.json` (tables, columns, PKs, FKs)
3. Place per-table CSVs in the same dir
4. Add a `questions.json` difficulty ladder
5. Load via `POST /api/datasets/<id>/load`

The loader handles FKs, streaming COPY, and dirty rows — same as the generated suite.
