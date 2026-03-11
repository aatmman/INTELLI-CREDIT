import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Missing SUPABASE credentials")
    exit(1)

supabase: Client = create_client(url, key)

try:
    buckets = supabase.storage.list_buckets()
    bucket_names = [b.name for b in buckets]
    print(f"Existing buckets: {bucket_names}")
    
    if "documents" not in bucket_names:
        print("Creating 'documents' bucket...")
        supabase.storage.create_bucket("documents")
        print("Bucket 'documents' created successfully!")
    else:
        print("Bucket 'documents' already exists.")
except Exception as e:
    print(f"Error checking/creating bucket: {e}")
