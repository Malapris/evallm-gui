import ollama
import json
import json_repair
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.logging import RichHandler
from pydantic import BaseModel
import logging
import platform
import psutil
import GPUtil
import sys
import webbrowser
import shutil
import requests
from jinja2 import Environment, FileSystemLoader

# Constantes
DEFAULT_OLLAMA_URL = 'http://localhost:11434'
OLLAMA_API_URL = f"{DEFAULT_OLLAMA_URL}/api/version"
EVALLM_VERSION = "4.0.1"
GB_DIVISOR = 1024**3

size = shutil.get_terminal_size()

# Configuration du logging avec rich
console = Console(
    width=size.columns,
    force_terminal=True,
    force_interactive=True,
    color_system="auto",
    legacy_windows=False
)

# Configuration de l'encodage pour Windows
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(
        rich_tracebacks=True,
        console=console,
        markup=True,
        show_time=True,
        show_path=False
    )]
)
logger = logging.getLogger("evallm")

# Configuration de la barre de progression
progress_columns = [
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(bar_width=None),
    TaskProgressColumn(),
    TimeRemainingColumn(),
]

@dataclass
class SystemInfo:
    os: str
    os_version: str
    python_version: str
    ollama_version: str
    evallm_version: str
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    gpu: Optional[List[Dict[str, Any]]]
    hostname: str

class ModelConfig(BaseModel):
    models: List[str]
    system_prompts: Dict[str, str]
    user_prompts: Dict[str, str]
    contexts: Dict[str, str]
    seeds: List[int] = [42]
    temperatures: List[float] = [0.7]
    commentaire: str = ""
    resultats: List[str] = []
    nom_test: str = ""

    def to_dict(self) -> Dict:
        """Convertit la configuration en dictionnaire (compatible Python 3.11)."""
        return {
            "models": self.models,
            "system_prompts": self.system_prompts,
            "user_prompts": self.user_prompts,
            "contexts": self.contexts,
            "seeds": self.seeds,
            "temperatures": self.temperatures,
            "commentaire": self.commentaire,
            "resultats": self.resultats,
            "nom_test": self.nom_test
        }

class Result(BaseModel):
    model: str
    system_prompt: str
    system_prompt_id: str
    user_prompt: str
    user_prompt_id: str
    context: str
    context_id: str
    seed: int
    temperature: float
    response: str
    response_time: float
    commentaire: str
    Resultats: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """Convertit le résultat en dictionnaire (compatible Python 3.11)."""
        return {
            "model": self.model,
            "system_prompt": self.system_prompt,
            "system_prompt_id": self.system_prompt_id,
            "user_prompt": self.user_prompt,
            "user_prompt_id": self.user_prompt_id,
            "context": self.context,
            "context_id": self.context_id,
            "seed": self.seed,
            "temperature": self.temperature,
            "response": self.response,
            "response_time": self.response_time,
            "commentaire": self.commentaire,
            "Resultats": self.Resultats
        }

# Template HTML intégré
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comparaison de LLM avec Ollama</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; background-color: #f8f9fa; }
        h1 { color: #1a237e; text-align: center; margin-bottom: 30px; }
        h2 { color: #283593; margin-top: 40px; border-bottom: 1px solid #c5cae9; padding-bottom: 10px; }
        .results-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.12); table-layout: fixed; }
        .results-table th, .results-table td { border: 1px solid #e0e0e0; padding: 12px; text-align: left; vertical-align: top; }
        .results-table th { background-color: #e8eaf6; font-weight: bold; color: #1a237e; }
        .results-table tr:nth-child(even) { background-color: #f5f5f5; }
        .results-table tr:hover { background-color: #e8eaf6; }
        .model-header { background-color: #3f51b5; color: white; }
        .response { max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-family: monospace; }
        .response-content { padding: 10px; background-color: #f8f9fa; border-radius: 4px; cursor: pointer; }
        .response-content:hover { background-color: #e8eaf6; }
        .response-pre { 
            display: none; 
            position: fixed; 
            top: 50%; 
            left: 50%; 
            transform: translate(-50%, -50%);
            width: 80%; 
            max-height: 80vh;
            background-color: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow-y: auto; 
            z-index: 1000; 
        }
        .response-pre pre { 
            margin: 0; 
            white-space: pre-wrap; 
            font-family: monospace;
            font-size: 14px;
            line-height: 1.4;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            max-height: none;
            overflow: visible;
        }
        .response-pre .think-section { color: #666; font-style: italic; }
        .think-tag { color: #5c6bc0; font-weight: bold; }
        .response-text { white-space: pre-wrap; }
        .overlay { 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background-color: rgba(0,0,0,0.5); 
            z-index: 999; 
        }
        .close-button { 
            position: absolute; 
            top: 10px; 
            right: 10px; 
            cursor: pointer; 
            font-size: 24px; 
            color: #666;
            background: none;
            border: none;
            padding: 5px;
        }
        .close-button:hover {
            color: #000;
        }
        .metadata { background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .summary-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .summary-table th, .summary-table td { border: 1px solid #e0e0e0; padding: 12px; text-align: center; }
        .summary-table th { background-color: #3f51b5; color: white; font-weight: bold; }
        .summary-table tr:nth-child(even) { background-color: #f5f5f5; }
        .summary-table tr:hover { background-color: #e8eaf6; }
        .footer { text-align: center; margin-top: 50px; font-size: 0.8em; color: #5c6bc0; }
        .temp-badge { display: inline-block; background-color: #5c6bc0; color: white; padding: 2px 6px; 
                      border-radius: 3px; font-size: 0.8em; margin-left: 8px; }
        .json-link { 
            display: block; 
            text-align: right; 
            margin: 10px 0; 
            color: #3f51b5; 
            text-decoration: none;
            padding: 8px 15px;
            background-color: #e8eaf6;
            border-radius: 4px;
            transition: background-color 0.3s;
        }
        .json-link:hover { 
            text-decoration: none;
            background-color: #c5cae9;
        }
        .models-list { background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0; 
                      box-shadow: 0 1px 3px rgba(0,0,0,0.12); font-family: monospace; }
        .input-data { background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .input-content { white-space: pre-wrap; background-color: #f5f5f5; padding: 10px; border-left: 4px solid #3f51b5; margin: 10px 0; }
        .commentaire { background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.12); font-style: italic; }
        .highlighted-response { text-decoration: underline; text-decoration-color: green; text-decoration-thickness: 2px; }
        .system-info { background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .system-info h3 { color: #1a237e; margin-top: 0; }
        .system-info table { margin: 10px 0; width: 100%; }
        .system-info td:first-child { font-weight: bold; width: 200px; }
        .identical { color: #666; font-style: italic; }
        .think-section { color: #666; font-style: italic; }
        think { display: block; color: #666; font-style: italic; margin: 5px 0; }
        @media screen and (max-width: 768px) {
            .results-table { display: block; overflow-x: auto; }
            .summary-table { display: block; overflow-x: auto; }
        }
        .header-info {
            text-align: center;
            margin-bottom: 20px;
            color: #5c6bc0;
            font-size: 1.2em;
        }
    </style>
    <script>
        function showResponse(response, event) {
            event.preventDefault();
            event.stopPropagation();
            
            // Création de l'overlay s'il n'existe pas
            if (!document.querySelector('.overlay')) {
                const overlay = document.createElement('div');
                overlay.className = 'overlay';
                document.body.appendChild(overlay);
            }
            
            // Suppression de l'ancien popup s'il existe
            const oldPopup = document.querySelector('.response-pre');
            if (oldPopup) {
                oldPopup.remove();
            }
            
            const pre = document.createElement('pre');
            try {
                response = JSON.parse('"' + response + '"');
            } catch (e) {
                // Si le décodage échoue, on garde la réponse originale
            }
            
            const escapedResponse = response
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;')
                .replace(/\n/g, '<br>')
                .replace(/\r/g, '');
                
            pre.innerHTML = escapedResponse;
            
            const div = document.createElement('div');
            div.className = 'response-pre';
            div.innerHTML = '<button class="close-button" onclick="closeResponse()">&times;</button>';
            div.appendChild(pre);
            
            document.body.appendChild(div);
            document.querySelector('.overlay').style.display = 'block';
            div.style.display = 'block';
        }
        
        function closeResponse() {
            const popup = document.querySelector('.response-pre');
            const overlay = document.querySelector('.overlay');
            if (popup) {
                popup.remove();
            }
            if (overlay) {
                overlay.style.display = 'none';
            }
        }
        
        // Fermer avec la touche Escape
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeResponse();
            }
        });
        
        // Fermer en cliquant sur l'overlay
        document.addEventListener('click', function(event) {
            if (event.target.classList.contains('overlay')) {
                closeResponse();
            }
        });
    </script>
</head>
<body>
    <div class="overlay"></div>
    <h1>evallm : comparaison de modèles avec ollama</h1>
    <div class="header-info">
        <h2>{{ config.nom_test }} - {{ system_info.hostname }} - {{ system_info.os }} {{ system_info.os_version }} - {{ datetime.now().strftime("%d/%m/%Y %H:%M:%S") }}</h2>
    </div>

    <div class="system-info">
        <h3>Informations du Test</h3>
        <table>
            <tr>
                <td>Nom du test</td>
                <td>{{ config.nom_test }}</td>
            </tr>
            <tr>
                <td>Commentaire</td>
                <td>{{ config.commentaire or "Aucun commentaire" }}</td>
            </tr>
        </table>
        <h3>Informations Système</h3>
        <table>
            <tr>
                <td>Nom de la machine</td>
                <td>{{ system_info.hostname }}</td>
            </tr>
            <tr>
                <td>Système d'exploitation</td>
                <td>{{ system_info.os }} {{ system_info.os_version }}</td>
            </tr>
            <tr>
                <td>Python</td>
                <td>{{ system_info.python_version }}</td>
            </tr>
            <tr>
                <td>Ollama</td>
                <td>{{ system_info.ollama_version }}</td>
            </tr>
            <tr>
                <td>evallm.py</td>
                <td>{{ system_info.evallm_version }}</td>
            </tr>
            <tr>
                <td>CPU</td>
                <td>{{ system_info.cpu.model }} ({{ system_info.cpu.cores }} cœurs, {{ system_info.cpu.threads }} threads)</td>
            </tr>
            <tr>
                <td>Mémoire</td>
                <td>{{ "%.1f"|format(system_info.memory.total_gb) }} GB total, {{ "%.1f"|format(system_info.memory.available_gb) }} GB disponible</td>
            </tr>
            {% if system_info.gpu %}
            <tr>
                <td>GPU</td>
                <td>
                    {% for gpu in system_info.gpu %}
                    {{ gpu.name }} ({{ "%.1f"|format(gpu.memory_total/1024) }} GB VRAM)<br>
                    {% endfor %}
                </td>
            </tr>
            {% endif %}
        </table>
    </div>
    
    <a href="{{ output_file|replace('.html', '.json')|replace('\\', '/') }}" class="json-link">📊 Voir les données au format JSON</a>

    <h2>Synthèse des Performances</h2>
    <table class="summary-table">
        <tr class="model-header">
            <th>Modèle</th>
            <th>Temps moyen (s)</th>
            <th>Temps minimum (s)</th>
            <th>Temps maximum (s)</th>
            <th>Nombre de tokens moyen</th>
        </tr>
        {% for model_temp, times in model_temp_times.items() %}
        <tr>
            <td><a href="#model_{{ model_temp_first_ids[model_temp] }}">{{ model_temp.split(' (')[0] }}</a> <span class="temp-badge">temp={{ model_temp.split('=')[1].split(')')[0] }}</span></td>
            <td>{{ "%.2f"|format(sum(times)/len(times)) }}</td>
            <td>{{ "%.2f"|format(min(times)) }}</td>
            <td>{{ "%.2f"|format(max(times)) }}</td>
            <td>{{ avg_tokens[model_temp] }}</td>
        </tr>
        {% endfor %}
    </table>
    
    <h2>Données d'Entrée</h2>
    <div class="input-data">
        <h3>Prompts Système</h3>
        {% for id, prompt in unique_system_prompts.items() %}
        <p><strong>{{ id }}</strong></p>
        <div class="input-content">{{ prompt }}</div>
        {% endfor %}
        
        <h3>Prompts Utilisateur</h3>
        {% for id, prompt in unique_user_prompts.items() %}
        <p><strong>{{ id }}</strong></p>
        <div class="input-content">{{ prompt }}</div>
        {% endfor %}
        
        <h3>Contextes</h3>
        {% for id, context in unique_contexts.items() %}
        <p><strong>{{ id }}</strong></p>
        <div class="input-content">{{ context }}</div>
        {% endfor %}
    </div>
    
    <h2>Résultats Détaillés</h2>
    {% for (model, sys_id, prompt_id, ctx_id, temp), seeds in grouped_results.items() %}
    {% set model_temp_key = model ~ " (temp=" ~ temp ~ ")" %}
    <h3 id="model_{{ model_temp_first_ids[model_temp_key] }}">Modèle: {{ model }} | Système: {{ sys_id }} | Prompt: {{ prompt_id }} | Contexte: {{ ctx_id }} | Température: {{ temp }}</h3>
    <table class="results-table">
        <tr class="model-header">
            <th>Métrique</th>
            {% for seed in sorted_seeds %}
            <th>Réponse graine {{ seed }}</th>
            {% endfor %}
        </tr>
        <tr>
            <th>Temps (s)</th>
            {% for seed in sorted_seeds %}
            <td>{{ "%.2f"|format(seeds[seed].response_time) }}</td>
            {% endfor %}
        </tr>
        <tr>
            <th>Réponse</th>
            {% for seed in sorted_seeds %}
            <td class="response">
                {% if seeds[seed].response in previous_responses %}
                <div class="response-content identical">(identique)</div>
                {% else %}
                <div class="response-content response-text" onclick="showResponse({{ seeds[seed].response|tojson|replace('"', '&quot;')|replace('\n', '\\n')|replace('\r', '')|replace('\\', '\\\\')|safe }}, event)">
                    {{ seeds[seed].response|replace('<think>', '<span class="think-tag">&lt;think&gt;</span>')|replace('</think>', '<span class="think-tag">&lt;/think&gt;</span>')|safe }}
                </div>
                {% set _ = previous_responses.append(seeds[seed].response) %}
                {% endif %}
            </td>
            {% endfor %}
        </tr>
    </table>
    <br>
    {% endfor %}
    
    <h2>Modèles Disponibles</h2>
    <div class="models-list">
        {{ available_models|tojson }}
    </div>
    
    <div class="footer">
        <p>Généré avec <a href="https://github.com/Malapris/evallm">evallm.py</a> par Francis Malapris</p>
    </div>
</body>
</html>
"""

def get_system_info(ollama_url: str = DEFAULT_OLLAMA_URL) -> SystemInfo:
    """Récupère les informations système détaillées."""
    try:
        # Récupération des informations CPU
        cpu_freq = psutil.cpu_freq()
        cpu_info = {
            "model": platform.processor(),
            "cores": psutil.cpu_count(),
            "threads": psutil.cpu_count(logical=True),
            "freq": cpu_freq._asdict() if cpu_freq else None
        }
        
        # Récupération des informations mémoire
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": memory.total / GB_DIVISOR,
            "available_gb": memory.available / GB_DIVISOR,
            "used_gb": memory.used / GB_DIVISOR,
            "percent": memory.percent
        }
        
        # Récupération des informations GPU
        gpu_info = []
        try:
            gpus = GPUtil.getGPUs()
            gpu_info = [{
                "name": gpu.name,
                "memory_total": gpu.memoryTotal,
                "memory_used": gpu.memoryUsed,
                "memory_free": gpu.memoryFree,
                "gpu_load": gpu.load * 100
            } for gpu in gpus]
        except (ImportError, RuntimeError) as e:
            logger.warning(f"Impossible de récupérer les informations GPU: {e}")
        
        # Récupération de la version d'Ollama
        try:
            api_url = f"{ollama_url}/api/version"
            response = requests.get(api_url, timeout=5)
            ollama_version = response.json().get('version', 'Non disponible') if response.status_code == 200 else "Non disponible"
            if response.status_code != 200:
                logger.warning(f"Erreur lors de la récupération de la version d'Ollama: {response.status_code}")
        except Exception as e:
            logger.warning(f"Impossible de récupérer la version d'Ollama: {e}")
            ollama_version = "Non disponible"
        
        return SystemInfo(
            os=platform.system(),
            os_version=platform.version(),
            python_version=sys.version,
            ollama_version=ollama_version,
            evallm_version=EVALLM_VERSION,
            cpu=cpu_info,
            memory=memory_info,
            gpu=gpu_info,
            hostname=platform.node()
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations système: {e}")
        return None

def read_content_from_file_if_exists(content: str) -> str:
    """Lit le contenu d'un fichier s'il existe, sinon retourne la chaîne d'origine."""
    # Vérifier si la chaîne ressemble à un chemin de fichier valide
    if isinstance(content, str):
        # Ignorer les chaînes qui sont clairement des prompts
        if (len(content) > 255 or  # Limite de longueur des noms de fichiers
            any(c in content for c in ['\n', '\r', '\t']) or  # Caractères spéciaux
            content.startswith('http://') or  # URL
            content.startswith('https://') or  # URL
            ' ' in content or  # Espaces dans le chemin
            content.count('/') > 10 or  # Trop de niveaux de répertoire
            content.count('\\') > 10):  # Trop de niveaux de répertoire (Windows)
            return content
            
        try:
            # Normaliser le chemin pour Windows
            content = content.replace('\\', '/')
            path = Path(content)
            if path.exists() and path.is_file():
                logger.info(f"Lecture du contenu depuis le fichier: {content}")
                return path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du fichier {content}: {e}")
            return content
    return content

def clean_for_json(obj, path=""):
    """Nettoie un objet pour le rendre sérialisable en JSON."""
    try:
        # Détection d'Undefined et autres types non-sérialisables
        if obj is None or obj == "undefined" or obj == "null" or (hasattr(obj, "__class__") and obj.__class__.__name__ == "Undefined"):
            return None
            
        # Types de base
        if isinstance(obj, (str, int, float, bool)):
            return obj
            
        # Dates
        if isinstance(obj, datetime):
            return obj.isoformat()
            
        # Dictionnaires
        if isinstance(obj, dict):
            return {k: clean_for_json(v, f"{path}.{k}" if path else k) 
                   for k, v in obj.items() 
                   if v is not None and not (hasattr(v, "__class__") and v.__class__.__name__ == "Undefined")}
                   
        # Listes et tuples
        if isinstance(obj, (list, tuple)):
            return [clean_for_json(item, f"{path}[{i}]" if path else f"[{i}]") 
                   for i, item in enumerate(obj) 
                   if item is not None and not (hasattr(item, "__class__") and item.__class__.__name__ == "Undefined")]
                   
        # Objets avec __dict__
        if hasattr(obj, '__dict__'):
            return clean_for_json(obj.__dict__, path)
            
        # Objets Pydantic
        if hasattr(obj, 'dict'):
            return clean_for_json(obj.dict(), path)
            
        # Objets avec model_dump
        if hasattr(obj, 'model_dump'):
            return clean_for_json(obj.model_dump(), path)

        # Vérification du type spécifique Undefined
        class_name = obj.__class__.__name__ if hasattr(obj, "__class__") else type(obj).__name__
        if class_name == "Undefined":
            logger.warning(f"Objet de type Undefined détecté à {path}")
            return None
            
        # Autres types d'objets
        try:
            return str(obj)
        except Exception as e:
            logger.warning(f"Impossible de convertir l'objet à {path} en chaîne: {e}")
            return None
            
    except Exception as e:
        logger.warning(f"Erreur lors du nettoyage de l'objet à {path}: {str(e)}")
        return None

def warmup_model(model: str, system_prompt: str, user_prompt: str, context: str = "") -> None:
    """Préchauffage du modèle avec une graine 0."""
    logger.info(f"Préchauffage du modèle {model}...")
    full_prompt = f"{context}\n\n{user_prompt}" if context else user_prompt
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt}
        ]
        for _ in range(1):
            ollama.chat(
                model=model,
                messages=messages,
                options={"seed": 0, "temperature": 0.0}
            )
            time.sleep(0.5)
        logger.info(f"Préchauffage réussi pour {model}")
    except Exception as e:
        logger.warning(f"Avertissement lors du préchauffage de {model}: {e}")

def extract_model_names(response: Any) -> List[str]:
    """Extrait les noms des modèles de la réponse d'Ollama."""
    try:
        import re
        
        # Conversion de la réponse en chaîne de caractères
        response_str = str(response)
        logger.debug(f"Réponse d'Ollama (string): {response_str[:200]}...")
        
        # Extraction des noms de modèles avec une regex précise
        model_names = re.findall(r"model=['\"](.*?)['\"]", response_str)
        
        # Filtrer les modèles valides (non vides et uniques)
        filtered_models = []
        seen = set()
        for name in model_names:
            if name and name not in seen:
                filtered_models.append(name)
                seen.add(name)
        
        if filtered_models:
            logger.info(f"Modèles trouvés avec regex: {filtered_models}")
            return filtered_models
            
        # Si la regex n'a rien trouvé, essayons d'autres approches
        if hasattr(response, 'models'):
            if isinstance(response.models, list):
                models = [m.model for m in response.models if hasattr(m, 'model') and m.model]
                return list(set(models))  # Éliminer les doublons
        
        # Pour les structures de type dictionnaire
        if isinstance(response, dict) and 'models' in response:
            models_list = response['models']
            if isinstance(models_list, list):
                if models_list and isinstance(models_list[0], dict) and 'model' in models_list[0]:
                    models = [m['model'] for m in models_list if m['model']]
                    return list(set(models))  # Éliminer les doublons
        
        logger.warning(f"Impossible d'extraire les noms de modèles de la réponse")
        return []
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des noms de modèles: {e}")
        return []

def compare_llms(config_file: str, output_file: Optional[str] = None, ollama_url: str = DEFAULT_OLLAMA_URL) -> List[Result]:
    """Compare différents LLM en utilisant Ollama selon la configuration spécifiée."""
    try:
        # Vérification du fichier de configuration
        config_path = Path(config_file)
        if not config_path.exists():
            logger.error(f"Le fichier de configuration {config_file} n'existe pas")
            return []

        # Chargement de la configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json_repair.load(f)
        config = ModelConfig(**config_data)

        # Validation de la configuration
        if not all([config.models, config.system_prompts, config.user_prompts]):
            logger.error("Configuration invalide: modèles, prompts système ou prompts utilisateur manquants")
            return []

        # Création du répertoire static/results s'il n'existe pas
        script_dir = Path(__file__).parent
        results_dir = script_dir / "static" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Détermination du nom du fichier de sortie
        base_name = config_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not output_file:
            output_file = str(results_dir / f"{base_name}_{timestamp}.html")
        elif not Path(output_file).is_absolute():
            # Si le chemin est relatif, le considérer comme relatif au dossier results
            output_file = str(results_dir / output_file)
            
        logger.info(f"Fichier de sortie HTML : {output_file}")
        
        # Initialisation du fichier JSON avec le même chemin mais extension .json
        json_output = Path(output_file).with_suffix('.json')
        logger.info(f"Fichier de sortie JSON : {json_output}")
        
        # Récupération des informations système
        system_info = get_system_info(ollama_url)
        
        # Initialisation du fichier JSON
        initial_json = {
            "system_info": clean_for_json(system_info.__dict__, "system_info"),
            "config": clean_for_json(config.to_dict(), "config"),
            "results": []
        }
        json_output.write_text(json.dumps(initial_json, indent=2, ensure_ascii=False), encoding='utf-8')

        # Traitement des fichiers pour les prompts
        system_prompts = {k: read_content_from_file_if_exists(v) for k, v in config.system_prompts.items()}
        user_prompts = {k: read_content_from_file_if_exists(v) for k, v in config.user_prompts.items()}
        contexts = {k: read_content_from_file_if_exists(v) for k, v in config.contexts.items()}

        logger.info(f"Configuration chargée : {len(config.models)} modèles, {len(system_prompts)} prompts système, "
                    f"{len(user_prompts)} prompts utilisateur, {len(contexts)} contextes")

        # Vérification des modèles disponibles
        try:
            logger.info("Vérification des modèles disponibles...")
            available_models_response = ollama.list()
            logger.debug(f"Réponse brute d'Ollama: {available_models_response}")
            
            available_models = extract_model_names(available_models_response)
            logger.info(f"Modèles disponibles: {available_models}")
            
            if not available_models:
                logger.warning("Aucun modèle n'a été trouvé. Vérifiez qu'Ollama est bien installé et en cours d'exécution.")
                logger.warning("Vous pouvez installer des modèles avec la commande 'ollama pull <nom_du_modèle>'")
                return []
            
            for model in config.models:
                if model not in available_models:
                    logger.warning(f"Le modèle '{model}' n'est pas disponible. Utilisez 'ollama pull {model}' pour le télécharger.")
                    
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des modèles: {e}")
            logger.error("Assurez-vous qu'Ollama est installé et en cours d'exécution.")
            logger.error("Vous pouvez vérifier l'état d'Ollama avec la commande 'ollama list'")
            return []

        # Calcul du nombre total d'itérations
        if not contexts:
            contexts = {"default": ""}  # Ajouter un contexte par défaut si aucun n'est fourni
        total_iterations = len(config.models) * len(system_prompts) * len(user_prompts) * len(contexts) * len(config.seeds) * len(config.temperatures)
        logger.info(f"Nombre total d'itérations à effectuer : {total_iterations}")
        
        results = []
        current_model = None
        
        with Progress(*progress_columns, console=console) as progress:
            task = progress.add_task("Génération des réponses...", total=total_iterations)
            
            for model in config.models:
                if current_model != model:
                    logger.info(f"Changement de modèle : passage à {model}")
                    first_sys_prompt = next(iter(system_prompts.values()))
                    first_user_prompt = next(iter(user_prompts.values()))
                    first_context = next(iter(contexts.values()))
                    warmup_model(model, first_sys_prompt, first_user_prompt, first_context)
                    current_model = model
                
                for sys_id, system_prompt in system_prompts.items():
                    for prompt_id, user_prompt in user_prompts.items():
                        for ctx_id, context in contexts.items():
                            for seed in config.seeds:
                                for temperature in config.temperatures:
                                    logger.debug(f"Génération pour {model} (seed={seed}, temp={temperature})")
                                    
                                    full_prompt = f"{user_prompt}\n\n{context}" if context else user_prompt
                                    start_time = time.time()
                                    
                                    try:
                                        response = ollama.chat(
                                            model=model,
                                            messages=[
                                                {"role": "system", "content": system_prompt},
                                                {"role": "user", "content": full_prompt}
                                            ],
                                            options={
                                                "seed": seed if seed is not None else None,
                                                "temperature": temperature
                                            }
                                        )
                                        
                                        result = Result(
                                            model=model,
                                            system_prompt=system_prompt,
                                            system_prompt_id=sys_id,
                                            user_prompt=user_prompt,
                                            user_prompt_id=prompt_id,
                                            context=context,
                                            context_id=ctx_id,
                                            seed=seed,
                                            temperature=temperature,
                                            response=response["message"]["content"],
                                            response_time=time.time() - start_time,
                                            commentaire=config.commentaire,
                                            Resultats=config.resultats if config.resultats else None
                                        )
                                        
                                    except Exception as e:
                                        logger.error(f"Erreur avec {model} (temp={temperature}): {e}")
                                        result = Result(
                                            model=model,
                                            system_prompt=system_prompt,
                                            system_prompt_id=sys_id,
                                            user_prompt=user_prompt,
                                            user_prompt_id=prompt_id,
                                            context=context,
                                            context_id=ctx_id,
                                            seed=seed,
                                            temperature=temperature,
                                            response=f"ERREUR: {str(e)}",
                                            response_time=time.time() - start_time,
                                            commentaire=config.commentaire,
                                            Resultats=config.resultats if config.resultats else None
                                        )
                                    
                                    results.append(result)
                                    
                                    # Mise à jour du fichier JSON
                                    try:
                                        json_data = json.loads(json_output.read_text(encoding='utf-8'))
                                        clean_result = clean_for_json(result.to_dict(), f"results[{len(json_data['results'])}]")
                                        json_data["results"].append(clean_result)
                                        json_output.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding='utf-8')
                                    except Exception as e:
                                        logger.error(f"Erreur lors de l'écriture du résultat dans le fichier JSON: {e}")
                                    
                                    progress.update(task, advance=1)
        
        logger.info("Génération des réponses terminée")
        
        # Génération du rapport HTML avec Jinja2
        script_dir = Path(__file__).parent
        env = Environment(loader=FileSystemLoader(str(script_dir)))
        env.globals.update({
            'sum': sum,
            'len': len,
            'min': min,
            'max': max,
            'str': str,
            'float': float,
            'int': int,
            'round': round,
            'datetime': datetime
        })
        template = env.from_string(HTML_TEMPLATE)
        
        # Préparation des données pour le template
        model_temp_times = {}
        model_temp_first_ids = {}
        avg_tokens = {}
        unique_system_prompts = {}
        unique_user_prompts = {}
        unique_contexts = {}
        grouped_results = {}
        sorted_seeds = sorted(config.seeds)
        previous_responses = []
        
        # Organisation des résultats
        for result in results:
            model_temp_key = f"{result.model} (temp={result.temperature})"
            if model_temp_key not in model_temp_times:
                model_temp_times[model_temp_key] = []
                model_temp_first_ids[model_temp_key] = f"model_{result.model.replace(':', '_')}_{str(result.temperature).replace('.', '_')}"
                avg_tokens[model_temp_key] = 0
            
            model_temp_times[model_temp_key].append(result.response_time)
            
            # Collecte des prompts uniques
            unique_system_prompts[result.system_prompt_id] = result.system_prompt
            unique_user_prompts[result.user_prompt_id] = result.user_prompt
            unique_contexts[result.context_id] = result.context
            
            # Groupement des résultats
            group_key = (result.model, result.system_prompt_id, result.user_prompt_id, result.context_id, result.temperature)
            if group_key not in grouped_results:
                grouped_results[group_key] = {}
            grouped_results[group_key][result.seed] = result
        
        html_content = template.render(
            results=results,
            system_info=system_info,
            datetime=datetime,
            config=config,
            model_temp_times=model_temp_times,
            model_temp_first_ids=model_temp_first_ids,
            avg_tokens=avg_tokens,
            unique_system_prompts=unique_system_prompts,
            unique_user_prompts=unique_user_prompts,
            unique_contexts=unique_contexts,
            grouped_results=grouped_results,
            sorted_seeds=sorted_seeds,
            previous_responses=previous_responses,
            output_file=output_file,
            available_models=available_models
        )
        
        # Sauvegarde du rapport HTML
        Path(output_file).write_text(html_content, encoding='utf-8')
        logger.info(f"Rapport HTML sauvegardé dans {output_file}")
        
        # Ouverture du rapport dans le navigateur
        webbrowser.open('file://' + str(Path(output_file).absolute()))
        logger.info("Rapport ouvert dans le navigateur")
        
        # Sauvegarde des résultats dans un fichier JSON
        json_output = Path(output_file).with_suffix('.json')
        try:
            # Nettoyer toutes les données avant de les sérialiser
            cleaned_system_info = clean_for_json(system_info.__dict__, "system_info")
            cleaned_config = clean_for_json(config.to_dict(), "config")
            cleaned_results = [clean_for_json(result.to_dict(), f"results[{i}]") for i, result in enumerate(results)]
            
            json_data = {
                "system_info": cleaned_system_info,
                "config": cleaned_config,
                "results": cleaned_results
            }
            
            # Vérifier la sérialisabilité avant d'écrire
            json.dumps(json_data)  # Test de sérialisation
            json_output.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding='utf-8')
            logger.info(f"Résultats sauvegardés dans {json_output}")
        except Exception as e:
            logger.error(f"Erreur lors de la sérialisation JSON: {e}")
            # Tentative de sauvegarde avec des données minimales
            minimal_json = {
                "system_info": {"error": "Erreur de sérialisation"},
                "config": {"error": "Erreur de sérialisation"},
                "results": []
            }
            json_output.write_text(json.dumps(minimal_json, indent=2), encoding='utf-8')
            logger.info(f"Données minimales sauvegardées dans {json_output} suite à une erreur")
        
        return results

    except json.JSONDecodeError as e:
        logger.error(f"Erreur de décodage JSON dans le fichier de configuration: {e}")
        return []
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        return []

def main():
    """Fonction principale pour exécuter le script depuis la ligne de commande."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comparer des LLM avec Ollama et générer un rapport HTML")
    parser.add_argument("config", help="Fichier de configuration JSON", nargs='?')
    parser.add_argument("--output", "-o", help="Fichier de sortie HTML (optionnel)")
    parser.add_argument("--debug", action="store_true", help="Activer le mode debug")
    parser.add_argument("--list", action="store_true", help="Afficher la liste des modèles disponibles au format JSON")
    parser.add_argument("--ollama-url", help=f"URL du serveur Ollama (défaut: {DEFAULT_OLLAMA_URL})", default=DEFAULT_OLLAMA_URL)
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Mode debug activé")
    
    if args.list:
        try:
            # Configuration de l'URL d'Ollama
            ollama.base_url = args.ollama_url
            available_models = [model.model for model in ollama.list().models]
            console.print_json(data=available_models)
            return
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des modèles: {e}")
            return
    
    if not args.config:
        parser.error("Le fichier de configuration est requis sauf si --list est utilisé")
    
    compare_llms(args.config, args.output, args.ollama_url)

if __name__ == "__main__":
    main()
