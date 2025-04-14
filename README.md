# Review Llama :llama: 

A python script which fetches a diff from a PR, sends it to an Ollama endpoint asking for a concise review which is then posted on the pull request as a review comment.

The script only picks newly created pull-requests that are tagged with a specific label. Looks into all the repositories the user (authenticated by the token) has access to.

# Configuration

The behavior of the script can be configured with the environmental variables:

1. `GITHUB_PERSONAL_ACCESS_TOKEN`: Your personal [GitHub access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) to interact with the GitHub API
2. `OLLAMA_ENDPOINT` (optional): Full path to the [completion generation endpoint](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion) on an Ollama instance (e.g https://SERVER:PORT/api/generate). Defaults to localhost.
3. `LABEL` (optional): Specify a label to let the script select one or several pull requests to review. Defaults to "review-llama"
4. `POLLING_FREQ_MINUTES` (optional): The frequency with which the script checks for new pull requests to review, in minutes. Defaults to 10.
5. `LOG_FILE` (optional): The file in which to store logs. Logging is disabled if not set


## Dependencies

- pyGithub
- python-requests
- pytz

# Examples on test Pull requests

https://github.com/open-steps/website_v3/pull/5 - Typo introduced
https://github.com/open-steps/website_v3/pull/6 - Bad indentation introduced
https://github.com/acorbi/sovereign/pull/1 - Bad practices and bugs
