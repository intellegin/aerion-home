#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# This script prepares the environment for a Vercel deployment.
# It swaps the full requirements.txt (for local dev) with the
# minimal requirements-vercel.txt (for deployment).

echo "Build script started..."

# Check if both requirements files exist
if [ -f "requirements.txt" ] && [ -f "requirements-vercel.txt" ]; then
  echo "Found both requirements files. Swapping them for Vercel deployment."
  # Remove the original requirements.txt
  rm requirements.txt
  # Rename requirements-vercel.txt to requirements.txt so Vercel's build process picks it up
  mv requirements-vercel.txt requirements.txt
else
  echo "Warning: Could not find one or both requirements files. Proceeding with default build."
fi

# Now, Vercel's default build process will run, and it will execute
# pip install -r requirements.txt, which now contains our minimal set of packages.
echo "Build script finished. Vercel will now install dependencies." 