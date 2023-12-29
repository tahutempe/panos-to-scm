#token_utils.py

import requests
import json
import time
import os
import logging
from requests.exceptions import RequestException

def obtain_api_token(client_id, client_secret, tsg_id, token_file, force_refresh=False):
    """
    Obtain and return the API token. If force_refresh is False and a valid token is cached, 
    return the cached token. Otherwise, request a new token and cache it.
    """
    if not force_refresh and os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                token_data = json.load(f)

            if time.time() < token_data.get("expires_at", 0):
                logging.info("Returning cached token")
                return token_data.get("access_token")
        except json.JSONDecodeError:
            logging.warning("Token file is empty or invalid JSON. Fetching new token.")
            pass

    logging.info("Fetching new Token because it's expired or force_refresh is set")
    print("Fetching new Token because it's expired or force_refresh is set")
    start_time = time.time()

    url = 'https://auth.apps.paloaltonetworks.com/oauth2/access_token'
    payload = {'grant_type': 'client_credentials', 'scope': f'tsg_id:{tsg_id}'}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    response = requests.post(url, data=payload, headers=headers, auth=(client_id, client_secret))

    if response.status_code == 200:
        data = response.json()
        token = data["access_token"]
        expires_in = data["expires_in"]
        elapsed_time = time.time() - start_time
        logging.info(f"New token fetched successfully in {elapsed_time:.2f} seconds")

        token_data = {
            "access_token": token,
            "expires_at": time.time() + expires_in - 180  # Subtract 180 seconds to account for potential delays
        }

        with open(token_file, "w") as f:
            json.dump(token_data, f)

        return token
    else:
        error_msg = f"Error fetching token: {response.status_code} {response.reason}"
        logging.error(error_msg)
        raise RequestException(error_msg)
