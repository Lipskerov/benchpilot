#!/usr/bin/env python3
"""
Fetch TNBC papers from PubMed using NCBI E-utilities.
Query: ("triple negative breast cancer"[Title/Abstract] OR TNBC[Title/Abstract]) 
       AND hasabstract AND 2019:2026[dp]
Cap: 800 records
Output: data/snapshot/papers.jsonl
Rate limit: ≤3 req/s, retmax=200 per batch
"""

import json
import time
from pathlib import Path
from typing import List, Dict
import requests
from xml.etree import ElementTree as ET


# NCBI E-utilities endpoints
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Query parameters
QUERY = '("triple negative breast cancer"[Title/Abstract] OR TNBC[Title/Abstract]) AND hasabstract AND 2019:2026[dp]'
MAX_RECORDS = 800
BATCH_SIZE = 200  # NCBI recommends ≤200 per request
RATE_LIMIT_DELAY = 0.34  # ~3 requests per second


def search_pubmed(query: str, max_results: int) -> List[str]:
    """
    Search PubMed and return list of PMIDs.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance"
    }
    
    print(f"Searching PubMed with query: {query[:100]}...")
    response = requests.get(ESEARCH_URL, params=params)
    response.raise_for_status()
    
    data = response.json()
    pmids = data.get("esearchresult", {}).get("idlist", [])
    count = int(data.get("esearchresult", {}).get("count", 0))
    
    print(f"Found {count} total results, retrieving {len(pmids)} PMIDs")
    return pmids


def fetch_pubmed_batch(pmids: List[str]) -> List[Dict]:
    """
    Fetch paper details for a batch of PMIDs.
    Returns list of paper records.
    """
    if not pmids:
        return []
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    
    response = requests.get(EFETCH_URL, params=params)
    response.raise_for_status()
    
    # Parse XML response
    root = ET.fromstring(response.content)
    papers = []
    
    for article in root.findall(".//PubmedArticle"):
        try:
            # Extract PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            # Extract title
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""
            
            # Extract abstract (concatenate all AbstractText elements)
            abstract_parts = []
            for abstract_text in article.findall(".//AbstractText"):
                label = abstract_text.get("Label", "")
                text = abstract_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)
            
            # Extract journal
            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""
            
            # Extract year
            year_elem = article.find(".//PubDate/Year")
            if year_elem is None:
                year_elem = article.find(".//PubDate/MedlineDate")
            year = int(year_elem.text[:4]) if year_elem is not None and year_elem.text else None
            
            # Extract MeSH terms
            mesh_terms = []
            for mesh in article.findall(".//MeshHeading/DescriptorName"):
                mesh_terms.append(mesh.text)
            
            if pmid and title and abstract:
                papers.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract,
                    "journal": journal,
                    "year": year,
                    "mesh": mesh_terms
                })
        except Exception as e:
            print(f"Error parsing article: {e}")
            continue
    
    return papers


def main():
    """
    Main execution: search PubMed, fetch papers in batches, save to JSONL.
    """
    # Ensure output directory exists
    output_dir = Path("data/snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "papers.jsonl"
    
    # Search for PMIDs
    pmids = search_pubmed(QUERY, MAX_RECORDS)
    
    if not pmids:
        print("No results found")
        return
    
    # Fetch papers in batches
    all_papers = []
    total_batches = (len(pmids) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, len(pmids), BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch_pmids = pmids[i:i + BATCH_SIZE]
        
        print(f"Fetching batch {batch_num}/{total_batches} ({len(batch_pmids)} PMIDs)...")
        papers = fetch_pubmed_batch(batch_pmids)
        all_papers.extend(papers)
        
        print(f"  Retrieved {len(papers)} papers")
        
        # Rate limiting
        if i + BATCH_SIZE < len(pmids):
            time.sleep(RATE_LIMIT_DELAY)
    
    # Save to JSONL
    print(f"\nSaving {len(all_papers)} papers to {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for paper in all_papers:
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")
    
    print(f"✓ Done! Saved {len(all_papers)} TNBC papers")
    
    # Print summary statistics
    years = [p["year"] for p in all_papers if p.get("year")]
    if years:
        print(f"  Year range: {min(years)}-{max(years)}")
    print(f"  Average abstract length: {sum(len(p['abstract']) for p in all_papers) / len(all_papers):.0f} chars")


if __name__ == "__main__":
    main()
