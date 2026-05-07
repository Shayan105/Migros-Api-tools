from fastapi import FastAPI, HTTPException, Query
from pymongo import MongoClient
from typing import List, Optional
from datetime import datetime, time, timedelta

app = FastAPI(title="Migros Scraper API", version="1.1.0")

# --- DATABASE SETUP ---
DB_NAME = "migros_db"
MONGO_URL = "mongodb://localhost:27017/"

def get_db():
    return MongoClient(MONGO_URL)[DB_NAME]

def format_mongo_doc(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("scraped_at"), datetime):
            doc["scraped_at"] = doc["scraped_at"].isoformat()
    return doc

def build_date_query(date_str: str = None, start_str: str = None, end_str: str = None):
    """Helper to construct MongoDB date filters."""
    query = {}
    
    # Specific Day (YYYY-MM-DD)
    if date_str:
        day_start = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d"), time.min)
        day_end = datetime.combine(day_start, time.max)
        query["scraped_at"] = {"$gte": day_start, "$lte": day_end}
    
    # Date Range
    elif start_str or end_str:
        range_query = {}
        if start_str:
            range_query["$gte"] = datetime.combine(datetime.strptime(start_str, "%Y-%m-%d"), time.min)
        if end_str:
            range_query["$lte"] = datetime.combine(datetime.strptime(end_str, "%Y-%m-%d"), time.max)
        query["scraped_at"] = range_query
        
    return query

# --- ENDPOINTS ---
@app.get("/products/{category}", tags=["Products"])
def get_products(
    category: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    is_reduced: Optional[bool] = None
):
    db = get_db()
    if category not in db.list_collection_names():
        raise HTTPException(status_code=404, detail="Category not found")

    # 1. Base Filters (Reduction status)
    match_filter = {}
    if is_reduced is not None:
        match_filter["is_reduced"] = is_reduced

    # 2. Date Filtering Logic
    date_query = build_date_query(date, start_date, end_date)
    has_date_filter = bool(date_query) # True if user provided date/range
    
    if has_date_filter:
        # Standard query if dates are provided
        match_filter.update(date_query)
        skip = (page - 1) * limit
        cursor = db[category].find(match_filter).sort("scraped_at", -1).skip(skip).limit(limit)
        
        products = [format_mongo_doc(p) for p in cursor]
        total = db[category].count_documents(match_filter)
    else:
        # AGGREGATION: Get latest distinct products by 'id'
        pipeline = [
            {"$match": match_filter},
            {"$sort": {"scraped_at": -1}}, # Sort globally by date first
            {
                "$group": {
                    "_id": "$id", # Group by the product's business ID
                    "latest_doc": {"$first": "$$ROOT"} # Grab the most recent document for each ID
                }
            },
            {"$replaceRoot": {"newRoot": "$latest_doc"}}, # Flatten the structure back
            {"$sort": {"scraped_at": -1}}, # Sort the distinct results by date
            {"$skip": (page - 1) * limit},
            {"$limit": limit}
        ]
        
        # We need a separate pipeline or a facet for the total count of distinct items
        total_pipeline = [
            {"$match": match_filter},
            {"$group": {"_id": "$id"}}
        ]
        
        cursor = db[category].aggregate(pipeline)
        products = [format_mongo_doc(p) for p in cursor]
        
        # Get count of distinct IDs
        distinct_groups = list(db[category].aggregate(total_pipeline))
        total = len(distinct_groups)

    return {
        "category": category,
        "mode": "snapshot" if has_date_filter else "latest_distinct",
        "total_matches": total,
        "results": products
    }

@app.get("/categories", tags=["Metadata"])
def list_categories():
    return {"categories": get_db().list_collection_names()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)