#!/bin/bash

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
pip install -r requirements.txt

# Print success message
echo "Virtual environment setup complete!"
echo "To activate the virtual environment, run: source venv/bin/activate" 