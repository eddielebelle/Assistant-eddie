# Guide: Uploading Eddie to GitHub

Follow these steps to upload your Eddie assistant to GitHub as a public repository.

## Prerequisites

1. A GitHub account (create one at https://github.com if needed)
2. Git installed on your system
3. Terminal access to your Eddie directory

## Step-by-Step Instructions

### Step 1: Initialize Git Repository

Open your terminal and navigate to the Eddie directory, then initialize git:

```bash
cd /path/to/Eddie
git init
```

### Step 2: Configure Git (First Time Only)

If you haven't configured git before on this machine:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Step 3: Add All Files

Add all files to the staging area:

```bash
git add .
```

Check what will be committed:

```bash
git status
```

You should see all your files listed in green, except those in `.gitignore`.

### Step 4: Create Initial Commit

```bash
git commit -m "Initial commit: Eddie privacy-first voice assistant

- Voice recognition using Whisper
- Natural language processing with T5
- MQTT-based smart home integration
- Spotify music control
- Privacy-focused local processing"
```

### Step 5: Create GitHub Repository

1. Go to https://github.com
2. Click the **"+"** icon in the top right
3. Select **"New repository"**
4. Fill in the details:
   - **Repository name:** `eddie` (or your preferred name)
   - **Description:** "Privacy-first local voice assistant - an open-source alternative to Alexa"
   - **Visibility:** Select **Public**
   - **DO NOT** initialize with README (you already have one)
   - **DO NOT** add .gitignore (you already have one)
   - **License:** Select "MIT License" if you want, or skip (you have one already)
5. Click **"Create repository"**

### Step 6: Link Local Repository to GitHub

GitHub will show you commands. Use the "push an existing repository" section:

```bash
git remote add origin https://github.com/YOUR_USERNAME/eddie.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

### Step 7: Authenticate

When prompted, enter your GitHub credentials. You may need to use a Personal Access Token instead of a password:

**To create a token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name like "Eddie Upload"
4. Select scope: **repo** (full control of private repositories)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)
7. Use this token as your password when pushing

### Step 8: Verify Upload

Visit `https://github.com/YOUR_USERNAME/eddie` to see your repository live!

## Optional: Add Topics and Polish

On your GitHub repository page:

1. Click the gear icon next to "About"
2. Add topics: `voice-assistant`, `privacy`, `local-ai`, `mqtt`, `whisper`, `nlp`, `smart-home`
3. Add website URL if you have one
4. Save changes

## Future Updates

When you make changes to Eddie:

```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "Add feature: description of what you changed"

# Push to GitHub
git push
```

## Troubleshooting

### Large Files Error

If you get errors about large files (models, etc.), they should already be in `.gitignore`. If not:

```bash
# Remove from git tracking but keep locally
git rm --cached path/to/large/file

# Add to .gitignore
echo "path/to/large/file" >> .gitignore

# Commit the change
git add .gitignore
git commit -m "Update .gitignore for large files"
```

### Authentication Issues

If using HTTPS fails, try SSH:

1. Generate SSH key: https://docs.github.com/en/authentication/connecting-to-github-with-ssh
2. Change remote URL:
```bash
git remote set-url origin git@github.com:YOUR_USERNAME/eddie.git
```

### Push Rejected

If the push is rejected:

```bash
# Pull first (if you made changes on GitHub)
git pull origin main --rebase

# Then push
git push
```

## What's Included in Your Repository

✅ Source code (all .py files)
✅ Configuration templates (.env.example)
✅ Dependencies (requirements.txt)
✅ Documentation (README.md)
✅ License (LICENSE)
✅ Git configuration (.gitignore)

❌ Your credentials (.env) - Protected by .gitignore
❌ Large model files - Protected by .gitignore
❌ Cache files - Protected by .gitignore
❌ Personal data - Protected by .gitignore

## Next Steps

After uploading:

1. ⭐ Star your own repository
2. 📝 Consider adding a CONTRIBUTING.md if you want contributions
3. 🏷️ Create a release tag for v1.0.0
4. 📢 Share with the community
5. 💬 Enable Discussions for Q&A

Congratulations! Eddie is now open source! 🎉
