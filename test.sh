#!/bin/bash

# --- Configuration ---
REQUESTS=100
API_URL="http://mel2090:8000/v1/completions"
# The JSON payload to send with each request
JSON_PAYLOAD='{"model": "mistralai/Mistral-7B-Instruct-v0.2", "prompt": "Explain tensor parallelism:", "max_tokens": 200}'
# ---------------------

echo "Starting load test: $REQUESTS inference requests to $API_URL"
echo "Prompt: Explain tensor parallelism:"
echo "---"

# Start a timer for the entire loop
START_TIME=$(date +%s.%N)

# Loop to fire the requests
for i in $(seq 1 $REQUESTS); do
    # curl command with output suppression and status code printing
    # -s: Silent mode (no progress bar)
    # -X POST: Explicitly set the method
    # -H ...: Content-Type header
    # -d ...: The JSON data
    # -o /dev/null: Redirects the server's response to the trash
    # -w "%{http_code}": Writes the HTTP status code
    STATUS_CODE=$(curl -s -X POST "$API_URL" \
                       -H 'Content-Type: application/json' \
                       -d "$JSON_PAYLOAD" \
                       -o /dev/null \
                       -w "%{http_code}")
    
    # Print the status code and request number
    echo "Request $i/$REQUESTS: HTTP $STATUS_CODE"
    
    # Optional: Add a small sleep here if you want to avoid overwhelming the server
    # sleep 0.1 
done

# End the timer and calculate the total duration
END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc -l)

echo "---"
echo "✅ Load test complete!"
echo "Total Requests: $REQUESTS"
printf "Total Duration: %.2f seconds\n" "$DURATION"
printf "Requests Per Second (RPS): %.2f\n" $(echo "$REQUESTS / $DURATION" | bc -l)
