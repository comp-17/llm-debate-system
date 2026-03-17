#!/bin/bash
# COPY-PASTE COMMANDS FOR GITHUB SUBMISSION
# Run these in order - deadline TONIGHT!

# ============================================================================
# STEP 1: Prepare directory (run from local machine if needed)
# ============================================================================

cd /mnt/user-data/outputs/llm-debate-system-fixed

# Verify you're in the right place
pwd
# Should show: .../llm-debate-system-fixed

# ============================================================================
# STEP 2: Prepare README
# ============================================================================

# Option A: Use the GitHub-ready README we created
cp README_GITHUB.md README.md

# Option B: Or use the comprehensive one
# cp README_COMPREHENSIVE.md README.md

# ============================================================================
# STEP 3: Initialize git
# ============================================================================

git init
git config user.name "Your Name"
git config user.email "your.email@university.edu"

# ============================================================================
# STEP 4: Add all files
# ============================================================================

git add .

# ============================================================================
# STEP 5: Commit
# ============================================================================

git commit -m "Multi-agent LLM debate system with 4-phase protocol"

# ============================================================================
# STEP 6: Add remote (REPLACE USERNAME)
# ============================================================================

# First, create empty repo on GitHub at https://github.com/new
# Get the HTTPS URL from the new repo page
# It looks like: https://github.com/YOUR_USERNAME/llm-debate-system.git

# PASTE THIS LINE (after replacing with your actual URL):
git remote add origin https://github.com/YOUR_USERNAME/llm-debate-system.git

# ============================================================================
# STEP 7: Push to GitHub
# ============================================================================

git branch -M main
git push -u origin main

# ============================================================================
# STEP 8: Verify
# ============================================================================

# Check that files are on GitHub (open in browser)
# https://github.com/YOUR_USERNAME/llm-debate-system

# You should see:
# - README.md (visible)
# - GITHUB_BLOG_POST.md (visible)
# - src/ folder
# - config.yaml
# - data/four_phase_results/

# ============================================================================
# STEP 9: SUBMIT TO COURSE PORTAL
# ============================================================================

# Go to course portal and submit this link:
# https://github.com/YOUR_USERNAME/llm-debate-system

# In notes, write:
# Multi-Agent LLM Debate System
# All components complete - see GITHUB_BLOG_POST.md for full report

# ============================================================================
# DONE!
# ============================================================================

echo "✓ Submission complete!"
echo "✓ Check your GitHub repository"
echo "✓ Submit the link to course portal"
echo "✓ Due tonight at 12:00 AM"
