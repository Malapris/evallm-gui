import sys
import os
import importlib.util

# Ensure distutils available on Python 3.12+ without importing setuptools
try:
    import distutils
except ModuleNotFoundError:
    vendored_dir = None
    for p in sys.path:
        candidate = os.path.join(p, 'setuptools', '_distutils')
        if os.path.isdir(candidate):
            vendored_dir = candidate
            break
    if not vendored_dir:
        raise ModuleNotFoundError("Cannot find vendored distutils in any setuptools installation")
    init_file = os.path.join(vendored_dir, '__init__.py')
    spec = importlib.util.spec_from_file_location("distutils", init_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules['distutils'] = module
    distutils = module

from pathlib import Path
import json
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import sqlite3
import ollama
from datetime import datetime
import logging

# Configuration des chemins
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TESTS_DIR = BASE_DIR / "_tests"
RESULTS_DIR = STATIC_DIR / "results"
DB_FILE = BASE_DIR / "evallm.db"

# Création des dossiers nécessaires
def create_directories():
    """Crée les répertoires nécessaires s'ils n'existent pas."""
    directories = [
        TESTS_DIR,
        STATIC_DIR,
        STATIC_DIR / "js",
        STATIC_DIR / "css",
        STATIC_DIR / "img",
        RESULTS_DIR
    ]
    for directory in directories:
        directory.mkdir(exist_ok=True)
        logger.info(f"Répertoire vérifié/créé: {directory}")

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("evallm-gui")

# Création de l'application FastAPI
app = FastAPI(
    title="evallm GUI",
    description="Interface graphique pour l'évaluation des modèles de langage",
    version="1.0.0"
)

# Middleware pour la gestion des erreurs
@app.middleware("http")
async def add_error_handling(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Erreur non gérée: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Une erreur interne est survenue"}
        )

# Modèles de données
class TestConfig(BaseModel):
    models: List[str]
    system_prompts: Dict[str, str]
    user_prompts: Dict[str, str]
    contexts: Dict[str, str]
    seeds: List[int]
    temperatures: List[float]
    nom_test: str = "test_sans_nom"
    commentaire: str = ""
    resultats: List[str] = []

class TestResult(BaseModel):
    id: int
    config: TestConfig
    results: List[Dict]
    timestamp: str
    system_info: Dict

# Initialisation de la base de données
def init_db():
    """Initialise la base de données SQLite."""
    try:
        if DB_FILE.exists():
            logger.info("Base de données existante détectée, suppression...")
            DB_FILE.unlink()
        
        conn = sqlite3.connect(str(DB_FILE))
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS test_results
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             config TEXT NOT NULL,
             results TEXT NOT NULL,
             timestamp TEXT NOT NULL,
             system_info TEXT NOT NULL)
        ''')
        conn.commit()
        conn.close()
        logger.info("Base de données initialisée avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
        raise

# Routes API
@app.get("/api/tests")
async def get_tests():
    """Récupère la liste des tests disponibles."""
    try:
        tests = []
        for test_file in TESTS_DIR.glob("*.json"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    test_data = json.load(f)
                    tests.append({
                        "name": test_file.stem,
                        "description": test_data.get("description", ""),
                        "config": test_data,
                        "last_modified": datetime.fromtimestamp(test_file.stat().st_mtime).isoformat()
                    })
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier {test_file}: {str(e)}")
                continue
        return {"tests": tests}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/models")
async def get_models():
    """Récupère la liste des modèles disponibles via Ollama."""
    try:
        models = ollama.list()
        model_names = [model.model for model in models.models]
        model_names.sort()  # Tri alphabétique
        return {"models": model_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def clean_for_json(obj, path=""):
    """Nettoie un objet pour le rendre sérialisable en JSON."""
    try:
        # Détection d'Undefined et autres types non-sérialisables
        if obj is None or obj == "undefined" or obj == "null":
            return None
            
        # Vérifier le nom de classe si possible
        try:
            class_name = obj.__class__.__name__ if hasattr(obj, "__class__") else type(obj).__name__
            if class_name == "Undefined":
                logger.warning(f"Objet de type Undefined détecté à {path}")
                return None
        except Exception:
            pass
        
        # Types de base
        if isinstance(obj, (str, int, float, bool)):
            return obj
            
        # Dates
        if isinstance(obj, datetime):
            return obj.isoformat()
            
        # Dictionnaires
        if isinstance(obj, dict):
            cleaned_dict = {}
            for k, v in obj.items():
                if v is None or (hasattr(v, "__class__") and v.__class__.__name__ == "Undefined"):
                    continue
                cleaned_dict[k] = clean_for_json(v, f"{path}.{k}" if path else k)
            return cleaned_dict
                   
        # Listes et tuples
        if isinstance(obj, (list, tuple)):
            cleaned_list = []
            for i, item in enumerate(obj):
                if item is None or (hasattr(item, "__class__") and item.__class__.__name__ == "Undefined"):
                    continue
                cleaned_list.append(clean_for_json(item, f"{path}[{i}]" if path else f"[{i}]"))
            return cleaned_list
                   
        # Objets avec différentes méthodes de conversion
        if hasattr(obj, 'model_dump'):
            try:
                return clean_for_json(obj.model_dump(), path)
            except Exception as e:
                logger.warning(f"Erreur lors de l'appel à model_dump à {path}: {e}")
                
        if hasattr(obj, 'dict'):
            try:
                return clean_for_json(obj.dict(), path)
            except Exception as e:
                logger.warning(f"Erreur lors de l'appel à dict à {path}: {e}")
                
        if hasattr(obj, '__dict__'):
            try:
                return clean_for_json(obj.__dict__, path)
            except Exception as e:
                logger.warning(f"Erreur lors de l'accès à __dict__ à {path}: {e}")
                
        # Dernier recours : vars() ou str()
        try:
            return clean_for_json(vars(obj), path)
        except Exception:
            try:
                return str(obj)
            except Exception as e:
                logger.warning(f"Impossible de convertir l'objet à {path} en chaîne: {e}")
                return None
            
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage de l'objet à {path}: {str(e)}")
        return None

@app.post("/api/test")
async def run_test(config: TestConfig):
    """Lance un test avec la configuration fournie."""
    try:
        logger.info(f"Configuration reçue: {config.dict()}")
        
        # Création d'un fichier de configuration temporaire
        timestamp_start = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Utilisation du nom_test pour le nom des fichiers
        test_name = config.nom_test
        test_name = "".join(c if c.isalnum() else "_" for c in test_name)
        temp_config_file = RESULTS_DIR / f"test_{test_name}_{timestamp_start}.json"
        temp_config_file.write_text(config.model_dump_json(), encoding='utf-8')
        logger.info(f"Configuration temporaire sauvegardée dans {temp_config_file}")
        
        # Exécution du test
        from evallm import compare_llms, get_system_info, HTML_TEMPLATE
        results = compare_llms(str(temp_config_file))
        
        # Sauvegarde des résultats
        system_info = get_system_info()
        timestamp_end = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Création des fichiers de résultats avec le nom du test
        base_filename = f"test_{test_name}_{timestamp_start}_{timestamp_end}"
        json_file = RESULTS_DIR / f"{base_filename}.json"
        html_file = RESULTS_DIR / f"{base_filename}.html"
        
        logger.info(f"Fichiers de résultats: JSON={json_file}, HTML={html_file}")
        
        # Nettoyage des données pour la sérialisation JSON
        try:
            # Nettoyage des résultats
            cleaned_results = []
            for result in results:
                try:
                    # Extraction des données du résultat de manière sécurisée
                    if hasattr(result, 'model_dump'):
                        result_dict = result.model_dump()
                    elif hasattr(result, 'dict'):
                        result_dict = result.dict()
                    elif hasattr(result, '__dict__'):
                        result_dict = result.__dict__
                    else:
                        result_dict = vars(result)
                        
                    # Nettoyage des valeurs non sérialisables
                    for key, value in result_dict.items():
                        if value is None or value == "undefined":
                            result_dict[key] = None
                        elif isinstance(value, (list, dict)):
                            result_dict[key] = clean_for_json(value)
                    cleaned_results.append(result_dict)
                except Exception as e:
                    logger.warning(f"Erreur lors du nettoyage d'un résultat: {e}", exc_info=True)
                    continue
            
            # Nettoyage des informations système
            system_info_dict = system_info.__dict__ if hasattr(system_info, '__dict__') else vars(system_info)
            cleaned_system_info = clean_for_json(system_info_dict)
            
            # Nettoyage de la configuration
            config_dict = config.model_dump() if hasattr(config, 'model_dump') else config.dict() if hasattr(config, 'dict') else config.__dict__
            cleaned_config = clean_for_json(config_dict)
            
            # Sauvegarde du fichier JSON
            json_data = {
                "config": cleaned_config,
                "results": cleaned_results,
                "system_info": cleaned_system_info,
                "timestamp": datetime.now().isoformat()
            }
            
            # Vérification finale de la sérialisation
            json.dumps(json_data)  # Test de sérialisation
            json_file.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding='utf-8')
            
        except Exception as e:
            logger.error(f"Erreur lors de la sérialisation JSON: {str(e)}")
            # Tentative de sérialisation avec des données minimales
            json_data = {
                "config": {"error": "Erreur de sérialisation"},
                "results": [],
                "system_info": {"error": "Erreur de sérialisation"},
                "timestamp": datetime.now().isoformat()
            }
            json_file.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding='utf-8')
            raise
        
        # Vérifier que le fichier HTML existe
        # Note: Le HTML est généré par evallm.py dans compare_llms()
        if html_file.exists():
            logger.info(f"Rapport HTML trouvé dans {html_file}")
            # Construction du chemin relatif pour l'API
            html_file_path = f"/static/results/{html_file.name}"
        else:
            logger.error(f"Rapport HTML non trouvé dans {html_file}")
            html_file_path = f"/static/results/{json_file.name}"
        
        # Sauvegarde dans la base de données
        conn = sqlite3.connect(str(DB_FILE))
        c = conn.cursor()
        c.execute(
            "INSERT INTO test_results (config, results, timestamp, system_info) VALUES (?, ?, ?, ?)",
            (json.dumps(cleaned_config), json.dumps(cleaned_results), datetime.now().isoformat(), json.dumps(cleaned_system_info))
        )
        test_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Vérifier si le nom du test existe déjà dans _tests
        test_name = config.nom_test
        test_name_sanitized = "".join(c if c.isalnum() else "_" for c in test_name)
        
        # S'assurer que le dossier _tests existe
        TESTS_DIR.mkdir(exist_ok=True)
        logger.info(f"Vérification du dossier _tests: {TESTS_DIR.exists()}")
        
        # Liste des tests existants
        existing_tests = []
        try:
            existing_tests = [test_file.stem for test_file in TESTS_DIR.glob("*.json")]
            logger.info(f"Tests existants trouvés: {len(existing_tests)}")
            logger.info(f"Liste des tests: {existing_tests}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tests existants: {e}")
        
        # Vérifier si le test existe déjà
        if test_name_sanitized in existing_tests:
            logger.info(f"Le test {test_name_sanitized} existe déjà, pas de sauvegarde")
        else:
            try:
                # Si le test a un nom, on utilise directement ce nom
                if test_name and test_name != "test_sans_nom":
                    test_file = TESTS_DIR / f"{test_name_sanitized}.json"
                else:
                    # Sinon on ajoute un timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    test_file = TESTS_DIR / f"{test_name_sanitized}_{timestamp}.json"
                
                logger.info(f"Tentative de sauvegarde du test dans: {test_file}")
                
                # Vérifier que le chemin est valide
                if not TESTS_DIR.exists():
                    logger.error(f"Le dossier _tests n'existe pas: {TESTS_DIR}")
                    TESTS_DIR.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Dossier _tests créé: {TESTS_DIR}")
                
                # Sauvegarder le fichier
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(cleaned_config, indent=2, ensure_ascii=False))
                
                # Vérifier que le fichier a bien été créé
                if test_file.exists():
                    logger.info(f"Test sauvegardé avec succès dans {test_file}")
                else:
                    logger.error(f"Échec de la sauvegarde du test dans {test_file}")
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du test dans _tests: {e}", exc_info=True)
        
        return {"id": test_id, "results": cleaned_results, "result_file": html_file_path}
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results")
async def get_results():
    """Récupère tous les résultats de tests."""
    conn = sqlite3.connect(str(DB_FILE))
    c = conn.cursor()
    c.execute("SELECT * FROM test_results ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "config": json.loads(row[1]),
            "results": json.loads(row[2]),
            "timestamp": row[3],
            "system_info": json.loads(row[4])
        })
    return results

@app.get("/api/result/{test_id}")
async def get_result(test_id: int):
    """Récupère un résultat de test spécifique."""
    conn = sqlite3.connect(str(DB_FILE))
    c = conn.cursor()
    c.execute("SELECT * FROM test_results WHERE id = ?", (test_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return {
        "id": row[0],
        "config": json.loads(row[1]),
        "results": json.loads(row[2]),
        "timestamp": row[3],
        "system_info": json.loads(row[4])
    }

@app.get("/results", response_class=HTMLResponse)
async def results_page():
    """Page de présentation des résultats."""
    try:
        # Récupération de tous les fichiers de résultats HTML
        result_files = sorted(RESULTS_DIR.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Génération de la page HTML
        html = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Résultats des tests</title>
            <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
            <style>
                .result-card {
                    transition: transform 0.2s;
                }
                .result-card:hover {
                    transform: translateY(-2px);
                }
                .model-badge {
                    display: inline-block;
                    background-color: #e8eaf6;
                    color: #3f51b5;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.8em;
                    margin-right: 4px;
                }
                .test-count {
                    display: inline-block;
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.8em;
                }
            </style>
        </head>
        <body class="bg-gray-100 p-8">
            <div class="max-w-4xl mx-auto">
                <div class="flex justify-between items-center mb-8">
                    <h1 class="text-3xl font-bold">Résultats des tests</h1>
                    <a href="/" class="text-blue-500 hover:text-blue-700">
                        Retour à l'interface
                    </a>
                </div>
                <div class="grid grid-cols-1 gap-4">
        """
        
        for result_file in result_files:
            try:
                file_name = result_file.stem
                # Extraction de la date du nom de fichier
                date_parts = file_name.split('_')
                if len(date_parts) >= 3:
                    date_str = f"{date_parts[-2]}_{date_parts[-1]}"
                    try:
                        formatted_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
                    except ValueError:
                        formatted_date = datetime.fromtimestamp(result_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                else:
                    formatted_date = datetime.fromtimestamp(result_file.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                
                json_file = RESULTS_DIR / f"{file_name}.json"
                
                # Lecture des informations du fichier JSON
                models = []
                test_count = 0
                if json_file.exists():
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if 'config' in data and 'models' in data['config']:
                                models = data['config']['models']
                            if 'results' in data:
                                test_count = len(data['results'])
                    except Exception as e:
                        logger.warning(f"Erreur lors de la lecture du fichier JSON {json_file}: {str(e)}")
                
                html += f"""
                    <div class="result-card bg-white rounded-lg shadow p-4">
                        <div class="flex justify-between items-start">
                            <div>
                                <h2 class="text-xl font-semibold">{file_name}</h2>
                                <p class="text-gray-600">{formatted_date}</p>
                                <div class="mt-2">
                                    <span class="test-count">Tests: {test_count}</span>
                                </div>
                                <div class="mt-2">
                                    <span class="text-sm text-gray-500">Modèles:</span>
                                    {" ".join([f'<span class="model-badge">{model}</span>' for model in models])}
                                </div>
                            </div>
                            <div class="space-x-4">
                                <a href="/static/results/{result_file.name}" 
                                   class="text-blue-500 hover:text-blue-700"
                                   target="_blank">
                                    Version HTML
                                </a>
                                <a href="/static/results/{json_file.name}" 
                                   class="text-blue-500 hover:text-blue-700"
                                   target="_blank">
                                    Version JSON
                                </a>
                            </div>
                        </div>
                    </div>
                """
            except Exception as e:
                logger.warning(f"Erreur lors du traitement du fichier {result_file}: {str(e)}")
                continue
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        logger.error(f"Erreur lors de la génération de la page des résultats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Servir les fichiers statiques
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/static/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")

# Page principale
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>evallm GUI</title>
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/vue@3.2.31"></script>
        <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
        <style>
            .loading {
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body class="bg-gray-100">
        <div id="app"></div>
        <script src="/static/js/app.js"></script>
    </body>
    </html>
    """

def main():
    """Point d'entrée principal de l'application."""
    try:
        # Création des répertoires
        create_directories()
        
        # Initialisation de la base de données
        init_db()
        
        # Démarrage du serveur
        logger.info("Démarrage du serveur FastAPI...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de l'application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()