#!/usr/bin/env python3
"""
Development environment setup script.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, check=True):
    """Run a shell command and handle errors."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error output: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def setup_environment():
    """Set up development environment."""
    print("🚀 Setting up SNMP Monitoring development environment...")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: You're not in a virtual environment!")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Please activate a virtual environment and try again.")
            sys.exit(1)
    
    # Install dependencies
    print("\n📦 Installing dependencies...")
    run_command("pip install -r requirements-dev.txt")
    
    # Create directories
    print("\n📁 Creating necessary directories...")
    directories = [
        'logs',
        'media/avatars',
        'static_files',
        'backup',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Copy environment file
    print("\n🔧 Setting up environment configuration...")
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            shutil.copy('.env.example', '.env')
            print("Created .env file from .env.example")
            print("⚠️  Please edit .env file with your configuration!")
        else:
            print("⚠️  .env.example not found. Please create .env manually.")
    else:
        print(".env file already exists")
    
    # Run migrations
    print("\n🗄️  Setting up database...")
    run_command("python manage.py makemigrations")
    run_command("python manage.py migrate")
    
    # Create superuser (optional)
    print("\n👤 Create superuser account...")
    response = input("Create superuser account? (y/N): ")
    if response.lower() == 'y':
        run_command("python manage.py createsuperuser", check=False)
    
    # Collect static files
    print("\n📦 Collecting static files...")
    run_command("python manage.py collectstatic --noinput")
    
    # Run tests
    print("\n🧪 Running tests...")
    response = input("Run tests? (y/N): ")
    if response.lower() == 'y':
        run_command("python manage.py test", check=False)
    
    print("\n✅ Development environment setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your database and Redis configuration")
    print("2. Start Redis server: redis-server")
    print("3. Start Celery worker: celery -A config worker -l info")
    print("4. Start Celery beat: celery -A config beat -l info")
    print("5. Run development server: python manage.py runserver")
    print("\n🎉 Happy coding!")

def install_pre_commit_hooks():
    """Install pre-commit hooks for code quality."""
    print("\n🔗 Installing pre-commit hooks...")
    
    # Install pre-commit if not already installed
    run_command("pip install pre-commit", check=False)
    
    # Create pre-commit config
    pre_commit_config = """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203,W503]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.1
    hooks:
      - id: mypy
        additional_dependencies: [django-stubs]
"""
    
    with open('.pre-commit-config.yaml', 'w') as f:
        f.write(pre_commit_config.strip())
    
    # Install the git hook scripts
    run_command("pre-commit install")
    print("Pre-commit hooks installed!")

if __name__ == "__main__":
    try:
        setup_environment()
        
        # Ask about pre-commit hooks
        response = input("\nInstall pre-commit hooks for code quality? (y/N): ")
        if response.lower() == 'y':
            install_pre_commit_hooks()
            
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)