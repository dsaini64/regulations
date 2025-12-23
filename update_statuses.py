"""
Script to update existing regulations with proper status analysis
"""
import sqlite3
import sys
import time
from app import RegulationScraper

DB_NAME = 'regulations.db'

def update_all_statuses():
    """Update status for all existing regulations"""
    print("=" * 60)
    print("🔄 Starting status update for all regulations...")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get all regulations
    print("\n📊 Fetching regulations from database...")
    c.execute('SELECT id, description, url FROM regulations')
    regulations = c.fetchall()
    total = len(regulations)
    print(f"✅ Found {total} regulations to update\n")
    
    if total == 0:
        print("⚠️  No regulations found in database!")
        conn.close()
        return
    
    print("🔧 Initializing regulation analyzer...")
    scraper = RegulationScraper()
    print("✅ Analyzer ready\n")
    
    updated = 0
    status_counts = {}
    start_time = time.time()
    
    print("⏳ Processing regulations...")
    print("-" * 60)
    
    for idx, (reg_id, description, url) in enumerate(regulations, 1):
        try:
            # Show progress
            if idx % 5 == 0 or idx == 1:
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = (total - idx) / rate if rate > 0 else 0
                print(f"📝 [{idx}/{total}] Processing regulation {reg_id}... "
                      f"({int(rate)} regs/sec, ~{int(remaining)}s remaining)", end='\r')
                sys.stdout.flush()
            
        status, status_reason = scraper.analyze_regulation_status(description or '', url or '')
        
        c.execute('''
            UPDATE regulations 
            SET status = ?, status_reason = ?
            WHERE id = ?
        ''', (status, status_reason, reg_id))
        
            # Track status distribution
            status_counts[status] = status_counts.get(status, 0) + 1
        updated += 1
            
        except Exception as e:
            print(f"\n❌ Error updating regulation {reg_id}: {e}")
            continue
    
    print("\n" + "-" * 60)
    print(f"💾 Committing changes to database...")
    conn.commit()
    conn.close()
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("✅ STATUS UPDATE COMPLETE!")
    print("=" * 60)
    print(f"\n📈 Summary:")
    print(f"   • Total regulations updated: {updated}/{total}")
    print(f"   • Time taken: {elapsed_time:.2f} seconds")
    print(f"   • Average rate: {updated/elapsed_time:.2f} regulations/second")
    print(f"\n📊 Status Distribution:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        percentage = (count / updated * 100) if updated > 0 else 0
        print(f"   • {status}: {count} ({percentage:.1f}%)")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    try:
    update_all_statuses()
    except KeyboardInterrupt:
        print("\n\n⚠️  Update cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

