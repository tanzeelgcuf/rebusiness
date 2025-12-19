from database_manager import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)

def cleanup_urls():
    db = DatabaseManager()
    conn = db._connect_db()
    cursor = conn.cursor()
    
    bad_domains = [
        '%stackoverflow%',
        '%youtube%',
        '%google%',
        '%wikipedia%',
        '%facebook%',
        '%instagram%',
        '%linkedin%',
        '%twitter%',
        '%amazon%',
        '%ebay%',
        '%yellowpages%',
        '%yelp%',
        '%zhihu%',
        '%desidime%',
        '%berkeley.edu%',
        '%baidu%',
        '%gov.uk%',
        '%statista%',
        '%pixabay%',
        '%cnetfrance%',
        '%wordreference%',
        '%pojie%',
        '%question%',
        '%discussion%',
        '%forum%',
        '%thread%',
        '%topic%',
        '%translate%',
        '%support%'
    ]
    
    try:
        logging.info("Starting cleanup...")
        total_deleted = 0
        
        for domain in bad_domains:
            cursor.execute(f"SELECT COUNT(*) FROM manufacturers WHERE website LIKE ?", (domain,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                cursor.execute(f"DELETE FROM manufacturers WHERE website LIKE ?", (domain,))
                logging.info(f"Deleted {count} records with domain matching {domain}")
                total_deleted += count
        
        conn.commit()
        logging.info(f"Cleanup complete. Total records deleted: {total_deleted}")
        
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")
    finally:
        db._close_db()

if __name__ == "__main__":
    cleanup_urls()
