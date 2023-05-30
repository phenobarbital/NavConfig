from time import sleep
from elasticsearch import Elasticsearch
from navconfig.logging import logger

## set a new logger name
logger.setName('config.example')
# verbose debugging:
logger.verbose('This is a verbose message')

# Give Elasticsearch some time to index the new log entry
sleep(5)

# Initialize the Elasticsearch client
es = Elasticsearch(
    ['http://localhost:9200'],
    basic_auth=('elastic', '12345678')
)

# Define the search query
search_query = {
    "match": {
        "message": "This is a verbose message"
    }
}

# Perform the search
res = es.search(index="logstash-*", query=search_query)


# Extract the total number of hits
total_hits = res['hits']['total']['value']

# If the log entry was found in Elasticsearch
if total_hits > 0:
    logger.verbose("Found the log entry in Elasticsearch!")
else:
    logger.verbose("Could not find the log entry in Elasticsearch.")

# Print out the first log entry (if any were found)
if total_hits > 0:
    print(res['hits']['hits'][0]['_source'])
