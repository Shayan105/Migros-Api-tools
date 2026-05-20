from fastapi import FastAPI, HTTPException, Query
from pymongo import MongoClient
from typing import List, Optional
from datetime import datetime, time, timedelta

app = FastAPI(title="Migros Scraper API", version="1.1.0")

DB_NAME = "migros_db"
MONGO_URL = "mongodb://127.0.0.1:27017/"

def get_db():
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)[DB_NAME]

def format_mongo_doc(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("scraped_at"), datetime):
            doc["scraped_at"] = doc["scraped_at"].isoformat()
    return doc

def build_date_query(date_str: str = None, start_str: str = None, end_str: str = None):
    query = {}
    
    if date_str:
        day_start = datetime.combine(datetime.strptime(date_str, "%Y-%m-%d"), time.min)
        day_end = datetime.combine(day_start, time.max)
        query["scraped_at"] = {"$gte": day_start, "$lte": day_end}
    
    elif start_str or end_str:
        range_query = {}
        if start_str:
            range_query["$gte"] = datetime.combine(datetime.strptime(start_str, "%Y-%m-%d"), time.min)
        if end_str:
            range_query["$lte"] = datetime.combine(datetime.strptime(end_str, "%Y-%m-%d"), time.max)
        query["scraped_at"] = range_query
        
    return query

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
    try:
        db = get_db()
        
        valid_categories = [c for c in db.list_collection_names() if not c.startswith("system.")]
        if category not in valid_categories:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

        match_filter = {}
        if is_reduced is not None:
            match_filter["is_reduced"] = is_reduced

        date_query = build_date_query(date, start_date, end_date)
        has_date_filter = bool(date_query)
        
        if has_date_filter:
            match_filter.update(date_query)
            skip = (page - 1) * limit
            cursor = db[category].find(match_filter).sort("scraped_at", -1).skip(skip).limit(limit)
            
            products = [format_mongo_doc(p) for p in cursor]
            total = db[category].count_documents(match_filter)
        else:
            pipeline = [
                {"$match": match_filter},
                {"$sort": {"scraped_at": -1}},
                {
                    "$group": {
                        "_id": "$id",
                        "latest_doc": {"$first": "$$ROOT"}
                    }
                },
                {"$replaceRoot": {"newRoot": "$latest_doc"}},
                {"$sort": {"scraped_at": -1}},
                {"$skip": (page - 1) * limit},
                {"$limit": limit}
            ]
            
            total_pipeline = [
                {"$match": match_filter},
                {"$group": {"_id": "$id"}},
                {"$count": "count"}
            ]
            
            cursor = db[category].aggregate(pipeline)
            products = [format_mongo_doc(p) for p in cursor]
            
            count_result = list(db[category].aggregate(total_pipeline))
            total = count_result[0]["count"] if count_result else 0

        return {
            "category": category,
            "mode": "snapshot" if has_date_filter else "latest_distinct",
            "total_matches": total,
            "results": products
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/categories", tags=["Metadata"])
def list_categories():
    try:
        db = get_db()
        categories = [c for c in db.list_collection_names() if not c.startswith("system.")]
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)