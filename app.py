from flask import Flask, render_template, request
from google.cloud import datastore, pubsub_v1
import requests
import json

app = Flask(__name__)

datastore_client = datastore.Client()

PRODUCTS_API_URL = "https://product-backend-327554758505.us-central1.run.app/products"

# Pub/Sub setup
PROJECT_ID = "silent-octagon-460701-a0"
TOPIC_ID = "inventory-stock-alerts"
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def publish_stock_alert(product_id, product_name, stock):
    data = {
        "product_id": product_id,
        "product_name": product_name,
        "stock": stock
    }
    print(f"Publishing to PubSub: {data}")
    future = publisher.publish(topic_path, json.dumps(data).encode("utf-8"))
    message_id = future.result()
    print(f"Published message ID: {message_id}")
    return message_id

@app.route('/', methods=['GET', 'POST'])
def home():
    response = requests.get(PRODUCTS_API_URL)
    products = response.json()

    if request.method == 'POST':
        product_id_raw = request.form.get('product_id')
        product_id = product_id_raw.split('-')[0].strip()
        product_name = product_id_raw.split('-', 1)[1].strip()
        stock_value = request.form.get('inventory_stock')
        key = datastore_client.key('Inventory', product_id)
        entity = datastore.Entity(key=key)
        entity['stock'] = int(stock_value)
        entity['product_name'] = product_name
        datastore_client.put(entity)
        return render_template('submit.html', product_id=product_id, stock_value=stock_value, product_name=product_name)
    return render_template('index.html', products=products)

@app.route('/decrement_stock', methods=['POST'])
def decrement_stock():
    data = request.get_json()
    product_id = data['product_id']
    decrement = int(data['decrement'])
    key = datastore_client.key('Inventory', product_id)
    entity = datastore_client.get(key)
    entity['stock'] = max(0, entity['stock'] - decrement)
    datastore_client.put(entity)

    # Publish to Pub/Sub if stock < 10
    if entity['stock'] < 10:
        publish_stock_alert(product_id, entity.get('product_name', ''), entity['stock'])

    return {'product_id': product_id, 'new_stock': entity['stock']}, 200

@app.route('/get_all_stock', methods=['GET'])
def get_all_stock():
    query = datastore_client.query(kind='Inventory')
    results = list(query.fetch())
    inventory_list = []
    for entity in results:
        inventory_list.append({
            'product_id': entity.key.name or entity.key.id,
            'product_name': entity.get('product_name', ''),
            'stock': entity.get('stock', 0)
        })
    return {'inventory': inventory_list}, 200

if __name__ == '__main__':
    app.run(debug=True, port=5010)