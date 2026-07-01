#!/usr/bin/env python3
"""
Fetch TNBC trials from ClinicalTrials.gov using API v2.
Query: cond="triple negative breast cancer"
Output: data/snapshot/trials.jsonl
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional
import requests


# ClinicalTrials.gov API v2 endpoint
API_BASE = "https://clinicaltrials.gov/api/v2/studies"

# Query parameters
CONDITION = "triple negative breast cancer"
PAGE_SIZE = 100  # Max allowed by API
RATE_LIMIT_DELAY = 0.5  # Be respectful with rate limiting


def fetch_trials_page(page_token: Optional[str] = None) -> Dict:
    """
    Fetch one page of trials from ClinicalTrials.gov API v2.
    Returns response with studies and next page token.
    """
    params = {
        "query.cond": CONDITION,
        "pageSize": PAGE_SIZE,
        "format": "json"
    }
    
    if page_token:
        params["pageToken"] = page_token
    
    response = requests.get(API_BASE, params=params)
    response.raise_for_status()
    
    return response.json()


def parse_trial(study: Dict) -> Dict:
    """
    Parse a trial record from API response into our schema.
    """
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    description = protocol.get("descriptionModule", {})
    conditions = protocol.get("conditionsModule", {})
    design = protocol.get("designModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    contacts = protocol.get("contactsLocationsModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    
    # Extract interventions
    interventions = []
    for intervention in arms.get("interventions", []):
        interventions.append({
            "type": intervention.get("type", ""),
            "name": intervention.get("name", "")
        })
    
    # Extract primary outcomes
    primary_outcomes = []
    for outcome in outcomes.get("primaryOutcomes", []):
        primary_outcomes.append(outcome.get("measure", ""))
    
    # Extract start date
    start_date_struct = status.get("startDateStruct", {})
    start_date = start_date_struct.get("date", "")
    
    # Extract enrollment
    enrollment_info = design.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count")
    
    return {
        "nct_id": identification.get("nctId", ""),
        "brief_title": identification.get("briefTitle", ""),
        "phase": design.get("phases", ["N/A"])[0] if design.get("phases") else "N/A",
        "status": status.get("overallStatus", ""),
        "conditions": conditions.get("conditions", []),
        "interventions": interventions,
        "primary_outcomes": primary_outcomes,
        "sponsor": sponsor.get("leadSponsor", {}).get("name", ""),
        "start_date": start_date,
        "enrollment": enrollment
    }


def main():
    """
    Main execution: fetch all TNBC trials, save to JSONL.
    """
    # Ensure output directory exists
    output_dir = Path("data/snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "trials.jsonl"
    
    all_trials = []
    page_token = None
    page_num = 1
    
    print(f"Fetching TNBC trials from ClinicalTrials.gov...")
    print(f"Condition: {CONDITION}\n")
    
    while True:
        print(f"Fetching page {page_num}...")
        
        try:
            response = fetch_trials_page(page_token)
            
            # Extract studies from response
            studies = response.get("studies", [])
            if not studies:
                break
            
            # Parse each study
            for study in studies:
                try:
                    trial = parse_trial(study)
                    if trial["nct_id"]:  # Only add if we have an NCT ID
                        all_trials.append(trial)
                except Exception as e:
                    print(f"  Error parsing study: {e}")
                    continue
            
            print(f"  Retrieved {len(studies)} trials (total: {len(all_trials)})")
            
            # Check for next page
            page_token = response.get("nextPageToken")
            if not page_token:
                break
            
            page_num += 1
            time.sleep(RATE_LIMIT_DELAY)
            
        except Exception as e:
            print(f"Error fetching page {page_num}: {e}")
            break
    
    # Save to JSONL
    print(f"\nSaving {len(all_trials)} trials to {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for trial in all_trials:
            f.write(json.dumps(trial, ensure_ascii=False) + "\n")
    
    print(f"✓ Done! Saved {len(all_trials)} TNBC trials")
    
    # Print summary statistics
    phases = {}
    statuses = {}
    for trial in all_trials:
        phase = trial.get("phase", "Unknown")
        phases[phase] = phases.get(phase, 0) + 1
        
        status = trial.get("status", "Unknown")
        statuses[status] = statuses.get(status, 0) + 1
    
    print("\nPhase distribution:")
    for phase, count in sorted(phases.items(), key=lambda x: x[1], reverse=True):
        print(f"  {phase}: {count}")
    
    print("\nStatus distribution:")
    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
