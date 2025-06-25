import time
import random
from database import log_message, supabase

def test_db_insertion():
    """
    Tests the database connection by inserting and verifying a sample record.
    """
    print("Running database insertion test...")

    if not supabase:
        print("❌ Supabase client not initialized. Check your .env file and credentials.")
        return

    # 1. Generate unique data for this test run to avoid ambiguity.
    session_id = int(time.time())
    unique_marker = random.randint(1000, 9999)
    test_content = f"Database connection test message. ID: {unique_marker}"
    
    print(f"Attempting to log a test message with session_id: {session_id} and content: '{test_content}'")

    # 2. Call the existing log_message function to insert the data.
    # This function has its own error handling, but we'll verify the result manually.
    log_message(
        session_id=session_id,
        content=test_content,
        direction="outbound",
    )
    
    # 3. Verify the insertion by querying for the unique message.
    print("Verifying insertion...")
    time.sleep(1) # Give the database a moment to process the insert.

    try:
        # We specifically select the 'content' to match against our unique marker.
        response = supabase.table("messages").select("id, content").eq("content", test_content).execute()
        
        if response.data:
            print("✅ Verification successful! Found the test message in the database.")
            print(f"   -> Found record: {response.data[0]}")
        else:
            print("❌ Verification failed. Could not find the test message in the database.")
            print("   -> The insert may have failed silently. Check your database's logs on Supabase.")
            print(f"   -> API Response from Supabase (for debugging): {response}")

    except Exception as e:
        print(f"❌ An error occurred during the verification step: {e}")


if __name__ == "__main__":
    test_db_insertion() 