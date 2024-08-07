import os
import pymysql
import numpy as np
import json
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from transformers import LlamaTokenizer, LlamaModel
import torch
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

# bge-base embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")

# ollama
Settings.llm = Ollama(model="llama3", request_timeout=360.0)


# Load environment variables from .env file
load_dotenv()

# TiDB connection details
TIDB_HOST = os.getenv("TIDB_HOST")
TIDB_PORT = int(os.getenv("TIDB_PORT"))
TIDB_USER = os.getenv("TIDB_USER")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD")
TIDB_DATABASE = os.getenv("TIDB_DATABASE")

# Connect to TiDB with SSL/TLS
connection = pymysql.connect(
    host=TIDB_HOST,
    port=TIDB_PORT,
    user=TIDB_USER,
    password=TIDB_PASSWORD,
    database=TIDB_DATABASE,
    ssl={'ssl': True} 
)


# Generate a vector for a given query to the chat bot
def generate_query_vector(query):
    # Create an embedding instance
    embed_model = Settings.embed_model
    # Generate the vector for the text snippet
    vector = embed_model.get_embedding(query)
    return vector


# Search code snippets using TiDB's vector search capabilities
def search_code_snippets(query, top_k=1):
    query_vector = generate_query_vector(query).numpy()
    print (query_vector)
    with connection.cursor() as cursor:
        sql = """
        SELECT file_path, function_name, type, start_line, end_line, code, vector
        FROM code_snippets
        """
        cursor.execute(sql)
        results = cursor.fetchall()

    snippets = []
    vectors = []
    
    # Parse the results and calculate cosine similarity
    for result in results:
        vector = np.array(json.loads(result[6]))  # Convert JSON string back to a NumPy array
        vectors.append((result, vector))
    
    similarities = cosine_similarity([query_vector], [v[1] for v in vectors]).flatten()

    # Sort by similarity and pick the top_k results
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    for index in top_indices:
        result = vectors[index][0]
        snippets.append({
            "file_path": result[0],
            "function_name": result[1],
            "type": result[2],
            "start_line": result[3],
            "end_line": result[4],
            "code": result[5],
            "similarity": similarities[index]
        })

    return snippets

async def response (index, query):
    query_engine = index.as_query_engine()
    response = query_engine.query(query)
    return response