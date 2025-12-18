import os

def create_structure():
    project_name = "CattleCounter_MLOps"
    print(f"🏗️ Initializing '{project_name}' Production Repository...")
    
    structure = {
        "api": ["routers", "schemas"],      # FastAPI Backend
        "worker": [],                       # Background Processor
        "core": [],                         # Shared Config & Azure Utils
        "ml_engine": [],                    # The Logic imported from Research
        "k8s": [],                          # Future Kubernetes manifests
        "tests": []
    }

    if not os.path.exists(project_name):
        os.makedirs(project_name)

    for main_folder, subfolders in structure.items():
        path = os.path.join(project_name, main_folder)
        os.makedirs(path, exist_ok=True)
        # Init file for package structure
        with open(os.path.join(path, "__init__.py"), 'w') as f: pass
        
        for sub in subfolders:
            sub_path = os.path.join(path, sub)
            os.makedirs(sub_path, exist_ok=True)
            with open(os.path.join(sub_path, "__init__.py"), 'w') as f: pass

    # Root files
    files = [".gitignore", "requirements.txt", "docker-compose.yml", "README.md", "Dockerfile.api", "Dockerfile.worker"]
    for f in files:
        with open(os.path.join(project_name, f), 'w') as fp: pass

    print("✅ Structure ready. Let's code!")

if __name__ == "__main__":
    create_structure()
