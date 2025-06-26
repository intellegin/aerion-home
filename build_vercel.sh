#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# This script prepares the environment for a Vercel deployment.
# It swaps the full requirements.txt (for local dev) with the
# minimal requirements-vercel.txt (for deployment).

echo "Build script started..."

# Check if both requirements files exist
if [ -f "requirements.txt" ] && [ -f "requirements-vercel.txt" ]; then
  echo "Found both requirements files. Swapping for Vercel deployment."
  # Remove the original requirements.txt
  rm requirements.txt
  # Rename requirements-vercel.txt to requirements.txt so Vercel's build process picks it up
  mv requirements-vercel.txt requirements.txt
else
  echo "Warning: Could not find one or both requirements files. Proceeding with default build."
fi

# Vercel's build process will execute this script, and then the installCommand in vercel.json
# will run pip install. We can't see the size until after that happens.
# The installCommand in vercel.json is the right place for this.

echo "Build script finished. Vercel will now install dependencies." 