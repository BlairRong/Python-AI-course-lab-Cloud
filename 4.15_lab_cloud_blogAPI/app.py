# app.py
import os
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)


# --- Cosmos DB Configuration配置 ---
# Get connection string from environment variable
conn_str = os.environ.get('CONNECTION_STRING')
if not conn_str:
    raise ValueError("Please set your CONNECTION_STRING environment variable.")

# Initialize Cosmos DB client (using the connecting string)
client = CosmosClient.from_connection_string(conn_str)

# Define database and container names
DATABASE_NAME = "blogdb"
CONTAINER_NAME = "posts"

# Get or create the database
try:
    database = client.create_database_if_not_exists(id=DATABASE_NAME)
    print(f"Database '{DATABASE_NAME}' ready.")
except exceptions.CosmosHttpResponseError as e:
    print(f"Error creating database: {e.message}")
    exit(1)

# Get or create the container
try:
    container = database.create_container_if_not_exists(
        id=CONTAINER_NAME,
        partition_key=PartitionKey(path="/author"),
        offer_throughput=400  # 400 RU/s is the minimum, suitable for learning
    )
    print(f"Container '{CONTAINER_NAME}' ready.")
except exceptions.CosmosHttpResponseError as e:
    print(f"Error creating container: {e.message}")
    exit(1)




# --- API Endpoints 端点 ---

# 1. GET /posts - Retrieve all posts
@app.route('/posts', methods=['GET'])
def get_posts():
    """Retrieve all blog posts from Cosmos DB."""
    try:
        # Query to fetch all items
        query = "SELECT * FROM c"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        # Sort by timestamp, newest first
        items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve posts: {str(e)}"}), 500

# 2. GET /posts/<id> - Retrieve a single post by its ID
@app.route('/posts/<id>', methods=['GET'])
def get_post(id):
    """Retrieve a single blog post by its ID."""
    try:
        # Read the item directly. Partition key is required.
        # Since we don't have the author for the query, we use a cross-partition query.
        query = f"SELECT * FROM c WHERE c.id = '{id}'"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        if not items:
            return jsonify({"error": "Post not found"}), 404
        return jsonify(items[0]), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve post: {str(e)}"}), 500

# 3. POST /posts - Create a new post
@app.route('/posts', methods=['POST'])
def create_post():
    """Create a new blog post."""
    data = request.get_json()
    
    # Validate required fields
    if not data or not all(k in data for k in ('title', 'content', 'author')):
        return jsonify({"error": "Missing required fields: title, content, author"}), 400
    
    # Create a new post document
    new_post = {
        "id": str(uuid.uuid4()),  # uuid module is to generate a unique ID
        "title": data['title'],
        "content": data['content'],
        "author": data['author'],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    #Error handling with try...except blocks ensures the API returns meaningful HTTP status codes and messages instead of crashing.
    try:
        # Insert the new item into Cosmos DB
        container.create_item(body=new_post)
        return jsonify(new_post), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create post: {str(e)}"}), 500

# 4. DELETE /posts/<id> - Delete a post by its ID
@app.route('/posts/<id>', methods=['DELETE'])
def delete_post(id):
    """Delete a blog post by its ID."""
    try:
        # First, find the item to get its partition key (author)
        query = f"SELECT * FROM c WHERE c.id = '{id}'"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        if not items:
            return jsonify({"error": "Post not found"}), 404
        
        # Delete the item using its ID and partition key (author)
        post_to_delete = items[0]
        container.delete_item(item=id, partition_key=post_to_delete['author'])
        return jsonify({"message": "Post deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete post: {str(e)}"}), 500

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000) #app.run(debug=True, port=5001) local text