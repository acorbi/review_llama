import os
import requests
import time
from datetime import datetime, timedelta
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

# Authentication is defined via github.Auth
# using an access token
auth = Auth.Token(GITHUB_PERSONAL_ACCESS_TOKEN)
# GitHub API setup
g = Github(auth=auth)

last_check_time = datetime.now().astimezone(pytz.utc)

def log_action(func_name, *args, **kwargs):
    """Log function calls with timestamp."""

    if not LOG_FILE:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] Called {func_name} with args: {args}, kwargs: {kwargs}\n")

def get_new_pull_requests():
    """Get new pull requests from all repositories since the last check."""
    log_action('get_new_pull_requests')
    new_pulls = []
    
    # Get all repositories the authenticated user has access to
    for repo in g.get_user().get_repos():

        log_action('found_repo', repo=repo.name)
        pulls = repo.get_pulls(state='open', sort='created', direction='desc')
        for pull in pulls:
            is_new_pr = pull.created_at.astimezone(pytz.utc) > last_check_time
            if is_new_pr:
                log_action('found_pull_requests', pull=pull.number, created_at= (pull.created_at))
                new_pulls.append(pull)
    
    return new_pulls

def has_label(pull, label):
    """Check if the pull request has a specific label."""
    log_action('has_label', pull=pull.number, label=label)
    labels = pull.get_labels()
    log_action('labels_found', labels=labels, count=labels.totalCount)
    for l in labels:
        if l.name == label:
            return True
    return False

def get_diff(pull):
    """Get the diff of a pull request."""
    log_action('get_diff', pull=pull.number, diff_url=pull.diff_url)
    headers = {'Authorization': f'token {GITHUB_PERSONAL_ACCESS_TOKEN}'}
    response = requests.get(pull.diff_url, headers=headers)
    diff = response.text
    log_action('diff_found', diff=diff)
    return diff

def send_to_ollama(diff):
    """Send the diff to the Ollama endpoint."""
    log_action('send_to_ollama', diff_length=len(diff))
    headers = {'Content-Type': 'application/json'}
    data = {
        'model': 'llama3.1:8b',
        'stream': False,
        'prompt': f'Review the following diff and provide a concise summary (max 100 words) of possible bugs introduced, whether the code complies with standard coding practices, and suggest improvements. Use natural, not too technical language. focus on the code, not the language.Omit the introductory text "here is the summary" and just provide the summary:\n\n{diff}'
    }
    response = requests.post(OLLAMA_ENDPOINT, headers=headers, json=data)
    log_action('ollama_response', response=response.json()['response'])
    return response.json()['response']

def post_comment(pull, summary):
    """Post a comment on the pull request."""
    log_action('post_comment', pull=pull.number)
    comment = f"""
{summary}
"""
    pull.create_review(body=comment, event='REQUEST_CHANGES')
def main():
    log_action('main')
    
    while True:
        new_pulls = get_new_pull_requests()
        for pull in new_pulls:
            if has_label(pull, LABEL):
                diff = get_diff(pull)
                summary = send_to_ollama(diff)
                post_comment(pull, summary)
        time.sleep(POLLING_FREQ_MINUTES * 60) 

if __name__ == '__main__':
    main()