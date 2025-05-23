import os
import time
from datetime import datetime
import requests
from github import Github
from github import Auth
import pytz

utc=pytz.UTC

# Configuration
GITHUB_PERSONAL_ACCESS_TOKEN = os.environ['GITHUB_PERSONAL_ACCESS_TOKEN']
OLLAMA_ENDPOINT = os.environ.get('OLLAMA_ENDPOINT', "http://localhost:11434/api/generate")
LABEL = os.environ.get('LABEL', 'review-llama')
POLLING_FREQ_MINUTES = int(os.environ.get('POLLING_FREQ_MINUTES', 10))
LOG_FILE = os.environ.get('LOG_FILE', None)

# Store reviewed PRs to avoid duplicate reviews
reviewed_prs = set()

# Authentication is defined via github.Auth
# using an access token
auth = Auth.Token(GITHUB_PERSONAL_ACCESS_TOKEN)
# GitHub API setup
g = Github(auth=auth)

last_check_time = datetime.now().astimezone(pytz.utc)

def log(msg):
    """Log function calls with timestamp."""

    if not LOG_FILE:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_new_pull_requests():
    """Get new pull requests from all repositories since the last check which have not been reviewed yet."""
    log('Fetching new pull requests')
    new_pulls = []
    
    # Get all repositories the authenticated user has access to
    for repo in g.get_user().get_repos():
        log(f'Looking for new pull requests in repository: {repo.name}')

        pulls = repo.get_pulls(state='open', sort='created', direction='desc')
        for pull in pulls:
            is_new_pr = pull.created_at.astimezone(pytz.utc) > last_check_time
            if is_new_pr and pull.number not in reviewed_prs:
                log(f'Found new pull request: {pull.number} created at: {pull.created_at}')
                new_pulls.append(pull)
    
    return new_pulls

def has_label(pull, label):
    """Check if the pull request has a specific label."""
    log(f'Checking if pull request has label: {label}')
    labels = pull.get_labels()
    for l in labels:
        if l.name == label:
            return True
    return False

def get_diff(pull):
    """Get the diff of a pull request."""
    log(f'Getting diff for pull request: {pull.number}')
    files = pull.get_files()
    diff = ''
    for file in files:
        patch = file.patch
        diff += patch + '\n\n'
    log(f'Diff found for pull request: {pull.number}')
    return diff

def extract_llama_input(description):
    """Extract the string following the 🦙 emoji in the description."""
    if '🦙' in description:
        return description.split('🦙', 1)[1].strip()
    return None

# Update the send_to_ollama function to include the additional input
def send_to_ollama(diff, description):
    """Send the diff and description to the Ollama endpoint."""
    log('Sending diff and description to Ollama, awaiting response...')
    llama_input = extract_llama_input(description)
    additional_input = f"\nAdditional Input:\n{llama_input}" if llama_input else ""
    
    headers = {'Content-Type': 'application/json'}
    data = {
        'model': 'llama3.1:8b',
        'stream': False,
        'prompt': f'Review the following pull request diff taking in consideration the description provided on the PR. Provide a concise summary (max 400 words) of possible bugs introduced, whether the code complies with standard coding practices, and suggest improvements. Use natural, not too technical language. Focus on the code, not the strings found within it. Use markdown to format the review. Omit the introductory text "here is the summary" and just provide the summary:\n\nDescription:\n{description}{additional_input}\n\nDiff:\n{diff}'
    }
    response = requests.post(OLLAMA_ENDPOINT, headers=headers, json=data)
    log(f'Ollama response received: {response.json()["response"]}')
    return response.json()['response']

def post_comment(pull, summary):
    """Post a comment on the pull request."""
    log(f'Posting comment on pull request: {pull.number}')
    comment = f"""
{summary}
"""
    pull.create_review(body=comment, event='COMMENT')
    reviewed_prs.add(pull.number)
def update_last_check_time():
    """Update the last check time."""
    global last_check_time
    last_check_time = datetime.now().astimezone(pytz.utc)
    log(f'Updating last check time: {last_check_time}')

def main():
    while True:
        new_pulls = get_new_pull_requests()
        update_last_check_time()
        for pull in new_pulls:
            if has_label(pull, LABEL):
                diff = get_diff(pull)
                description = pull.body or "No description provided."
                summary = send_to_ollama(diff, description)
                post_comment(pull, summary)
        time.sleep(POLLING_FREQ_MINUTES * 60) 

if __name__ == '__main__':
    main()