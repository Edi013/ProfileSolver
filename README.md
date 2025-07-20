# Profile Resolver Project

## Overview & Chapters

A multi-stage system for crawling the web, enriching company data, synchronizing it to databases and Elasticsearch, and exposing a REST API for powerful search capabilities.

### Chapters

- [1. Requirements](#requirements)
- [2. Tools](#tools)
- [3. How to use](#how-to-use)
- [4. Time tests scraper](#time-tests-scraper)

---

## Requirements

- Python 3.x
- PostgreSQL latest
- Java 17
- Elasticsearch latest

---

## Tools

- IntelliJ IDEA 2025 (Java API)
- PyCharm 2025 (Python scripts)
- pgAdmin4 (PostgreSQL management)
- Terminal (Git, Docker, Curl)

---

## How to Use

### 1. Scrape, store, analyze & merge data

1.1 Initialize the database using the seed method in the scraper.
1.2 Run the scraper. Higher `timeout` and `depth` values yield richer data.
1.3 Use the unifier to merge additional datasets with your findings.

---

### 2. Integrate Elasticsearch with your database

2.1 Start the Elasticsearch container.  
2.2 Create the required index.  
2.3 Sync data using the provided Python synchronizer script.  

---

### 3. Query ElasticSearch via a REST API

3.1 Start the API:
```
mvn spring-boot:run
```

3.2 Hit the endpoint

```
http://localhost:8080/api/companies/search?query=key_word_about_company
```

## Time tests scraper

Context:
- my machine has 12cores, 24 threads.
- max depth per domain = 5.
- timeout per request = 3s.

Chunck size = how many threads will python access :
- 18 = 11m 31s
- 23 = 10m 34s
- 24 = 10m 13s
