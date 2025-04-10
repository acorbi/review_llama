import os
import requests
import time
from datetime import datetime, timedelta
from github import Github
from github import Auth
import pytz

utc=pytz.UTC

# Environment variables
GITHUB_PERSONAL_ACCESS_TOKEN = os.environ['GITHUB_PERSONAL_ACCESS_TOKEN']
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
LABEL = "ai-review"
POLLING_FREQ_MINUTES = 10
LOG_FILE = "review_llama.log"
ENABLED_REPOSITORIES = [""]
REVIEWED_PRS_FILE = "/tmp/reviewed_prs.txt"

# Authentication is defined via github.Auth
# using an access token
auth = Auth.Token(GITHUB_PERSONAL_ACCESS_TOKEN)
# GitHub API setup
g = Github(auth=auth)

review_requested = False

# File to store reviewed PRs

def load_reviewed_prs():
    """Load the list of already reviewed PRs from file."""
    try:
        with open(REVIEWED_PRS_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    except FileNotFoundError:
        return set()

def save_reviewed_pr(pull_number):
    """Save a PR ID to the reviewed PRs file."""
    with open(REVIEWED_PRS_FILE, 'a') as f:
        f.write(f"{pull_number}\n")

def is_pr_reviewed(pull_number):
    """Check if a PR has already been reviewed."""
    reviewed_prs = load_reviewed_prs()
    return str(pull_number) in reviewed_prs

def log_action(func_name, *args, **kwargs):
    """Log function calls with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] Called {func_name} with args: {args}, kwargs: {kwargs}\n")

def get_new_pull_requests():
    """Get new pull requests from all repositories since the last check."""
    log_action('get_new_pull_requests')
    new_pulls = []
    
    # Get all repositories the authenticated user has access to
    for repo in g.get_user().get_repos():
        # Skip if repository is not in enabled list
        if repo.name not in ENABLED_REPOSITORIES:
            continue

        log_action('found_repo', repo=repo.name)
        pulls = repo.get_pulls(state='open', sort='created', direction='desc')
        for pull in pulls:
            if is_pr_reviewed(pull.number):
                continue

            is_new_pr = pull.created_at > utc.localize(datetime.now())
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
    # Log the diff content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    diff_filename = f"diff_pr_{pull.number}_{timestamp.replace(' ', '_').replace(':', '')}.txt"
    with open(diff_filename, 'w') as f:
        f.write(diff)
    return diff

def send_to_ollama(diff):
    """Send the diff to the Ollama endpoint."""
    log_action('send_to_ollama', diff_length=len(diff))
    review_requested = True
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
    save_reviewed_pr(pull.number)
def main():
    log_action('main')
    
    while review_requested is False:
        new_pulls = get_new_pull_requests()
        for pull in new_pulls:
            if has_label(pull, LABEL):
                diff = get_diff(pull)
                summary = send_to_ollama(diff)
                post_comment(pull, summary)
        time.sleep(POLLING_FREQ_MINUTES * 60) 

if __name__ == '__main__':
    main()