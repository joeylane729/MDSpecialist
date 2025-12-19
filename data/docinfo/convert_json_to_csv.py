#!/usr/bin/env python3
"""Convert existing JSON results to CSV."""

import json
import csv
from pathlib import Path

json_file = Path(__file__).parent / 'license_info_results.json'
csv_file = Path(__file__).parent / 'license_info_results.csv'

# Read JSON
with open(json_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# Flatten results for CSV - one row per match
csv_rows = []
for result in results:
    npi = result['npi']
    first_name = result['first_name']
    last_name = result['last_name']
    full_name = result['full_name']
    
    if result.get('matches'):
        for match in result['matches']:
            # Handle failed profile retrievals (different structure)
            if 'error' in match and match.get('profile_id'):
                csv_rows.append({
                    'npi': npi,
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': full_name,
                    'docinfo_id': match.get('profile_id', ''),
                    'docinfo_full_name': match.get('docinfo_name', ''),
                    'graduation_year': '',
                    'medical_school_name': '',
                    'degree_code': '',
                    'licensures': '',
                    'certifications': '',
                    'locations': '',
                    'board_actions': match.get('error', '')
                })
                continue
            
            # Format locations as semicolon-separated string
            locations_list = match.get('locations', [])
            if isinstance(locations_list, list):
                locations_str = '; '.join([f"{loc.get('city', '')}, {loc.get('state', '')}" for loc in locations_list])
            else:
                locations_str = ''
            
            # Format licensures as semicolon-separated string
            licensures_list = match.get('licensures', [])
            licensures_str = '; '.join(licensures_list) if isinstance(licensures_list, list) else ''
            
            # Format certifications as semicolon-separated string
            certs_list = match.get('certifications', [])
            certifications_str = '; '.join(certs_list) if isinstance(certs_list, list) else ''
            
            # Format board actions
            board_actions = []
            boards_actions_list = match.get('boardsActionsByState', [])
            if isinstance(boards_actions_list, list):
                for state_action in boards_actions_list:
                    state = state_action.get('state', '')
                    orders = state_action.get('orders', [])
                    if isinstance(orders, list):
                        for order in orders:
                            order_date = order.get('orderDate', '')
                            action = order.get('action', '')
                            board_actions.append(f"{state}: {order_date} - {action}")
            board_actions_str = '; '.join(board_actions) if board_actions else ''
            
            csv_rows.append({
                'npi': npi,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'docinfo_id': match.get('_id', ''),
                'docinfo_full_name': match.get('fullName', ''),
                'graduation_year': match.get('graduationYear', ''),
                'medical_school_name': match.get('medicalSchoolName', ''),
                'degree_code': match.get('degreeCode', ''),
                'licensures': licensures_str,
                'certifications': certifications_str,
                'locations': locations_str,
                'board_actions': board_actions_str
            })
    else:
        # No matches - still create a row
        csv_rows.append({
            'npi': npi,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'docinfo_id': '',
            'docinfo_full_name': '',
            'graduation_year': '',
            'medical_school_name': '',
            'degree_code': '',
            'licensures': '',
            'certifications': '',
            'locations': '',
            'board_actions': result.get('error', '')
        })

# Write to CSV
fieldnames = ['npi', 'first_name', 'last_name', 'full_name', 'docinfo_id', 'docinfo_full_name', 
              'graduation_year', 'medical_school_name', 'degree_code', 'licensures', 
              'certifications', 'locations', 'board_actions']

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"✅ Converted {len(results)} doctor results to {len(csv_rows)} CSV rows")
print(f"💾 Saved to: {csv_file}")

