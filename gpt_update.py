import os
import openai
from github import Github
from git import Repo
import tempfile
import shutil

# Initialize OpenAI and GitHub clients
openai.api_key = os.getenv('OPENAI_API_KEY')
github_token = os.getenv('GHTOKEN')  # Ensure correct environment variable
repo_name = os.getenv('REPO_NAME')
issue_number = int(os.getenv('ISSUE_NUMBER'))

g = Github(github_token)
repo = g.get_repo(repo_name)
issue = repo.get_issue(number=issue_number)

# Step 1: Fetch Issue Content
issue_content = issue.body

# Step 2: Generate Code with GPT
system_prompt = "You are an AI assistant that generates code changes based on user requests."

user_prompt = f"""
Issue Description:
{issue_content}

Please provide the filename and the complete code content that needs to be updated. Format your response as follows:

Filename: path/to/filename.py

[Code Content]
"""

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",  # Use "gpt-4" if you have access
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    max_tokens=800,
    temperature=0
)

code_changes = response['choices'][0]['message']['content'].strip()

# Step 3: Apply Code Changes
# Clone the repository to a temporary directory
temp_dir = tempfile.mkdtemp()
cloned_repo = Repo.clone_from(
    repo.clone_url.replace("https://", f"https://{github_token}@"),
    temp_dir,
    branch='main'
)

# Create a new branch
new_branch_name = f'issue-{issue_number}-gpt-update'
cloned_repo.git.checkout('-b', new_branch_name)

# Apply code changes
try:
    # Parse the GPT response to extract filename and code content
    if code_changes.startswith("Filename:"):
        filename_line, code_content = code_changes.split('\n', 1)
        filename = filename_line.replace('Filename:', '').strip()
        file_path = os.path.join(temp_dir, filename)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write the code content to the file
        with open(file_path, 'w') as f:
            f.write(code_content.strip())

        # Step 4: Commit and Push Changes
        cloned_repo.git.add('--all')
        cloned_repo.index.commit(f'GPT update for issue #{issue_number}')
        origin = cloned_repo.remote(name='origin')
        origin.push(new_branch_name)

        # Step 5: Create Pull Request
        pr = repo.create_pull(
            title=f'GPT Update for Issue #{issue_number}',
            body='Automated code changes generated by GPT.',
            head=new_branch_name,
            base='main'
        )

        # Comment on the issue with the PR link
        issue.create_comment(f'A pull request has been created: {pr.html_url}')
    else:
        # If the response does not start with 'Filename:', handle the error
        issue.create_comment('GPT did not provide the expected output format.')
except Exception as e:
    # Log the exception and comment on the issue
    issue.create_comment(f'An error occurred while processing the issue: {e}')
finally:
    # Clean up temporary directory
    shutil.rmtree(temp_dir)
