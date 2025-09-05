#!/usr/bin/env python3
"""
Show complete distribution of all publication types with exact counts.
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def extract_publication_types(article: ET.Element):
    """Extract publication types from the article."""
    pub_types = []
    pub_type_list = article.find('.//PublicationTypeList')
    if pub_type_list is not None:
        for pub_type in pub_type_list.findall('PublicationType'):
            if pub_type.text:
                pub_types.append(pub_type.text.strip())
    return pub_types

def main():
    """Show complete publication type distribution."""
    # Get the data directory path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    data_dir = project_root / "data" / "pubmed"
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    # Find all XML files
    xml_files = list(data_dir.glob("*.xml"))
    if not xml_files:
        print(f"❌ No XML files found in {data_dir}")
        return
    
    print("📚 Complete Publication Type Distribution")
    print("=" * 80)
    print(f"Processing {len(xml_files)} XML files...")
    
    # Initialize counters
    article_count = 0
    pub_type_counts = Counter()
    pub_types_with_data = 0
    pub_types_without_data = 0
    
    for xml_file in sorted(xml_files):
        print(f"📖 Processing {xml_file.name}...")
        context = ET.iterparse(str(xml_file), events=('start', 'end'))
        file_articles = 0
        
        for event, elem in context:
            if event == 'end' and elem.tag == 'PubmedArticle':
                article_count += 1
                file_articles += 1
                
                # Extract publication types
                pub_types = extract_publication_types(elem)
                if pub_types:
                    for pub_type in pub_types:
                        pub_type_counts[pub_type] += 1
                    pub_types_with_data += 1
                else:
                    pub_types_without_data += 1
                
                # Clear element to free memory
                elem.clear()
                
                # Progress indicator
                if file_articles % 10000 == 0:
                    print(f"   Processed {file_articles:,} articles from this file...")
        
        print(f"   ✅ Completed {xml_file.name}: {file_articles:,} articles")
    
    # Print complete results
    print(f"\n📈 Overall Statistics:")
    print(f"   Total articles processed: {article_count:,}")
    print(f"   Articles with publication types: {pub_types_with_data:,}")
    print(f"   Articles without publication types: {pub_types_without_data:,}")
    print(f"   Coverage: {(pub_types_with_data/article_count)*100:.1f}%")
    print(f"   Total unique publication types: {len(pub_type_counts)}")
    
    print(f"\n📚 Complete Publication Type Distribution:")
    print(f"   {'Rank':<4} {'Type':<50} {'Count':<10} {'Percentage':<12}")
    print(f"   {'-'*4} {'-'*50} {'-'*10} {'-'*12}")
    
    total_pub_type_instances = sum(pub_type_counts.values())
    
    for rank, (pub_type, count) in enumerate(pub_type_counts.most_common(), 1):
        percentage = (count / total_pub_type_instances) * 100
        print(f"   {rank:<4} {pub_type:<50} {count:<10,} {percentage:<12.2f}%")
    
    print(f"\n✅ Analysis completed!")
    print(f"   Total publication type instances: {total_pub_type_instances:,}")

if __name__ == "__main__":
    main()

