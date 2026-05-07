
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import json
import re 
from pymongo import MongoClient
import os
import json
from datetime import datetime
import os
import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


SLEEP_FACTOR = 0.5
URLS = {
    "pates_condiments_conserves": "https://www.migros.ch/fr/category/pates-condiments-conserves",
    "produits_laitiers_ufs_plats": "https://www.migros.ch/fr/category/produits-laitiers-ufs-plats-prep",
    "fruits_legumes": "https://www.migros.ch/fr/category/fruits-legumes",
    "viandes_poissons": "https://www.migros.ch/fr/category/viandes-poissons",
    "boulangerie_patisserie": "https://www.migros.ch/fr/category/boulangerie-patisserie-petit-dej",
    "pates_condiments_conserves":"https://www.migros.ch/fr/category/pates-condiments-conserves",
    "snacks_confiseries":"https://www.migros.ch/fr/category/snacks-confiseries",
    "surgeles":"https://www.migros.ch/fr/category/surgeles",
    "boissons_cafe_the":"https://www.migros.ch/fr/category/boissons-cafe-the",
    "vins_bieres_spiritueux":"https://www.migros.ch/fr/category/vins-bieres-spiritueux",
    "cosmetiques_droguerie":"https://www.migros.ch/fr/category/cosmetiques-droguerie",
    "entretien_nettoyage":"https://www.migros.ch/fr/category/entretien-nettoyage",
} 



def clean_price_to_float(raw_string):
    """Cleans Swiss price formats (1.-, 16.–, 1.−) into sortable floats."""
    if not raw_string:
        return None
    cleaned = raw_string.strip()
    # Regex: Look for a dot followed by any non-digit chars at the end and replace with .00
    cleaned = re.sub(r'\.\D+$', '.00', cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return cleaned

def parse_product(article):
    """Parses a single product card into a dictionary."""
    product_dict = {}
    
    # ID
    link_tag = article.find('a', {'data-testid': 'product-link'})
    product_dict['id'] = link_tag.get('href').rstrip('/').split('/')[-1] if link_tag else None
    
    # Brand & Name
    brand = article.find('span', class_='name')
    product_dict['brand'] = brand.text.strip() if brand else None
    name = article.find('span', attrs={'data-testid': lambda x: x and x.startswith('product-name')})
    product_dict['name'] = name.text.strip() if name else None
    
    # Price
    price_tag = article.find('span', {'data-testid': 'current-price'})
    product_dict['price'] = clean_price_to_float(price_tag.text) if price_tag else None

    # Promotion Check    
    promo_badge = article.find('span', class_='badge-promo')
    product_dict['is_reduced'] = promo_badge is not None

    if product_dict['is_reduced']:
        description_tag = promo_badge.find('span', {'data-testid': 'description'})
        product_dict['reduction_text'] = description_tag.text.strip() if description_tag else None
    else:
        product_dict['reduction_text'] = None
        
    # Quantity (Multipack Math)
    quantity_tag = article.find('span', {'data-testid': 'default-product-size'})
    if quantity_tag:
        raw_qty = quantity_tag.text.strip()
        multipack_match = re.search(r'(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', raw_qty)
        if multipack_match:
            total = int(multipack_match.group(1)) * float(multipack_match.group(2))
            unit = multipack_match.group(3)
            product_dict['quantity'] = f"{int(total) if total.is_integer() else total}{unit}"
        else:
            product_dict['quantity'] = raw_qty
    else:
        product_dict['quantity'] = None
    
    # Price per Unit & Unit
    product_dict['price_per_unit'], product_dict['unit'] = None, None
    ppu_tag = article.find('span', id=lambda x: x and x.endswith('-price-unit'))
    if ppu_tag:
        raw_ppu = ppu_tag.text.strip() 
        if '/' in raw_ppu:
            ppu_part, unit_part = raw_ppu.split('/', 1)
            product_dict['price_per_unit'] = clean_price_to_float(ppu_part)
            product_dict['unit'] = unit_part.strip() 
        else:
            product_dict['price_per_unit'] = clean_price_to_float(raw_ppu)
    
    # Image URL
    img = article.find('img')
    product_dict['image_url'] = img.get('src') if img else None
    
    return product_dict

def create_driver():
    print("Setting up the browser (Invisible Mode)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    return driver


def load_and_expand_page(driver, url):
    """
    Loads the page and clicks the 'Load More' button based on the presence
    of the 'remaining-products' counter.
    """
    print(f"Loading {url}...")
    driver.get(url)
    
    time.sleep(SLEEP_FACTOR*3) 
    
    click_count = 0
    while True:
        # 1. Scroll to bottom to ensure the counter and button are triggered/rendered
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SLEEP_FACTOR*1) 
        
        # 2. Check if the "remaining products" counter is still present
        try:
            driver.find_element(By.CSS_SELECTOR, "div.remaining-products")
        except NoSuchElementException:
            print("Finished: 'remaining-products' div not found. All products loaded.")
            break
            
        try:
            button = driver.find_element(By.CSS_SELECTOR, '[data-testid="view-more-button"]')
            
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(SLEEP_FACTOR*0.5)
            driver.execute_script("arguments[0].click();", button)
                        
            click_count += 1
            print(f"Action: Clicked 'Voir plus' ({click_count}). Waiting 2s for render...")
            
            time.sleep(SLEEP_FACTOR*2)
            
        except NoSuchElementException:
            print("Counter detected, but button not visible yet. Retrying scroll...")
            time.sleep(SLEEP_FACTOR*2)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break

    return driver.page_source


def fetch_product_data(base_url, path_to_json="migros_products.json", fetch_online=True):
    """
    Fetches product data either by dynamically scrolling the page or loading a local JSON file.
    """
    # --- LOCAL FILE OVERRIDE ---
    if not fetch_online:
        print(f"Bypassing online scrape. Attempting to load local file: '{path_to_json}'...")
        if os.path.exists(path_to_json):
            with open(path_to_json, 'r', encoding='utf-8') as f:
                all_products = json.load(f)
            print(f"✅ Successfully loaded {len(all_products)} products from local JSON.")
            return all_products 
        else:
            print(f"⚠️ Warning: Local file '{path_to_json}' not found! Forcing online fetch...")
            
    # --- LIVE SCRAPING LOGIC ---
    print(f"Fetching online data from: {base_url}")
    driver = create_driver()
    all_products = []
    
    try:
        # Get the fully expanded HTML with all products loaded
        rendered_html = load_and_expand_page(driver, base_url)
        
        if rendered_html:
            print("Parsing HTML...")
            soup = BeautifulSoup(rendered_html, 'html.parser')
            
            product_cards = soup.find_all('article', class_='product-card')
            print(f"Found {len(product_cards)} product elements. Extracting data...")
            
            for card in product_cards:
                parsed_data = parse_product(card)
                if parsed_data and parsed_data.get('name'):
                    all_products.append(parsed_data)
                    
    finally:
        driver.quit()

    print(f"\nSuccessfully extracted {len(all_products)} total products.")

    # Save the fresh data to JSON
    with open(path_to_json, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=4, ensure_ascii=False)
    print(f"All data successfully saved to '{path_to_json}'!")
    
    return all_products


def save_to_mongodb(products_list, db_name="migros_db", collection_name="products"):
    """Saves a list of dictionaries to MongoDB as daily snapshots."""
    
    # Connect to the local MongoDB server
    client = MongoClient("mongodb://localhost:27017/")
    db = client[db_name]
    collection = db[collection_name]
    
    print(f"Connected to MongoDB. Saving {len(products_list)} product snapshots...")
    
    scrape_timestamp = datetime.utcnow()
    
    for product in products_list:
        if not product.get('id'):
            continue
        product['scraped_at'] = scrape_timestamp
        collection.insert_one(product)
        
    print("Snapshot data successfully saved to MongoDB!")


def fetch_all_products():
    """Main function to fetch products for all categories and save to MongoDB."""
    for category, url in URLS.items():
        print(f"\n--- Starting scrape for category: {category} ---")
        products = fetch_product_data(base_url=url, path_to_json=f"{category}.json", fetch_online=True)
        save_to_mongodb(products_list=products, db_name="migros_db", collection_name=category)
        print(f"--- Completed scrape for category: {category} ---\n")


if __name__ == "__main__":
    # check if a mongodb server is running before starting the scraping process
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
        client.server_info()  # Trigger a server selection to check connection
        print("✅ MongoDB connection successful. Starting scraping process...")
        fetch_all_products()
    except Exception as e:
        print(f"⚠️ MongoDB connection failed: {e}") 